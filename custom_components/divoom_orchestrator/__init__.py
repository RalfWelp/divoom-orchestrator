"""Divoom GIF folder playlists."""

import asyncio
from collections.abc import Coroutine
import logging
import math
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .playlist import PlaylistController, scan_gifs
from .panel import async_register_panel

DOMAIN = "divoom_orchestrator"
_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
START_SCHEMA = vol.Schema(
    {
        vol.Required("device"): vol.All(cv.string, vol.Length(min=1)),
        vol.Required("folder"): vol.All(cv.string, vol.Length(min=1)),
        vol.Required("duration"): vol.All(vol.Coerce(float), vol.Range(min=1, max=3600)),
        vol.Optional("order", default="alphabetical"): vol.In(["alphabetical", "random"]),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions independently of the integration entry lifecycle."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_panel(hass)

    def controller() -> PlaylistController:
        instance = hass.data[DOMAIN].get("controller")
        if instance is None:
            raise HomeAssistantError("Divoom Orchestrator is not configured or not loaded")
        return instance

    async def start(call: ServiceCall) -> None:
        if not hass.services.has_service("divoom", "image"):
            raise HomeAssistantError("The divoom.image action is not available")
        root = Path(hass.config.path("pixelart"))
        folder = call.data["folder"]
        shuffle = call.data["order"] == "random"
        device = call.data["device"]
        duration = call.data["duration"]
        if not math.isfinite(duration):
            raise HomeAssistantError("Duration must be a finite number")

        async def scan() -> list[str]:
            return await hass.async_add_executor_job(scan_gifs, root, folder, shuffle)

        async def show(filename: str) -> None:
            await hass.services.async_call(
                "divoom", "image", {"device": device, "file": filename}, blocking=True
            )

        try:
            await controller().start(scan, show, duration)
        except (OSError, ValueError) as err:
            raise HomeAssistantError(f"Cannot start Divoom playlist: {err}") from err

    async def stop(call: ServiceCall) -> None:
        await controller().stop()

    hass.services.async_register(DOMAIN, "start", start, schema=START_SCHEMA)
    hass.services.async_register(DOMAIN, "stop", stop, schema=vol.Schema({}))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the playlist controller."""
    async def report_error(err: Exception) -> None:
        _LOGGER.error(
            "Divoom playlist stopped: %s",
            err,
            exc_info=(type(err), err, err.__traceback__),
        )
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Divoom Orchestrator: playlist stopped",
                "message": f"The playlist stopped: {err}",
                "notification_id": "divoom_orchestrator_error",
            },
            blocking=True,
        )

    def create_task(coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        return hass.async_create_background_task(coro, "Divoom playlist")

    hass.data[DOMAIN]["controller"] = PlaylistController(create_task, report_error)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop the playlist before unloading."""
    instance = hass.data[DOMAIN].pop("controller", None)
    if instance is not None:
        await instance.stop()
    return True
