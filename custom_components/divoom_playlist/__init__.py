"""Divoom GIF folder playlists."""

import asyncio
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .playlist import play, scan_gifs

DOMAIN = "divoom_playlist"
_LOGGER = logging.getLogger(__name__)

START_SCHEMA = vol.Schema(
    {
        vol.Required("device"): cv.string,
        vol.Required("folder"): cv.string,
        vol.Required("duration"): vol.All(vol.Coerce(float), vol.Range(min=1, max=3600)),
        vol.Optional("order", default="alphabetical"): vol.In(["alphabetical", "random"]),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register the single playlist controller."""
    root = Path(hass.config.path("pixelart"))
    current: asyncio.Task | None = None

    async def stop_current() -> None:
        nonlocal current
        if current is None:
            return
        task = current
        current = None
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def start(call: ServiceCall) -> None:
        nonlocal current
        if current is not None and not current.done():
            raise HomeAssistantError("Stop the current Divoom playlist before starting another")
        if not hass.services.has_service("divoom", "image"):
            raise HomeAssistantError("The divoom.image action is not available")
        folder = call.data["folder"]
        shuffle = call.data["order"] == "random"
        device = call.data["device"]

        async def scan() -> list[str]:
            return await hass.async_add_executor_job(scan_gifs, root, folder, shuffle)

        try:
            first = await scan()
        except (OSError, ValueError) as err:
            raise HomeAssistantError(f"Cannot read playlist folder: {err}") from err
        if not first:
            raise HomeAssistantError("The playlist folder contains no GIF files")

        async def show(filename: str) -> None:
            await hass.services.async_call(
                "divoom", "image", {"device": device, "file": filename}, blocking=True
            )

        async def run() -> None:
            try:
                await play(scan, show, call.data["duration"])
            except (OSError, ValueError, HomeAssistantError) as err:
                _LOGGER.exception("Divoom playlist stopped: %s", err)
                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "Divoom playlist stopped",
                        "message": f"The playlist stopped: {err}",
                        "notification_id": "divoom_playlist_error",
                    },
                    blocking=True,
                )

        current = hass.async_create_task(run())

    async def stop(call: ServiceCall) -> None:
        await stop_current()

    hass.services.async_register(DOMAIN, "start", start, schema=START_SCHEMA)
    hass.services.async_register(DOMAIN, "stop", stop)
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "start"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "stop"))
    entry.async_on_unload(lambda: current.cancel() if current and not current.done() else None)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True
