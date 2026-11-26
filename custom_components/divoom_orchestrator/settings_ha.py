"""Persistent defaults for the Orchestrator panel."""

import asyncio
import math

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

DOMAIN = "divoom_orchestrator"
DEFAULTS = {"duration": 5.0, "cooldown": 5.0, "community_sort": 1}


def validate(value):
    duration = float(value["duration"])
    cooldown = float(value["cooldown"])
    sort = value["community_sort"]
    if not math.isfinite(duration) or not 0 < duration <= 3600:
        raise ValueError("Anzeigedauer muss zwischen 0 und 3600 Sekunden liegen")
    if not math.isfinite(cooldown) or cooldown < 0:
        raise ValueError("Abklingzeit muss eine nicht negative Zahl sein")
    if sort not in (0, 1):
        raise ValueError("Ungültige Community-Sortierung")
    return {"duration": duration, "cooldown": cooldown, "community_sort": sort}


class Settings:
    def __init__(self, hass):
        self.store = Store(hass, 1, "divoom_orchestrator.settings")
        self.values = dict(DEFAULTS)
        self.lock = asyncio.Lock()

    async def load(self):
        saved = await self.store.async_load()
        if saved is not None:
            self.values = validate(saved)

    async def save(self, values):
        values = validate(values)
        async with self.lock:
            await self.store.async_save(values)
            self.values = values


def runtime(hass):
    settings = hass.data[DOMAIN].get("settings")
    if settings is None:
        raise HomeAssistantError("Orchestrator settings are not loaded")
    return settings


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "divoom_orchestrator/settings"})
@websocket_api.async_response
async def websocket_settings(hass, connection, msg):
    try:
        connection.send_result(msg["id"], runtime(hass).values)
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "settings_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/settings_save",
    vol.Required("duration"): vol.Coerce(float),
    vol.Required("cooldown"): vol.Coerce(float),
    vol.Required("community_sort"): vol.In([0, 1]),
})
@websocket_api.async_response
async def websocket_save(hass, connection, msg):
    try:
        settings = runtime(hass)
        await settings.save({key: msg[key] for key in DEFAULTS})
        connection.send_result(msg["id"], settings.values)
    except (HomeAssistantError, OSError, ValueError) as err:
        connection.send_error(msg["id"], "settings_error", str(err))


def register(hass):
    for command in (websocket_settings, websocket_save):
        websocket_api.async_register_command(hass, command)
