"""Text sources and persistent list selection for rotation blocks."""

import asyncio
import hashlib
import json
import math
import random

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

COLOR = vol.All([vol.All(vol.Coerce(int), vol.Range(min=0, max=255))], vol.Length(min=3, max=3))
TEXT = {
    vol.Required("name"): vol.All(cv.string, vol.Length(min=1, max=80)),
    vol.Required("source"): vol.In(["fixed", "entity", "list"]),
    vol.Required("text"): vol.All(cv.string, vol.Length(max=4096)),
    vol.Required("entity"): vol.All(cv.string, vol.Length(max=255)),
    vol.Required("attribute"): vol.All(cv.string, vol.Length(max=255)),
    vol.Required("lines"): vol.All([vol.All(cv.string, vol.Length(max=4096))], vol.Length(max=10000)),
    vol.Required("list_version"): vol.All(cv.string, vol.Length(max=80)),
    vol.Required("selection"): vol.In(["daily_order", "daily_random", "call_order", "call_random"]),
    vol.Required("foreground"): COLOR,
    vol.Required("background"): COLOR,
    vol.Required("size"): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
    vol.Required("time"): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    vol.Required("duration_mode"): vol.In(["seconds", "loops"]),
    vol.Required("duration"): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=3600)),
}
TEXT_SCHEMA = vol.Schema(TEXT)


def validate_text(settings: dict) -> None:
    """Reject invalid sources before persisting a rotation."""
    mode = settings["duration_mode"]
    value = float(settings["duration"])
    if not math.isfinite(value) or (mode == "loops" and not value.is_integer()):
        raise ValueError("Text duration must be finite and loop counts must be whole numbers")
    if settings["source"] == "fixed" and not settings["text"].strip():
        raise ValueError("Fixed text cannot be empty")
    if settings["source"] == "entity" and not settings["entity"].strip():
        raise ValueError("Select an entity for the text block")
    if settings["source"] == "list":
        lines = settings["lines"]
        if not settings["list_version"] or not lines or any(not line.strip() for line in lines):
            raise ValueError("Upload a nonempty UTF-8 text list")
        if sum(len(line.encode("utf-8")) for line in lines) > 1024 * 1024:
            raise ValueError("Text list exceeds 1 MiB")


class TextRuntime:
    """Select list values and persist only successful playback selections."""

    def __init__(self, hass):
        self.hass = hass
        self.store = Store(hass, 1, "divoom_orchestrator.text_progress")
        self.progress = {}
        self._lock = asyncio.Lock()

    async def load(self):
        saved = await self.store.async_load()
        if saved is not None:
            if not isinstance(saved, dict):
                raise ValueError("Invalid text progress storage")
            self.progress = saved

    async def select(self, block_id: str, settings: dict):
        source = settings["source"]
        if source == "fixed":
            text = settings["text"]
            return self._valid_text(text), None
        if source == "entity":
            state = self.hass.states.get(settings["entity"])
            if state is None or state.state in ("unknown", "unavailable"):
                raise ValueError(f"Entity unavailable: {settings['entity']}")
            attribute = settings["attribute"]
            value = state.attributes.get(attribute) if attribute else state.state
            if not isinstance(value, (str, int, float, bool)) or value is None:
                raise ValueError("Entity value must be a simple scalar")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Entity value must be finite")
            return self._valid_text(str(value)), None

        lines = settings["lines"]
        if not lines:
            raise ValueError("Text list is empty")
        signature = hashlib.sha256(json.dumps(
            [settings["list_version"], lines, settings["selection"]], ensure_ascii=False
        ).encode("utf-8")).hexdigest()
        current = self.progress.get(block_id, {})
        if not isinstance(current, dict) or current.get("signature") != signature:
            current = {}
        today = dt_util.now().date().isoformat()
        selection = settings["selection"]
        if selection.startswith("daily_") and current.get("day") == today:
            index = current.get("index")
            if not isinstance(index, int) or not 0 <= index < len(lines):
                raise ValueError("Invalid saved text selection")
        elif selection.endswith("_random"):
            index = random.randrange(len(lines))
        else:
            previous = current.get("index", -1)
            if not isinstance(previous, int):
                raise ValueError("Invalid saved text progress")
            index = (previous + 1) % len(lines)
        return self._valid_text(lines[index]), {"signature": signature, "index": index, "day": today}

    @staticmethod
    def _valid_text(text: str) -> str:
        if not text.strip() or text.strip().lower() in ("unknown", "unavailable"):
            raise ValueError("Text is empty or unavailable")
        if len(text) > 4096:
            raise ValueError("Text exceeds 4096 characters")
        return text

    async def commit(self, block_id: str, selection: dict | None) -> None:
        if selection is None:
            return
        async with self._lock:
            updated = dict(self.progress)
            updated[block_id] = selection
            await self.store.async_save(updated)
            self.progress = updated


def duration(settings: dict, text: str) -> float:
    """Approximate scrolling duration; device encoding may change frame count."""
    if settings["duration_mode"] == "seconds":
        return settings["duration"]
    frames = 16 + len(text) * settings["size"] * 0.6
    seconds = frames * settings["time"] / 1000 * settings["duration"]
    if not math.isfinite(seconds) or seconds > 3600:
        raise ValueError("Estimated text duration exceeds one hour")
    return max(0.01, seconds)
