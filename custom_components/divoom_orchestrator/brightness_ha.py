"""Home Assistant configuration and scheduling for brightness."""

import asyncio
from datetime import time, timedelta
import logging
import math
import time as monotonic_time
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .brightness import BrightnessController, scheduled_brightness

DOMAIN = "divoom_orchestrator"
_LOGGER = logging.getLogger(__name__)
DEFAULTS = {
    "enabled": False,
    "device": "",
    "motion": "",
    "connection": "",
    "morning": "05:00",
    "day": 100,
    "twilight": 50,
    "night": 10,
}
PERCENT = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
CONFIG_SCHEMA = vol.Schema({
    vol.Required("enabled"): cv.boolean,
    vol.Required("device"): cv.string,
    vol.Required("motion"): cv.string,
    vol.Required("connection"): cv.string,
    vol.Required("morning"): vol.Match(r"^(?:[01]\d|2[0-3]):[0-5]\d$"),
    vol.Required("day"): PERCENT,
    vol.Required("twilight"): PERCENT,
    vol.Required("night"): PERCENT,
})


class BrightnessRuntime:
    """Keep saved options and manage the running controller."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, 1, "divoom_orchestrator.brightness")
        self.config = dict(DEFAULTS)
        self.controller = BrightnessController(self._schedule, self._send, self._report)
        self._unsub_state = None
        self._unsub_timer = None
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._closed = False
        self._config_lock = asyncio.Lock()
        self._retry_at = 0.0
        self._motion_fault = False

    async def start(self) -> None:
        saved = await self.store.async_load()
        if saved is not None:
            self.config = CONFIG_SCHEMA(saved)
        self._listen()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._tick, timedelta(seconds=5)
        )
        self._task = self.hass.async_create_background_task(
            self._run(), "Divoom brightness"
        )
        self._set_motion_from_state()
        self.request()

    def _listen(self) -> None:
        if self._unsub_state:
            self._unsub_state()
        entities = ["sun.sun"]
        entities.extend(
            value for value in (self.config["motion"], self.config["connection"])
            if value and value not in entities
        )
        self._unsub_state = async_track_state_change_event(
            self.hass, entities, self._state_changed
        )

    def _set_motion_from_state(self) -> None:
        state = self.hass.states.get(self.config["motion"])
        self.controller.motion_changed(state is not None and state.state == "on")

    @callback
    def _state_changed(self, event: Any) -> None:
        entity_id = event.data["entity_id"]
        state = event.data["new_state"]
        if entity_id == self.config["motion"]:
            self.controller.motion_changed(state is not None and state.state == "on")
        if entity_id == self.config["connection"] and state and state.state == "connected":
            self.controller.connected()
            self._retry_at = 0.0
        self.request()

    @callback
    def _tick(self, now: Any) -> None:
        self.request()

    @callback
    def request(self) -> None:
        self._wake.set()

    async def _run(self) -> None:
        while not self._closed:
            await self._wake.wait()
            self._wake.clear()
            if self._closed:
                break
            if self.config["enabled"]:
                motion = self.config["motion"]
                state = self.hass.states.get(motion) if motion else None
                fault = bool(motion and (state is None or state.state not in ("on", "off")))
                if fault and not self._motion_fault:
                    await self._report(HomeAssistantError(f"Motion sensor unavailable: {motion}"))
                self._motion_fault = fault
                if monotonic_time.monotonic() < self._retry_at:
                    continue
                try:
                    await self.controller.refresh()
                except Exception:
                    # The controller reports the error; avoid flooding the device.
                    self._retry_at = monotonic_time.monotonic() + 30
                else:
                    self._retry_at = 0.0

    def _schedule(self) -> int:
        sun = self.hass.states.get("sun.sun")
        if sun is None or sun.state in ("unknown", "unavailable"):
            raise HomeAssistantError("Sun entity is unavailable")
        elevation = sun.attributes.get("elevation")
        rising = sun.attributes.get("rising")
        if not isinstance(elevation, (float, int)) or not math.isfinite(elevation):
            raise HomeAssistantError("Sun elevation is unavailable")
        if not isinstance(rising, bool):
            raise HomeAssistantError("Sun direction is unavailable")
        hour, minute = map(int, self.config["morning"].split(":"))
        now = dt_util.now().time().replace(tzinfo=None)
        return scheduled_brightness(
            now, time(hour, minute), elevation, rising,
            self.config["day"], self.config["twilight"], self.config["night"],
        )

    async def _send(self, action: str, value: int | None) -> None:
        data: dict[str, Any] = {"device": self.config["device"]}
        if value is not None:
            data["brightness"] = value
        await self.hass.services.async_call("divoom", action, data, blocking=True)

    async def _report(self, err: Exception) -> None:
        _LOGGER.error("Brightness control failed: %s", err, exc_info=err)
        await self.hass.services.async_call(
            "persistent_notification", "create",
            {"title": "Divoom Orchestrator: Helligkeit",
             "message": f"Helligkeitssteuerung fehlgeschlagen: {err}",
             "notification_id": "divoom_orchestrator_brightness_error"},
            blocking=True,
        )

    async def configure(self, config: dict[str, Any]) -> None:
        config = CONFIG_SCHEMA(config)
        config["device"] = config["device"].strip()
        for key in ("motion", "connection"):
            config[key] = config[key].strip()
            if config[key] and self.hass.states.get(config[key]) is None:
                raise HomeAssistantError(f"Unknown entity: {config[key]}")
        if config["motion"] and not config["motion"].startswith("binary_sensor."):
            raise HomeAssistantError("Motion must be a binary sensor")
        if config["enabled"] and not config["device"]:
            raise HomeAssistantError("A Divoom device is required")
        async with self._config_lock:
            await self.store.async_save(config)

            def update() -> None:
                self.config = config
                self._retry_at = 0.0
                self._motion_fault = False
                self._listen()
                self._set_motion_from_state()

            await self.controller.reconfigure(update)
        self.request()

    async def stop(self) -> None:
        self._closed = True
        if self._unsub_state:
            self._unsub_state()
        if self._unsub_timer:
            self._unsub_timer()
        self.request()
        if self._task:
            await self._task


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "divoom_orchestrator/brightness"})
@callback
def websocket_brightness(hass, connection, msg):
    """Expose the persisted settings to the admin panel."""
    runtime = hass.data[DOMAIN].get("brightness")
    if runtime is None:
        connection.send_error(msg["id"], "not_loaded", "Integration is not loaded")
        return
    connection.send_result(msg["id"], runtime.config)


def register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_brightness)

    async def configure(call: ServiceCall) -> None:
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise HomeAssistantError("Administrator access is required")
        runtime = hass.data[DOMAIN].get("brightness")
        if runtime is None:
            raise HomeAssistantError("Integration is not loaded")
        await runtime.configure(call.data)

    async def test(call: ServiceCall) -> None:
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise HomeAssistantError("Administrator access is required")
        runtime = hass.data[DOMAIN].get("brightness")
        if runtime is None or not runtime.config["enabled"]:
            raise HomeAssistantError("Enable brightness control before testing")
        runtime.controller.test(call.data["value"])
        await runtime.controller.refresh()

    hass.services.async_register(DOMAIN, "brightness_configure", configure, schema=CONFIG_SCHEMA)
    hass.services.async_register(
        DOMAIN, "brightness_test", test,
        schema=vol.Schema({vol.Required("value"): PERCENT}),
    )
