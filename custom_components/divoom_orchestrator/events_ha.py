"""Event editor storage and administrator-only playback."""

import asyncio
from copy import deepcopy
from datetime import date, datetime, time, timedelta
import logging
import math
from pathlib import Path
import re
from time import monotonic

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .gif_preview import gif_preview
from .playlist import scan_gifs
from .date_rules import validate_schedule

DOMAIN = "divoom_orchestrator"
_LOGGER = logging.getLogger(__name__)


def valid_value(value):
    value = vol.Coerce(float)(value)
    if not math.isfinite(value) or not 0 < value <= 3600:
        raise vol.Invalid("Value must be positive and no greater than 3600")
    return value


def valid_cooldown(value):
    value = vol.Coerce(float)(value)
    if not math.isfinite(value) or value <= 0:
        raise vol.Invalid("Cooldown must be a positive finite number of seconds")
    return value


STEP = {
    vol.Required("file"): cv.string,
    vol.Required("mode"): vol.In(["seconds", "loops"]),
    vol.Required("value"): valid_value,
}
EVENT = {
    vol.Optional("kind", default="trigger"): vol.In(["trigger", "date"]),
    vol.Optional("enabled", default=True): cv.boolean,
    vol.Optional("priority", default=3): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    vol.Optional("cooldown_seconds"): valid_cooldown,
    vol.Optional("schedule"): {
        vol.Required("mode"): vol.In(["annual", "once", "weekly", "dates_once", "dates_annual", "holiday"]),
        vol.Optional("start"): cv.string,
        vol.Optional("end"): cv.string,
        vol.Optional("weekdays"): [int],
        vol.Optional("dates"): [cv.string],
        vol.Optional("calendar"): cv.string,
        vol.Optional("holidays"): [cv.string],
    },
    vol.Optional("trigger"): {
        vol.Required("type"): vol.In(["manual", "state", "event"]),
        vol.Optional("entity_id"): cv.string,
        vol.Optional("to"): cv.string,
        vol.Optional("event_type"): cv.string,
    },
    vol.Required("folder"): vol.All(cv.string, vol.Length(min=1)),
    vol.Optional("device"): vol.All(cv.string, vol.Length(min=1)),
    vol.Required("steps"): [STEP],
}
EVENT_SCHEMA = vol.Schema(EVENT)


class CooldownActive(ValueError):
    """A trigger was requested before its cooldown expired."""


def folders(root: Path, folder: str) -> list[str]:
    """List only direct subdirectories within the media root."""
    root = root.resolve(strict=True)
    subdir = Path(folder)
    if not folder or subdir.is_absolute():
        raise ValueError("Folder must be relative to the Divoom directory")
    directory = (root / subdir).resolve(strict=True)
    if not directory.is_relative_to(root) or not directory.is_dir():
        raise ValueError("Folder is outside the Divoom directory or not a directory")
    children = []
    for path in directory.iterdir():
        resolved = path.resolve(strict=True)
        if resolved.is_relative_to(root) and resolved.is_dir():
            children.append(path.relative_to(root).as_posix())
    return sorted(children, key=lambda value: (value.casefold(), value))


def folder_nodes(root: Path, folder: str) -> list[dict]:
    """List folders with whether each contains further folders."""
    return [
        {"path": child, "has_children": bool(folders(root, child))}
        for child in folders(root, folder)
    ]


class EventStore:
    """Store ordered event steps independently from playlist durations."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, 1, "divoom_orchestrator.events")
        self.events: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._subscriptions = []
        self._trigger_tasks: set[asyncio.Task] = set()
        self._started_at: dict[str, float] = {}

    @property
    def root(self) -> Path:
        return Path(self.hass.config.path("pixelart"))

    async def load(self) -> None:
        saved = await self.store.async_load()
        if saved is not None:
            self.events = vol.Schema({cv.string: EVENT_SCHEMA})(saved)
            for event in self.events.values():
                validate_trigger(event)

    async def prepare(self, event: dict) -> list[tuple[str, float]]:
        files = await self.hass.async_add_executor_job(scan_gifs, self.root, event["folder"], False)
        steps = event["steps"]
        if not steps:
            raise ValueError("Select at least one GIF")
        if len({step["file"] for step in steps}) != len(steps):
            raise ValueError("The same GIF cannot be selected twice")
        prepared = []
        for step in steps:
            filename = step["file"]
            if filename not in files:
                raise ValueError(f"GIF is no longer in the selected folder: {filename}")
            value = valid_value(step["value"])
            if step["mode"] == "loops":
                if not value.is_integer():
                    raise ValueError(f"Loop count must be a whole number: {filename}")
                preview = await self.hass.async_add_executor_job(
                    gif_preview, self.root, event["folder"], filename
                )
                if preview["cycle_seconds"] is None:
                    raise ValueError(f"GIF has no usable loop duration: {filename}")
                value *= preview["cycle_seconds"]
            if value > 3600:
                raise ValueError(f"Display duration exceeds one hour: {filename}")
            prepared.append((filename, value))
        return prepared

    async def save(self, name: str, event: dict, displayed: list[str]) -> None:
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("Event name must contain 1 to 80 characters")
        event = EVENT_SCHEMA(event)
        validate_trigger(event)
        if event.get("kind", "trigger") == "date":
            if "schedule" not in event:
                raise ValueError("A date schedule is required")
            validate_schedule(event["schedule"])
        async with self._lock:
            files = await self.hass.async_add_executor_job(scan_gifs, self.root, event["folder"], False)
            if len(set(displayed)) != len(displayed) or set(displayed) != set(files):
                raise ValueError("GIF list changed; refresh the folder and try again")
            await self.prepare(event)
            updated = dict(self.events)
            updated[name] = event
            await self.store.async_save(updated)
            self.events = updated
            self.listen()

    async def delete(self, name: str) -> None:
        async with self._lock:
            if name not in self.events:
                raise ValueError("Event does not exist")
            updated = dict(self.events)
            del updated[name]
            await self.store.async_save(updated)
            self.events = updated
            self._started_at.pop(name, None)
            self.listen()

    async def calendar_holidays(self, entity: str, days: int) -> set[str]:
        """Return individual event titles, including merged Holiday titles."""
        if not re.fullmatch(r"calendar\.[a-z0-9_]+", entity):
            raise ValueError("Select a calendar entity")
        state = self.hass.states.get(entity)
        if state is None or state.state in ("unknown", "unavailable"):
            raise ValueError(f"Calendar unavailable: {entity}")
        now = dt_util.now()
        start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        end = datetime.combine(now.date() + timedelta(days=days), time.min, tzinfo=now.tzinfo)
        names = set()
        cursor = start
        while cursor < end:
            segment_end = min(end, datetime.combine(
                cursor.date() + timedelta(days=365), time.min, tzinfo=now.tzinfo
            ))
            response = await self.hass.services.async_call(
                "calendar", "get_events",
                {"entity_id": entity, "start_date_time": cursor.isoformat(),
                 "end_date_time": segment_end.isoformat()},
                blocking=True, return_response=True,
            )
            if not isinstance(response, dict) or not isinstance(response.get(entity), dict):
                raise ValueError(f"Calendar returned no event data: {entity}")
            records = response[entity].get("events")
            if not isinstance(records, list):
                raise ValueError(f"Calendar returned invalid event data: {entity}")
            for record in records:
                if (not isinstance(record, dict) or not isinstance(record.get("summary"), str)
                        or not isinstance(record.get("start"), str)):
                    raise ValueError(f"Calendar returned an event without a title or start: {entity}")
                try:
                    raw_start = record["start"]
                    if len(raw_start) == 10:
                        event_date = date.fromisoformat(raw_start)
                    else:
                        timestamp = datetime.fromisoformat(raw_start)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=now.tzinfo)
                        event_date = timestamp.astimezone(now.tzinfo).date()
                except ValueError as err:
                    raise ValueError(f"Calendar returned an invalid event start: {entity}") from err
                if cursor.date() <= event_date < segment_end.date():
                    names.update(name.strip() for name in record["summary"].split(";") if name.strip())
            cursor = segment_end
        return names

    def listen(self) -> None:
        """Replace listeners without firing events for existing entity states."""
        for unsub in self._subscriptions:
            unsub()
        self._subscriptions.clear()
        for name, event in self.events.items():
            if event.get("kind", "trigger") != "trigger" or not event.get("enabled", True):
                continue
            trigger = event.get("trigger", {"type": "manual"})
            if trigger["type"] == "state":
                @callback
                def changed(change, name=name, trigger=trigger):
                    old, new = change.data.get("old_state"), change.data.get("new_state")
                    if old is not None and new is not None and old.state != new.state and new.state == trigger["to"]:
                        self._dispatch(name)
                self._subscriptions.append(async_track_state_change_event(
                    self.hass, [trigger["entity_id"]], changed
                ))
            elif trigger["type"] == "event":
                @callback
                def fired(change, name=name):
                    self._dispatch(name)
                self._subscriptions.append(self.hass.bus.async_listen(trigger["event_type"], fired))

    def _dispatch(self, name: str) -> None:
        task = self.hass.async_create_background_task(self._run_trigger(name), f"Divoom trigger {name}")
        self._trigger_tasks.add(task)
        task.add_done_callback(self._trigger_tasks.discard)

    async def _run_trigger(self, name: str) -> None:
        try:
            await self.play_event(name, automatic=True)
        except CooldownActive as err:
            _LOGGER.debug("Ignoring trigger %s: %s", name, err)
        except (OSError, ValueError, vol.Invalid, HomeAssistantError) as err:
            if isinstance(err, ValueError) and str(err) == "An event is already running with equal or higher priority":
                _LOGGER.debug("Ignoring trigger %s: %s", name, err)
                return
            rotation = self.hass.data[DOMAIN].get("rotation")
            if rotation is not None:
                await rotation._report("trigger", f"{name}: {err}")
            else:
                _LOGGER.error("Triggered event %s failed: %s", name, err)

    async def close(self) -> None:
        for unsub in self._subscriptions:
            unsub()
        self._subscriptions.clear()
        if self._trigger_tasks:
            await asyncio.gather(*self._trigger_tasks)

    async def play_event(self, name: str, *, automatic: bool = False, test: bool = False) -> None:
        """Play a saved snapshot, shared by automatic and manual triggers."""
        event = deepcopy(self.events.get(name))
        if event is None:
            raise ValueError("Event does not exist")
        if automatic and (event.get("kind", "trigger") != "trigger" or not event.get("enabled", True)):
            return
        data = self.hass.data[DOMAIN]
        controller = data.get("controller")
        if controller is None:
            raise HomeAssistantError("Integration is not loaded")
        if not self.hass.services.has_service("divoom", "image"):
            raise HomeAssistantError("The divoom.image action is not available")
        brightness = data.get("brightness")
        if brightness is None or not brightness.config["device"].strip():
            raise HomeAssistantError("Configure a Divoom device in settings first")
        is_trigger = event.get("kind", "trigger") == "trigger"
        cooldown = event.get("cooldown_seconds") if is_trigger and not test else None

        def check_cooldown() -> None:
            last_started = self._started_at.get(name)
            if cooldown is not None and last_started is not None:
                remaining = cooldown - (monotonic() - last_started)
                if remaining > 0:
                    raise CooldownActive(f"Cooldown active for {name}: {remaining:.1f} seconds remaining")

        check_cooldown()
        if is_trigger and not brightness.config["enabled"]:
            raise HomeAssistantError("Enable brightness automation before testing a triggered event")
        device = brightness.config["device"].strip()
        try:
            steps = await self.prepare(event)
        except (OSError, ValueError, vol.Invalid) as err:
            rotation = data.get("rotation")
            if not is_trigger or rotation is None:
                raise
            await rotation._report("trigger", f"{name}: {err}")
            seconds = rotation.config["error_seconds"] if rotation.config else 5
            steps = await rotation._fallback("trigger", seconds)
            if not steps:
                raise ValueError(f"Cannot play event or its error image: {err}") from err

        async def event_started():
            if cooldown is not None:
                self._started_at[name] = monotonic()
            brightness.controller.event_started()
            await brightness.controller.refresh()

        async def event_finished():
            brightness.controller.event_finished()
            brightness.request()

        async def show(filename):
            while True:
                try:
                    await self.hass.services.async_call(
                        "divoom", "image", {"device": device, "file": filename}, blocking=True
                    )
                    rotation = data.get("rotation")
                    if rotation is not None:
                        rotation._reported.discard("transfer")
                    return
                except (HomeAssistantError, OSError) as err:
                    rotation = data.get("rotation")
                    if rotation is None:
                        raise HomeAssistantError(f"Failed to display {filename}: {err}") from err
                    await rotation._report("transfer", f"{filename}: {err}; retrying in 30 seconds")
                    if await controller.wait_for_interrupt(30):
                        return

        check_cooldown()
        await controller.start_event(
            steps, show, device, priority=event.get("priority", 3), name=name,
            on_start=event_started if is_trigger else None,
            on_finish=event_finished if is_trigger else None,
        )


def validate_trigger(event: dict) -> None:
    """Validate the single selected trigger without querying current state."""
    trigger = event.get("trigger", {"type": "manual"})
    kind = trigger.get("type")
    if kind == "state":
        if (not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", trigger.get("entity_id", ""))
                or not trigger.get("to", "").strip()):
            raise ValueError("State triggers require an entity and target state")
    elif kind == "event":
        if not trigger.get("event_type", "").strip():
            raise ValueError("Event triggers require an event type")
    elif kind != "manual":
        raise ValueError("Invalid trigger type")


def runtime(hass: HomeAssistant) -> EventStore:
    instance = hass.data[DOMAIN].get("events")
    if instance is None:
        raise HomeAssistantError("Integration is not loaded")
    return instance


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/event_folders",
    vol.Required("folder"): str,
    vol.Optional("include_children", default=False): bool,
})
@websocket_api.async_response
async def websocket_folders(hass, connection, msg):
    try:
        store = runtime(hass)
        list_folders = folder_nodes if msg.get("include_children", False) else folders
        result = await hass.async_add_executor_job(list_folders, store.root, msg["folder"])
        connection.send_result(msg["id"], result)
    except (OSError, ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "folder_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "divoom_orchestrator/events"})
@websocket_api.async_response
async def websocket_events(hass, connection, msg):
    try:
        connection.send_result(msg["id"], runtime(hass).events)
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "not_loaded", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/holiday_names",
    vol.Required("calendar"): str,
})
@websocket_api.async_response
async def websocket_holiday_names(hass, connection, msg):
    try:
        names = await runtime(hass).calendar_holidays(msg["calendar"], 730)
        connection.send_result(msg["id"], sorted(names, key=str.casefold))
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "calendar_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/event_save",
    vol.Required("name"): str,
    vol.Required("event"): EVENT,
    vol.Required("files"): [str],
})
@websocket_api.async_response
async def websocket_save(hass, connection, msg):
    try:
        await runtime(hass).save(msg["name"], msg["event"], msg["files"])
        connection.send_result(msg["id"])
    except (OSError, ValueError, vol.Invalid, HomeAssistantError) as err:
        connection.send_error(msg["id"], "save_failed", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/event_delete",
    vol.Required("name"): str,
})
@websocket_api.async_response
async def websocket_delete(hass, connection, msg):
    try:
        await runtime(hass).delete(msg["name"])
        connection.send_result(msg["id"])
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "delete_failed", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/event_test",
    vol.Required("name"): str,
})
@websocket_api.async_response
async def websocket_test(hass, connection, msg):
    try:
        await runtime(hass).play_event(msg["name"], test=True)
        connection.send_result(msg["id"])
    except (OSError, ValueError, vol.Invalid, HomeAssistantError) as err:
        connection.send_error(msg["id"], "event_failed", str(err))


def register(hass: HomeAssistant) -> None:
    for command in (websocket_folders, websocket_events, websocket_holiday_names, websocket_save,
                    websocket_delete, websocket_test):
        websocket_api.async_register_command(hass, command)
