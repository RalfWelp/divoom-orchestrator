"""Persist and play the start and date-event rotation."""

import asyncio
from copy import deepcopy
import logging
import random
import re

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .date_rules import is_active
from .events_ha import STEP, valid_value
from .playlist import scan_gifs
from .text_ha import TEXT, duration as text_duration, validate_text

DOMAIN = "divoom_orchestrator"
_LOGGER = logging.getLogger(__name__)
TEXT_END_PADDING = " " * 8
ROTATION = {
    vol.Required("folder"): vol.All(cv.string, vol.Length(min=1)),
    vol.Required("steps"): [STEP],
    vol.Required("date_events"): cv.boolean,
    vol.Required("error_seconds"): valid_value,
    vol.Optional("blocks"): [cv.string],
    vol.Optional("inactive_blocks"): [cv.string],
    vol.Optional("texts", default={}): {cv.string: TEXT},
    vol.Optional("weather"): {
        vol.Required("entity"): vol.All(cv.string, vol.Length(min=1)),
        vol.Required("seconds"): valid_value,
    },
}
SCHEMA = vol.Schema(ROTATION)


class RotationRuntime:
    """Build a fresh ordered cycle while using the shared playback controller."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, 1, "divoom_orchestrator.rotation")
        self.config = None
        self.manual_stop = False
        self._lock = asyncio.Lock()
        self._cycle: dict[str, tuple[str | dict, float]] = {}
        self._reported: set[str] = set()
        self._owns_controller = False
        self._last_weather: str | None = None
        self._startup_task: asyncio.Task | None = None
        self._closed = False

    async def load(self) -> None:
        saved = await self.store.async_load()
        if saved is not None:
            self.config = SCHEMA(saved)

    async def save(self, data: dict, displayed: list[str]) -> None:
        config = SCHEMA(data)
        blocks = config.get("blocks", ["date"] if config["date_events"] else [])
        if len(set(blocks)) != len(blocks):
            raise ValueError("Each rotation block must have a unique ID")
        inactive = config.get("inactive_blocks", [])
        if len(set(inactive)) != len(inactive) or not set(inactive).issubset(blocks):
            raise ValueError("Inactive blocks must be unique rotation blocks")
        for block in blocks:
            if block in ("weather", "date"):
                continue
            if not re.fullmatch(r"text:[a-zA-Z0-9_-]{1,80}", block) or block not in config.get("texts", {}):
                raise ValueError(f"Unknown rotation block: {block}")
            validate_text(config["texts"][block])
        if set(config.get("texts", {})) != {block for block in blocks if block.startswith("text:")}:
            raise ValueError("Text configuration does not match rotation blocks")
        if "weather" in blocks and "weather" not in inactive and not config.get("weather", {}).get("entity", "").startswith("weather."):
            raise ValueError("Select a weather entity")
        events = self.hass.data[DOMAIN]["events"]
        async with self._lock:
            files = await self.hass.async_add_executor_job(scan_gifs, events.root, config["folder"], False)
            if len(set(displayed)) != len(displayed) or set(files) != set(displayed):
                raise ValueError("GIF list changed; refresh the folder and try again")
            await events.prepare(config)
            await self.store.async_save(config)
            self.config = config
        if not self.manual_stop and not self.hass.data[DOMAIN]["controller"].running:
            await self.auto_start()

    async def _report(self, key: str, message: str) -> None:
        if key in self._reported:
            return
        self._reported.add(key)
        _LOGGER.warning("Rotation %s: %s", key, message)
        await self.hass.services.async_call(
            "persistent_notification", "create",
            {"title": "Divoom Orchestrator: Rotation",
             "message": f"{key}: {message}",
             "notification_id": f"divoom_orchestrator_rotation_{key}"},
            blocking=True,
        )

    async def _fallback(self, name: str, seconds: float) -> list[tuple[str, float]]:
        events = self.hass.data[DOMAIN]["events"]
        filename = f"fehler/{name}.gif"
        try:
            files = await self.hass.async_add_executor_job(scan_gifs, events.root, "fehler", False)
            if filename not in files:
                raise ValueError(f"Missing error image: {filename}")
            return [(filename, seconds)]
        except (OSError, ValueError) as err:
            await self._report(f"{name}_fallback", str(err))
            return []

    async def _sequence(self) -> list[str]:
        config = deepcopy(self.config)
        if config is None:
            raise ValueError("Rotation is not configured")
        events = self.hass.data[DOMAIN]["events"]
        saved = deepcopy(events.events)
        try:
            sequence = await events.prepare(config)
        except (OSError, ValueError, vol.Invalid) as err:
            await self._report("start", str(err))
            sequence = await self._fallback("start", config["error_seconds"])
        inactive = set(config.get("inactive_blocks", []))
        for block in config.get("blocks", ["date"] if config["date_events"] else []):
            if block in inactive:
                continue
            if block == "weather":
                try:
                    sequence.append(await self._weather(config["weather"]))
                    self._reported.discard("weather")
                except (KeyError, OSError, ValueError) as err:
                    await self._report("weather", str(err))
                    sequence.extend(await self._fallback("wetter", config["error_seconds"]))
            elif block == "date":
                today = dt_util.now().date()
                for name in sorted(saved, key=lambda value: (value.casefold(), value)):
                    event = saved[name]
                    if event.get("kind") != "date" or not event.get("enabled", True):
                        continue
                    try:
                        if not is_active(event["schedule"], today):
                            continue
                        sequence.extend(await events.prepare(event))
                    except (KeyError, OSError, ValueError, vol.Invalid) as err:
                        await self._report("date", f"{name}: {err}")
                        sequence.extend(await self._fallback("datum", config["error_seconds"]))
            elif block.startswith("text:"):
                sequence.append(({"id": block, "settings": config["texts"][block],
                                  "error_seconds": config["error_seconds"]}, 1.0))
        if not sequence:
            raise ValueError("No start animation or error image can be played")
        self._cycle = {str(index): item for index, item in enumerate(sequence)}
        return list(self._cycle)

    async def _weather(self, settings: dict) -> tuple[str, float]:
        state = self.hass.states.get(settings["entity"])
        sun = self.hass.states.get("sun.sun")
        if state is None or not re.fullmatch(r"[a-z0-9_-]+", state.state) or state.state in ("unknown", "unavailable"):
            raise ValueError(f"Weather unavailable or invalid: {settings['entity']}")
        if sun is None or sun.state not in ("above_horizon", "below_horizon"):
            raise ValueError("Sun state unavailable")
        phase = "tag" if sun.state == "above_horizon" else "nacht"
        folder = f"wetter/{state.state}/{phase}"
        files = await self.hass.async_add_executor_job(
            scan_gifs, self.hass.data[DOMAIN]["events"].root, folder, False
        )
        if not files:
            raise ValueError(f"No GIFs in {folder}")
        choices = [item for item in files if item != self._last_weather] if len(files) > 1 else files
        filename = random.choice(choices)
        self._last_weather = filename
        return filename, settings["seconds"]

    async def start(self) -> None:
        async with self._lock:
            if self.config is None:
                raise ValueError("Configure the start animation first")
            data = self.hass.data[DOMAIN]
            device = data["brightness"].config["device"].strip()
            if not device:
                raise ValueError("Configure the Divoom device in settings")
            if not self.hass.services.has_service("divoom", "image"):
                raise HomeAssistantError("The divoom.image action is not available")
            await data["events"].prepare(self.config)

            async def show(token: str) -> None:
                item, _ = self._cycle[token]
                action = "image"
                selection = None
                block_id = None
                if isinstance(item, dict):
                    block_id = item["id"]
                    try:
                        settings = item["settings"]
                        text, selection = await data["texts"].select(block_id, settings)
                        text += TEXT_END_PADDING
                        seconds = await self.hass.async_add_executor_job(text_duration, settings, text)
                        self._cycle[token] = (item, seconds)
                        payload = {"device": device, "text": text, "size": settings["size"],
                                   "time": settings["time"], "foreground_color": settings["foreground"],
                                   "background_color": settings["background"]}
                        action = "text"
                        self._reported.discard("text")
                    except (KeyError, OSError, ValueError, vol.Invalid) as err:
                        await self._report("text", f"{block_id}: {err}")
                        fallback = await self._fallback("text", item["error_seconds"])
                        if not fallback:
                            self._cycle[token] = (item, 0.01)
                            return
                        filename, seconds = fallback[0]
                        self._cycle[token] = (item, seconds)
                        payload = {"device": device, "file": filename}
                        selection = None
                else:
                    payload = {"device": device, "file": item}
                while True:
                    try:
                        await self.hass.services.async_call(
                            "divoom", action, payload, blocking=True
                        )
                        self._reported.discard("transfer")
                    except (HomeAssistantError, OSError) as err:
                        await self._report("transfer", f"{action}: {err}; retrying in 30 seconds")
                        if await data["controller"].wait_for_interrupt(30):
                            return
                    else:
                        if block_id is not None:
                            await data["texts"].commit(block_id, selection)
                        return

            await data["controller"].start(
                self._sequence, show, 10, lambda key: self._cycle[key][1], device
            )
            self._owns_controller = True
            self.manual_stop = False

    async def stop(self) -> None:
        self.manual_stop = True
        await self._cancel_startup()
        async with self._lock:
            self.manual_stop = True
            await self.hass.data[DOMAIN]["controller"].stop()
            self._owns_controller = False

    async def device_changed(self) -> None:
        controller = self.hass.data[DOMAIN]["controller"]
        if self._owns_controller and controller.running:
            await controller.stop()
            self._owns_controller = False
        if not self.manual_stop and not controller.running:
            await self.auto_start()

    async def auto_start(self) -> None:
        if self.config is None or self.manual_stop or self._closed:
            return
        try:
            await self.start()
        except (OSError, ValueError, vol.Invalid, HomeAssistantError) as err:
            await self._report("autostart", str(err))
            if (not self.manual_stop and not self._closed
                    and self.hass.data[DOMAIN]["brightness"].config["device"].strip()
                    and not self.hass.services.has_service("divoom", "image")
                    and (self._startup_task is None or self._startup_task.done())):
                self._startup_task = self.hass.async_create_background_task(
                    self._retry_startup(), "Divoom rotation startup retry"
                )

    async def _retry_startup(self) -> None:
        while not self._closed and not self.manual_stop:
            await asyncio.sleep(30)
            if self.hass.data[DOMAIN]["controller"].running:
                return
            if self.hass.services.has_service("divoom", "image"):
                await self.auto_start()
                return

    async def _cancel_startup(self) -> None:
        task = self._startup_task
        self._startup_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def close(self) -> None:
        self._closed = True
        await self._cancel_startup()


def runtime(hass: HomeAssistant) -> RotationRuntime:
    instance = hass.data[DOMAIN].get("rotation")
    if instance is None:
        raise HomeAssistantError("Integration is not loaded")
    return instance


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "divoom_orchestrator/rotation"})
@websocket_api.async_response
async def websocket_rotation(hass, connection, msg):
    try:
        connection.send_result(msg["id"], runtime(hass).config)
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "not_loaded", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/rotation_save",
    vol.Required("config"): ROTATION,
    vol.Required("files"): [str],
})
@websocket_api.async_response
async def websocket_save(hass, connection, msg):
    try:
        await runtime(hass).save(msg["config"], msg["files"])
        connection.send_result(msg["id"])
    except (OSError, ValueError, vol.Invalid, HomeAssistantError) as err:
        connection.send_error(msg["id"], "save_failed", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/rotation_start",
})
@websocket_api.async_response
async def websocket_start(hass, connection, msg):
    try:
        await runtime(hass).start()
        connection.send_result(msg["id"])
    except (OSError, ValueError, vol.Invalid, HomeAssistantError) as err:
        connection.send_error(msg["id"], "start_failed", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/rotation_stop",
})
@websocket_api.async_response
async def websocket_stop(hass, connection, msg):
    try:
        await runtime(hass).stop()
        connection.send_result(msg["id"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "stop_failed", str(err))


def register(hass: HomeAssistant) -> None:
    for command in (websocket_rotation, websocket_save, websocket_start, websocket_stop):
        websocket_api.async_register_command(hass, command)
