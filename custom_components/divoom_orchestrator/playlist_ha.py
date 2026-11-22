"""Persist and expose per-animation display durations."""

import asyncio
import math
from pathlib import Path

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .playlist import scan_gifs

DOMAIN = "divoom_orchestrator"


def valid_duration(value):
    value = vol.Coerce(float)(value)
    if not math.isfinite(value) or not 1 <= value <= 3600:
        raise vol.Invalid("Duration must be between 1 and 3600 seconds")
    return value


SAVE_SCHEMA = vol.Schema({
    vol.Required("folder"): vol.All(cv.string, vol.Length(min=1)),
    vol.Required("durations"): {cv.string: valid_duration},
    vol.Required("files"): [cv.string],
})


class PlaylistDurations:
    """Keep durations keyed by root-relative file paths."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, 1, "divoom_orchestrator.playlist_durations")
        self.values: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        saved = await self.store.async_load()
        if saved is not None:
            self.values = vol.Schema({cv.string: valid_duration})(saved)

    async def scan(self, folder: str) -> list[str]:
        return await self.hass.async_add_executor_job(
            scan_gifs, Path(self.hass.config.path("pixelart")), folder, False
        )

    async def save(self, folder: str, values: dict[str, float], displayed: list[str]) -> None:
        async with self._lock:
            files = await self.scan(folder)
            if (len(set(displayed)) != len(displayed) or set(displayed) != set(files)
                    or not set(values).issubset(files)):
                raise HomeAssistantError("GIF list changed; refresh the folder and try again")
            updated = dict(self.values)
            for name in files:
                updated.pop(name, None)
            updated.update(values)
            await self.store.async_save(updated)
            self.values = updated


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/playlist_files",
    vol.Required("folder"): str,
})
@websocket_api.async_response
async def websocket_playlist_files(hass, connection, msg):
    runtime = hass.data[DOMAIN].get("durations")
    if runtime is None:
        connection.send_error(msg["id"], "not_loaded", "Integration is not loaded")
        return
    try:
        files = await runtime.scan(msg["folder"])
    except (OSError, ValueError) as err:
        connection.send_error(msg["id"], "scan_failed", str(err))
        return
    connection.send_result(msg["id"], [
        {"file": filename, "duration": runtime.values.get(filename)}
        for filename in files
    ])


def register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_playlist_files)

    async def save(call: ServiceCall) -> None:
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise HomeAssistantError("Administrator access is required")
        runtime = hass.data[DOMAIN].get("durations")
        if runtime is None:
            raise HomeAssistantError("Integration is not loaded")
        try:
            await runtime.save(call.data["folder"], dict(call.data["durations"]), call.data["files"])
        except (OSError, ValueError) as err:
            raise HomeAssistantError(f"Cannot save GIF durations: {err}") from err

    hass.services.async_register(DOMAIN, "playlist_durations", save, schema=SAVE_SCHEMA)
