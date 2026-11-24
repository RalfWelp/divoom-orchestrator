"""Contract tests with Home Assistant APIs simulated, not a real HA runtime."""

import asyncio
from datetime import datetime
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image
import voluptuous as real_vol


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "divoom_orchestrator"


def module(name, **attributes):
    result = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(result, key, value)
    return result


class FakeError(Exception):
    pass


class FakeServices:
    def __init__(self):
        self.handlers = {}
        self.calls = []
        self.image_error = None

    def async_register(self, domain, name, handler, **kwargs):
        self.handlers[domain, name] = handler

    def has_service(self, domain, name):
        return (domain, name) == ("divoom", "image")

    async def async_call(self, domain, name, data, blocking=False):
        self.calls.append((domain, name, data))
        if domain == "divoom" and self.image_error:
            raise self.image_error


class FakeHass:
    def __init__(self, path):
        self.data = {}
        self.services = FakeServices()
        self.config = types.SimpleNamespace(path=lambda name: str(path / name))
        self.http = types.SimpleNamespace(async_register_static_paths=AsyncMock())
        self.states = types.SimpleNamespace(get=lambda entity: None)
        self.state_listeners = []
        self.bus_listeners = []
        self.bus = types.SimpleNamespace(async_listen=self.listen_bus)

    def listen_state(self, entities, callback):
        record = (entities, callback)
        self.state_listeners.append(record)
        return lambda: self.state_listeners.remove(record)

    def listen_bus(self, event_type, callback):
        record = (event_type, callback)
        self.bus_listeners.append(record)
        return lambda: self.bus_listeners.remove(record)

    async def async_add_executor_job(self, func, *args):
        return await asyncio.to_thread(func, *args)

    def async_create_background_task(self, coro, name):
        return asyncio.create_task(coro, name=name)


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        identity = lambda *args, **kwargs: lambda value: value
        vol = module(
            "voluptuous",
            Required=lambda key, **kwargs: key,
            Optional=lambda key, **kwargs: key,
            Schema=identity, All=identity, Coerce=identity, Range=identity,
            In=identity, Length=identity, Match=identity, Invalid=ValueError,
        )
        ha = module("homeassistant")
        components = module("homeassistant.components")
        panel_custom = module(
            "homeassistant.components.panel_custom",
            async_register_panel=AsyncMock(),
        )
        helpers = module("homeassistant.helpers")
        websocket_api = module(
            "homeassistant.components.websocket_api",
            require_admin=lambda func: func,
            websocket_command=lambda schema: lambda func: func,
            async_response=lambda func: func,
            async_register_command=lambda *args: None,
        )
        config_validation = module(
            "homeassistant.helpers.config_validation",
            string=str, boolean=bool, config_entry_only_config_schema=identity,
        )
        modules = {
            "voluptuous": vol,
            "homeassistant": ha,
            "homeassistant.components": components,
            "homeassistant.components.websocket_api": websocket_api,
            "homeassistant.components.panel_custom": panel_custom,
            "homeassistant.components.http": module(
                "homeassistant.components.http",
                StaticPathConfig=lambda url_path, path, cache_headers: types.SimpleNamespace(
                    url_path=url_path, path=path, cache_headers=cache_headers
                ),
            ),
            "homeassistant.config_entries": module("homeassistant.config_entries", ConfigEntry=object),
            "homeassistant.core": module(
                "homeassistant.core", HomeAssistant=object, ServiceCall=object,
                callback=lambda func: func,
            ),
            "homeassistant.exceptions": module("homeassistant.exceptions", HomeAssistantError=FakeError),
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.config_validation": config_validation,
            "homeassistant.helpers.event": module(
                "homeassistant.helpers.event",
                async_track_state_change_event=lambda hass, entities, callback: hass.listen_state(entities, callback),
                async_track_time_interval=lambda *args: lambda: None,
            ),
            "homeassistant.helpers.storage": module(
                "homeassistant.helpers.storage",
                Store=lambda *args: types.SimpleNamespace(
                    async_load=AsyncMock(return_value=None), async_save=AsyncMock()
                ),
            ),
            "homeassistant.helpers.typing": module("homeassistant.helpers.typing", ConfigType=dict),
            "homeassistant.util": module("homeassistant.util"),
            "homeassistant.util.dt": module("homeassistant.util.dt"),
        }
        modules["homeassistant.util.dt"].now = lambda: datetime(2026, 12, 31)
        self.modules = patch.dict(sys.modules, modules)
        self.modules.start()
        spec = importlib.util.spec_from_file_location(
            "test_divoom_orchestrator", PACKAGE / "__init__.py",
            submodule_search_locations=[str(PACKAGE)],
        )
        self.integration = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.integration
        spec.loader.exec_module(self.integration)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "pixelart" / "rain").mkdir(parents=True)
        (self.root / "pixelart" / "rain" / "one.gif").write_bytes(b"test")
        self.hass = FakeHass(self.root)
        await self.integration.async_setup(self.hass, {})
        await self.integration.async_setup_entry(self.hass, object())
        self.panel_custom = panel_custom

    async def asyncTearDown(self):
        await self.integration.async_unload_entry(self.hass, object())
        self.temp.cleanup()
        self.modules.stop()
        sys.modules.pop("test_divoom_orchestrator", None)
        sys.modules.pop("test_divoom_orchestrator.playlist", None)
        sys.modules.pop("test_divoom_orchestrator.panel", None)
        sys.modules.pop("test_divoom_orchestrator.brightness", None)
        sys.modules.pop("test_divoom_orchestrator.brightness_ha", None)
        sys.modules.pop("test_divoom_orchestrator.playlist_ha", None)
        sys.modules.pop("test_divoom_orchestrator.events_ha", None)
        sys.modules.pop("test_divoom_orchestrator.gif_preview", None)
        sys.modules.pop("test_divoom_orchestrator.rotation_ha", None)
        sys.modules.pop("test_divoom_orchestrator.text_ha", None)

    async def start(self, **overrides):
        data = {"device": "divoom_pixoo", "folder": "rain", "duration": 30, "order": "alphabetical"}
        data.update(overrides)
        call = types.SimpleNamespace(data=data)
        await self.hass.services.handlers["divoom_orchestrator", "start"](call)

    async def test_actions_forward_relative_path_and_stop(self):
        await self.start()
        await asyncio.sleep(0)
        self.assertEqual(
            self.hass.services.calls[0],
            ("divoom", "image", {"device": "divoom_pixoo", "file": "rain/one.gif"}),
        )
        await self.hass.services.handlers["divoom_orchestrator", "stop"](types.SimpleNamespace(data={}))
        self.assertEqual(len(self.hass.services.calls), 1)

    async def test_rotation_cycle_snapshots_start_and_active_dates(self):
        data = self.hass.data["divoom_orchestrator"]
        rotation = data["rotation"]
        events = data["events"]
        data["brightness"].config["device"] = "pixoo"
        start = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 0.1},
        ], "date_events": True, "error_seconds": 2}
        events.events = {
            "Silvester": {"kind": "date", "enabled": True, "folder": "rain",
                          "steps": [{"file": "rain/one.gif", "mode": "seconds", "value": 0.2}],
                          "schedule": {"mode": "annual", "start": "12-31", "end": "01-01"}},
            "Aus": {"kind": "date", "enabled": False},
        }
        await rotation.save(start, ["rain/one.gif"])
        self.assertTrue(data["controller"].running)
        await asyncio.sleep(0)
        self.assertEqual(list(rotation._cycle.values()),
                         [("rain/one.gif", 0.1), ("rain/one.gif", 0.2)])
        events.events.clear()
        self.assertEqual(len(rotation._cycle), 2)
        await rotation.stop()
        await rotation.save(start, ["rain/one.gif"])
        self.assertFalse(data["controller"].running)
        await rotation.start()
        self.assertEqual(len(rotation._cycle), 1)
        await rotation.stop()

    async def test_rotation_transfer_retry_can_be_stopped(self):
        data = self.hass.data["divoom_orchestrator"]
        data["brightness"].config["device"] = "pixoo"
        self.hass.services.image_error = FakeError("offline")
        await data["rotation"].save({"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1},
        ], "date_events": False, "error_seconds": 2}, ["rain/one.gif"])
        for _ in range(10):
            await asyncio.sleep(0)
            if any(call[0] == "persistent_notification" for call in self.hass.services.calls):
                break
        self.assertTrue(data["controller"].running)
        await asyncio.wait_for(data["rotation"].stop(), timeout=1)

    async def test_weather_follows_order_and_avoids_immediate_repeat(self):
        data = self.hass.data["divoom_orchestrator"]
        rotation = data["rotation"]
        weather_dir = self.root / "pixelart" / "wetter" / "sunny" / "tag"
        weather_dir.mkdir(parents=True)
        for name in ("a.gif", "b.gif"):
            (weather_dir / name).write_bytes(b"test")
        self.hass.states.get = {
            "weather.home": types.SimpleNamespace(state="sunny"),
            "sun.sun": types.SimpleNamespace(state="above_horizon"),
        }.get
        rotation.config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1},
        ], "date_events": True, "error_seconds": 2, "blocks": ["weather", "date"],
            "weather": {"entity": "weather.home", "seconds": 4}}
        data["events"].events = {"day": {"kind": "date", "enabled": True,
            "folder": "rain", "steps": [{"file": "rain/one.gif", "mode": "seconds", "value": 3}],
            "schedule": {"mode": "annual", "start": "12-31", "end": "01-01"}}}
        await rotation._sequence()
        cycle = list(rotation._cycle.values())
        self.assertEqual(cycle[0], ("rain/one.gif", 1))
        self.assertEqual(cycle[2], ("rain/one.gif", 3))
        self.assertTrue(cycle[1][0].startswith("wetter/sunny/tag/"))
        await rotation._sequence()
        self.assertNotEqual(cycle[1], list(rotation._cycle.values())[1])

    async def test_trigger_subscriptions_require_transition_and_are_replaced(self):
        store = self.hass.data["divoom_orchestrator"]["events"]
        store.play_event = AsyncMock()
        event = {"kind": "trigger", "enabled": True, "folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1},
        ], "trigger": {"type": "state", "entity_id": "binary_sensor.door", "to": "on"}}
        await store.save("Door", event, ["rain/one.gif"])
        state_callback = next(cb for entities, cb in self.hass.state_listeners if entities == ["binary_sensor.door"])
        state = lambda value: types.SimpleNamespace(state=value)
        state_callback(types.SimpleNamespace(data={"old_state": None, "new_state": state("on")}))
        state_callback(types.SimpleNamespace(data={"old_state": state("on"), "new_state": state("on")}))
        await asyncio.sleep(0)
        store.play_event.assert_not_awaited()
        state_callback(types.SimpleNamespace(data={"old_state": state("off"), "new_state": state("on")}))
        await asyncio.sleep(0)
        store.play_event.assert_awaited_once_with("Door", automatic=True)
        event["trigger"] = {"type": "event", "event_type": "doorbell"}
        await store.save("Door", event, ["rain/one.gif"])
        self.assertFalse(any(entities == ["binary_sensor.door"] for entities, cb in self.hass.state_listeners))
        self.assertEqual(self.hass.bus_listeners[0][0], "doorbell")
        self.hass.bus_listeners[0][1](None)
        await asyncio.sleep(0)
        self.assertEqual(store.play_event.await_count, 2)
        await store.delete("Door")
        self.assertEqual(self.hass.bus_listeners, [])

    async def test_weather_failure_displays_error_image_and_notifies(self):
        data = self.hass.data["divoom_orchestrator"]
        rotation = data["rotation"]
        errors = self.root / "pixelart" / "fehler"
        errors.mkdir()
        (errors / "wetter.gif").write_bytes(b"test")
        rotation.config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1},
        ], "date_events": False, "error_seconds": 2, "blocks": ["weather"],
            "weather": {"entity": "weather.home", "seconds": 4}}
        await rotation._sequence()
        self.assertEqual(list(rotation._cycle.values())[-1], ("fehler/wetter.gif", 2))
        self.assertTrue(any("Weather unavailable" in call[2].get("message", "")
                            for call in self.hass.services.calls))

    def text_settings(self, **overrides):
        settings = {"name": "Spruch", "source": "list", "text": "", "entity": "",
                    "attribute": "", "lines": ["Erster", "Zweiter"], "list_version": "v1",
                    "selection": "call_order", "foreground": [255, 0, 0],
                    "background": [0, 0, 0], "size": 8, "time": 100,
                    "duration_mode": "seconds", "duration": 0.03}
        settings.update(overrides)
        return settings

    async def test_text_loop_duration_matches_pixoo_measurements(self):
        text_module = sys.modules["test_divoom_orchestrator.text_ha"]
        settings = self.text_settings(size=10, time=100, duration_mode="loops", duration=1)
        for text, expected in (("TEST", 4.9), ("TESTTESTTEST", 5.1), ("Tiiiiiiiiiii", 6.3)):
            with self.subTest(text=text):
                self.assertAlmostEqual(text_module.duration(settings, text), expected)
        settings["time"] = 200
        self.assertAlmostEqual(text_module.duration(settings, "TESTTESTTEST"), 9.7)
        settings["duration"] = 2
        self.assertAlmostEqual(text_module.duration(settings, "TESTTESTTEST"), 18.9)
        settings["duration_mode"] = "seconds"
        settings["duration"] = 3
        self.assertEqual(text_module.duration(settings, "TEST"), 3)

    async def test_text_loop_duration_checks_limit_and_long_text(self):
        text_module = sys.modules["test_divoom_orchestrator.text_ha"]
        settings = self.text_settings(size=10, time=100, duration_mode="loops", duration=1)
        with patch.object(text_module.ImageFont, "load_default") as font:
            with patch.object(text_module.ImageDraw.ImageDraw, "textbbox", return_value=(0, 0, 221, 10)):
                self.assertAlmostEqual(text_module.duration(settings, "long"), 6.5)
            font.assert_called_once_with(10)
        settings["time"] = 65535
        settings["duration"] = 3600
        with self.assertRaisesRegex(ValueError, "exceeds one hour"):
            text_module.duration(settings, "TEST")

    async def test_text_selection_persists_daily_and_reupload_resets(self):
        texts = self.hass.data["divoom_orchestrator"]["texts"]
        settings = self.text_settings(selection="daily_order")
        text, selection = await texts.select("text:one", settings)
        self.assertEqual(text, "Erster")
        await texts.commit("text:one", selection)
        self.assertEqual((await texts.select("text:one", settings))[0], "Erster")
        saved = dict(texts.progress)
        restored = type(texts)(self.hass)
        restored.store.async_load = AsyncMock(return_value=saved)
        await restored.load()
        self.assertEqual((await restored.select("text:one", settings))[0], "Erster")
        saved["text:one"]["day"] = "2026-12-30"
        self.assertEqual((await restored.select("text:one", settings))[0], "Zweiter")
        settings["list_version"] = "v2"
        self.assertEqual((await restored.select("text:one", settings))[0], "Erster")

    async def test_rotation_text_schema_with_real_voluptuous(self):
        text_spec = importlib.util.spec_from_file_location(
            "test_divoom_orchestrator.actual_text_schema", PACKAGE / "text_ha.py"
        )
        actual_text = importlib.util.module_from_spec(text_spec)
        rotation_spec = importlib.util.spec_from_file_location(
            "test_divoom_orchestrator.actual_rotation_schema", PACKAGE / "rotation_ha.py"
        )
        actual_rotation = importlib.util.module_from_spec(rotation_spec)
        with patch.dict(sys.modules, {"voluptuous": real_vol}):
            text_spec.loader.exec_module(actual_text)
            with patch.dict(sys.modules, {"test_divoom_orchestrator.text_ha": actual_text}):
                rotation_spec.loader.exec_module(actual_rotation)
        config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1},
        ], "date_events": False, "error_seconds": 2, "blocks": ["text:one"],
            "texts": {"text:one": self.text_settings(source="fixed", text="Hallo")}}
        parsed = actual_rotation.SCHEMA(config)
        self.assertEqual(parsed["texts"]["text:one"]["foreground"], [255, 0, 0])
        config["texts"]["text:one"]["foreground"] = [256, 1, 2]
        with self.assertRaises(real_vol.Invalid):
            actual_rotation.SCHEMA(config)

    async def test_text_selection_handles_entity_and_bad_values(self):
        texts = self.hass.data["divoom_orchestrator"]["texts"]
        self.hass.states.get = lambda entity: types.SimpleNamespace(
            state="ready", attributes={"temperature": 21, "complex": [1, 2]}
        )
        settings = self.text_settings(source="entity", entity="sensor.home", attribute="temperature")
        self.assertEqual((await texts.select("text:one", settings))[0], "21")
        settings["attribute"] = "complex"
        with self.assertRaisesRegex(ValueError, "simple scalar"):
            await texts.select("text:one", settings)
        settings.update(source="fixed", text="unavailable")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            await texts.select("text:one", settings)

    async def test_text_random_modes_and_per_call_progress(self):
        texts = self.hass.data["divoom_orchestrator"]["texts"]
        module = sys.modules["test_divoom_orchestrator.text_ha"]
        settings = self.text_settings(selection="daily_random")
        with patch.object(module.random, "randrange", side_effect=[1, 0]) as random_index:
            text, selected = await texts.select("text:one", settings)
            self.assertEqual(text, "Zweiter")
            await texts.commit("text:one", selected)
            self.assertEqual((await texts.select("text:one", settings))[0], "Zweiter")
            self.assertEqual(random_index.call_count, 1)
            settings["selection"] = "call_random"
            self.assertEqual((await texts.select("text:one", settings))[0], "Erster")
        settings["selection"] = "call_order"
        text, selected = await texts.select("text:two", settings)
        await texts.commit("text:two", selected)
        self.assertEqual((await texts.select("text:two", settings))[0], "Zweiter")

    async def test_failed_text_transfer_does_not_advance_list(self):
        data = self.hass.data["divoom_orchestrator"]
        data["brightness"].config["device"] = "pixoo"
        original_call = self.hass.services.async_call

        async def fail_text(domain, name, payload, blocking=False):
            if domain == "divoom" and name == "text":
                raise FakeError("offline")
            await original_call(domain, name, payload, blocking=blocking)

        self.hass.services.async_call = fail_text
        config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 0.01},
        ], "date_events": False, "error_seconds": 1, "blocks": ["text:one"],
            "texts": {"text:one": self.text_settings()}}
        await data["rotation"].save(config, ["rain/one.gif"])
        for _ in range(50):
            await asyncio.sleep(0.01)
            if "transfer" in data["rotation"]._reported:
                break
        self.assertNotIn("text:one", data["texts"].progress)
        await asyncio.wait_for(data["rotation"].stop(), 1)

    async def test_event_interrupts_text_and_rotation_resumes_next_block(self):
        data = self.hass.data["divoom_orchestrator"]
        data["brightness"].config.update({"device": "pixoo", "enabled": True})
        data["brightness"].controller.refresh = AsyncMock()
        config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 0.01},
        ], "date_events": True, "error_seconds": 1, "blocks": ["text:one", "date"],
            "texts": {"text:one": self.text_settings(duration=30)}}
        data["events"].events["Day"] = {"kind": "date", "enabled": True, "folder": "rain",
            "steps": [{"file": "rain/one.gif", "mode": "seconds", "value": 30}],
            "schedule": {"mode": "annual", "start": "12-31", "end": "01-01"}}
        data["events"].events["Door"] = {"kind": "trigger", "enabled": True, "folder": "rain",
            "steps": [{"file": "rain/one.gif", "mode": "seconds", "value": 0.01}]}
        await data["rotation"].save(config, ["rain/one.gif"])
        for _ in range(50):
            await asyncio.sleep(0.01)
            if any(call[1] == "text" for call in self.hass.services.calls):
                break
        await data["events"].play_event("Door")
        for _ in range(50):
            await asyncio.sleep(0.01)
            images = [call for call in self.hass.services.calls if call[:2] == ("divoom", "image")]
            if len(images) >= 3:
                break
        self.assertEqual(len(images), 3)
        self.assertEqual(data["texts"].progress["text:one"]["index"], 0)
        self.assertEqual(len([call for call in self.hass.services.calls if call[1] == "text"]), 1)
        await data["rotation"].stop()

    async def test_text_rotation_sends_service_and_commits_after_playback(self):
        data = self.hass.data["divoom_orchestrator"]
        data["brightness"].config["device"] = "pixoo"
        config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 0.01},
        ], "date_events": False, "error_seconds": 0.01,
            "blocks": ["text:one"], "texts": {"text:one": self.text_settings()}}
        await data["rotation"].save(config, ["rain/one.gif"])
        for _ in range(50):
            await asyncio.sleep(0.01)
            if any(call[1] == "text" for call in self.hass.services.calls):
                break
        calls = [call for call in self.hass.services.calls if call[:2] == ("divoom", "text")]
        self.assertEqual(calls[0][2]["text"], "Erster        ")
        self.assertEqual(calls[0][2]["foreground_color"], [255, 0, 0])
        self.assertEqual(data["texts"].progress["text:one"]["index"], 0)
        await data["rotation"].stop()

    async def test_text_loop_duration_uses_padded_sent_text(self):
        data = self.hass.data["divoom_orchestrator"]
        data["brightness"].config["device"] = "pixoo"
        rotation_module = sys.modules["test_divoom_orchestrator.rotation_ha"]
        settings = self.text_settings(source="fixed", text="TEST", size=10,
                                      duration_mode="loops", duration=1)
        config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 0.01},
        ], "date_events": False, "error_seconds": 0.01,
            "blocks": ["text:one"], "texts": {"text:one": settings}}
        with patch.object(rotation_module, "text_duration", wraps=rotation_module.text_duration) as calculate:
            await data["rotation"].save(config, ["rain/one.gif"])
            for _ in range(50):
                await asyncio.sleep(0.01)
                if any(call[1] == "text" for call in self.hass.services.calls):
                    break
            calls = [call for call in self.hass.services.calls if call[:2] == ("divoom", "text")]
            self.assertTrue(calls)
            sent_text = calls[0][2]["text"]
            self.assertEqual(sent_text, "TEST        ")
            self.assertEqual(calculate.call_args.args[1], sent_text)
            self.assertNotEqual(rotation_module.text_duration(settings, sent_text),
                                rotation_module.text_duration(settings, "TEST"))
            await data["rotation"].stop()

    async def test_text_error_fallback_and_invalid_loop_config(self):
        data = self.hass.data["divoom_orchestrator"]
        data["brightness"].config["device"] = "pixoo"
        errors = self.root / "pixelart" / "fehler"
        errors.mkdir()
        (errors / "text.gif").write_bytes(b"test")
        config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 0.01},
        ], "date_events": False, "error_seconds": 0.02, "blocks": ["text:one"],
            "texts": {"text:one": self.text_settings(source="entity", entity="sensor.missing")}}
        await data["rotation"].save(config, ["rain/one.gif"])
        for _ in range(50):
            await asyncio.sleep(0.01)
            if any(call[2].get("file") == "fehler/text.gif" for call in self.hass.services.calls):
                break
        self.assertTrue(any(call[2].get("file") == "fehler/text.gif" for call in self.hass.services.calls))
        await data["rotation"].stop()
        config["texts"]["text:one"] = self.text_settings(duration_mode="loops", duration=1.5)
        with self.assertRaisesRegex(ValueError, "whole numbers"):
            await data["rotation"].save(config, ["rain/one.gif"])

    async def test_trigger_missing_gif_uses_error_image(self):
        data = self.hass.data["divoom_orchestrator"]
        data["brightness"].config.update({"device": "pixoo", "enabled": True})
        data["brightness"].controller.refresh = AsyncMock()
        errors = self.root / "pixelart" / "fehler"
        errors.mkdir()
        (errors / "trigger.gif").write_bytes(b"test")
        data["events"].events["Door"] = {"kind": "trigger", "folder": "rain",
            "steps": [{"file": "rain/missing.gif", "mode": "seconds", "value": 1}]}
        await data["events"].play_event("Door")
        await asyncio.sleep(0)
        self.assertIn(("divoom", "image", {"device": "pixoo", "file": "fehler/trigger.gif"}),
                      self.hass.services.calls)

    async def test_invalid_weather_or_trigger_configuration_is_rejected(self):
        rotation = self.hass.data["divoom_orchestrator"]["rotation"]
        config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1},
        ], "date_events": True, "error_seconds": 2, "blocks": ["weather"],
            "weather": {"entity": "sensor.home", "seconds": 4}}
        with self.assertRaisesRegex(ValueError, "weather entity"):
            await rotation.save(config, ["rain/one.gif"])
        store = self.hass.data["divoom_orchestrator"]["events"]
        event = {"folder": "rain", "steps": config["steps"],
                 "trigger": {"type": "state", "entity_id": "binary_sensor.door", "to": ""}}
        with self.assertRaisesRegex(ValueError, "target state"):
            await store.save("Door", event, ["rain/one.gif"])

    async def test_autostart_retries_unavailable_service_and_stop_cancels(self):
        data = self.hass.data["divoom_orchestrator"]
        rotation = data["rotation"]
        data["brightness"].config["device"] = "pixoo"
        rotation.config = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1},
        ], "date_events": False, "error_seconds": 2}
        self.hass.services.has_service = lambda domain, name: False
        await rotation.auto_start()
        self.assertIsNotNone(rotation._startup_task)
        await rotation.stop()
        self.assertIsNone(rotation._startup_task)
        self.assertTrue(rotation.manual_stop)
        rotation.manual_stop = False
        self.hass.services.has_service = lambda domain, name: (domain, name) == ("divoom", "image")
        rotation_ha = sys.modules["test_divoom_orchestrator.rotation_ha"]
        with patch.object(rotation_ha.asyncio, "sleep", new=AsyncMock()):
            await rotation._retry_startup()
        self.assertTrue(data["controller"].running)
        await rotation.stop()

    async def test_invalid_folder_fails_start(self):
        with self.assertRaisesRegex(FakeError, "Cannot start"):
            await self.start(folder="missing")

    async def test_image_error_creates_notification(self):
        self.hass.services.image_error = FakeError("offline")
        await self.start()
        for _ in range(10):
            await asyncio.sleep(0)
            if len(self.hass.services.calls) > 1:
                break
        self.assertEqual(self.hass.services.calls[-1][:2], ("persistent_notification", "create"))
        self.assertIn("offline", self.hass.services.calls[-1][2]["message"])

    async def test_unloaded_integration_rejects_start(self):
        await self.integration.async_unload_entry(self.hass, object())
        with self.assertRaisesRegex(FakeError, "not configured"):
            await self.start()

    async def test_running_playlist_rejects_second_start(self):
        await self.start()
        with self.assertRaisesRegex(FakeError, "already running"):
            await self.start()

    async def test_no_divoom_service_fails_explicitly(self):
        self.hass.services.has_service = lambda domain, name: False
        with self.assertRaisesRegex(FakeError, "not available"):
            await self.start()

    async def test_panel_registration(self):
        self.hass.http.async_register_static_paths.assert_awaited_once()
        static = self.hass.http.async_register_static_paths.await_args.args[0][0]
        self.assertEqual(static.url_path, "/divoom-orchestrator-static/panel.js")
        self.assertTrue(Path(static.path).is_file())
        self.panel_custom.async_register_panel.assert_awaited_once()
        options = self.panel_custom.async_register_panel.await_args.kwargs
        manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(options["module_url"], f"{static.url_path}?v={manifest['version']}")
        self.assertEqual(options["webcomponent_name"], "divoom-orchestrator-panel")
        self.assertTrue(options["require_admin"])

    async def test_brightness_configuration_persists_and_disabled_is_idle(self):
        runtime = self.hass.data["divoom_orchestrator"]["brightness"]
        config = dict(runtime.config)
        config.update({"device": "pixoo", "night": 0})
        await runtime.configure(types.MappingProxyType(config))
        runtime.store.async_save.assert_awaited_once_with(config)
        self.assertEqual(runtime.config["night"], 0)
        await asyncio.sleep(0)
        self.assertFalse(any(call[0] == "divoom" for call in self.hass.services.calls))

    async def test_brightness_uses_sun_and_motion_and_calls_device(self):
        runtime = self.hass.data["divoom_orchestrator"]["brightness"]
        states = {
            "sun.sun": types.SimpleNamespace(
                state="below_horizon", attributes={"elevation": -15.0, "rising": False}
            ),
            "binary_sensor.motion": types.SimpleNamespace(state="on"),
        }
        self.hass.states.get = states.get
        brightness_ha = sys.modules["test_divoom_orchestrator.brightness_ha"]
        from datetime import datetime
        brightness_ha.dt_util.now = lambda: datetime(2026, 11, 21, 20, 0)
        config = dict(runtime.config)
        config.update({"enabled": True, "device": "pixoo", "motion": "binary_sensor.motion"})
        await runtime.configure(config)
        await runtime.controller.refresh()
        self.assertIn(("divoom", "on", {"device": "pixoo"}), self.hass.services.calls)
        self.assertIn(("divoom", "brightness", {"device": "pixoo", "brightness": 100}), self.hass.services.calls)
        self.assertEqual(runtime._schedule(), 10)

    async def test_per_file_durations_save_scan_and_preserve_other_folders(self):
        runtime = self.hass.data["divoom_orchestrator"]["durations"]
        runtime.values = {"other/file.gif": 22.0}
        await runtime.save("rain", {"rain/one.gif": 5.0}, ["rain/one.gif"])
        self.assertEqual(runtime.values, {"other/file.gif": 22.0, "rain/one.gif": 5.0})
        runtime.store.async_save.assert_awaited_once_with(runtime.values)
        with self.assertRaisesRegex(FakeError, "GIF list changed"):
            await runtime.save("rain", {"../outside.gif": 4.0}, ["rain/one.gif"])
        with self.assertRaisesRegex(FakeError, "GIF list changed"):
            await runtime.save("rain", {}, [])
        await runtime.save("rain", {}, ["rain/one.gif"])
        self.assertEqual(runtime.values, {"other/file.gif": 22.0})

    async def test_individual_playlist_uses_saved_durations(self):
        runtime = self.hass.data["divoom_orchestrator"]["durations"]
        await runtime.save("rain", {"rain/one.gif": 3.0}, ["rain/one.gif"])
        await self.start(individual_durations=True)
        await asyncio.sleep(0)
        self.assertEqual(self.hass.services.calls[0],
                         ("divoom", "image", {"device": "divoom_pixoo", "file": "rain/one.gif"}))

    async def test_preview_websocket_reports_valid_data_and_rejects_escape(self):
        playlist_ha = sys.modules["test_divoom_orchestrator.playlist_ha"]
        image = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(image, format="GIF")
        (self.root / "pixelart" / "rain" / "one.gif").write_bytes(image.getvalue())
        connection = types.SimpleNamespace(send_result=unittest.mock.Mock(), send_error=unittest.mock.Mock())
        await playlist_ha.websocket_gif_preview(self.hass, connection, {
            "id": 1, "folder": "rain", "file": "rain/one.gif",
        })
        self.assertIsNone(connection.send_result.call_args.args[1]["cycle_seconds"])
        self.assertTrue(connection.send_result.call_args.args[1]["data"])
        await playlist_ha.websocket_gif_preview(self.hass, connection, {
            "id": 2, "folder": "rain", "file": "../outside.gif",
        })
        self.assertEqual(connection.send_error.call_args.args[:2], (2, "preview_failed"))

    async def test_event_storage_is_per_event_and_requires_current_file_list(self):
        store = self.hass.data["divoom_orchestrator"]["events"]
        event = {"device": "pixoo", "folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 2.0},
        ]}
        await store.save("Klingel", event, ["rain/one.gif"])
        other = {"device": "pixoo", "folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 4.0},
        ]}
        await store.save("Bewegung", other, ["rain/one.gif"])
        self.assertEqual(store.events["Klingel"]["steps"][0]["value"], 2.0)
        self.assertEqual(store.events["Bewegung"]["steps"][0]["value"], 4.0)
        with self.assertRaisesRegex(ValueError, "GIF list changed"):
            await store.save("Klingel", event, [])
        await store.delete("Klingel")
        self.assertEqual(list(store.events), ["Bewegung"])

    async def test_date_event_requires_valid_schedule_and_preserves_it(self):
        store = self.hass.data["divoom_orchestrator"]["events"]
        event = {"kind": "date", "enabled": True, "folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 2.0},
        ]}
        with self.assertRaisesRegex(ValueError, "schedule is required"):
            await store.save("Weihnachten", event, ["rain/one.gif"])
        event["schedule"] = {"mode": "annual", "start": "12-20", "end": "01-06"}
        await store.save("Weihnachten", event, ["rain/one.gif"])
        self.assertEqual(store.events["Weihnachten"]["schedule"], event["schedule"])
        event["schedule"] = {"mode": "once", "start": "2027-01-02", "end": "2027-01-01"}
        with self.assertRaisesRegex(ValueError, "End date"):
            await store.save("Weihnachten", event, ["rain/one.gif"])

    async def test_event_loop_duration_uses_gif_frame_times(self):
        output = io.BytesIO()
        first = Image.new("RGB", (2, 2), "red")
        second = Image.new("RGB", (2, 2), "blue")
        first.save(output, format="GIF", save_all=True, append_images=[second],
                   duration=[100, 200], loop=0)
        (self.root / "pixelart" / "rain" / "one.gif").write_bytes(output.getvalue())
        store = self.hass.data["divoom_orchestrator"]["events"]
        event = {"device": "pixoo", "folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "loops", "value": 3.0},
        ]}
        result = await store.prepare(event)
        self.assertAlmostEqual(result[0][1], 0.9)
        event["steps"][0]["value"] = 1.5
        with self.assertRaisesRegex(ValueError, "whole number"):
            await store.prepare(event)
        first.save(output := io.BytesIO(), format="GIF")
        (self.root / "pixelart" / "rain" / "one.gif").write_bytes(output.getvalue())
        event["steps"][0]["value"] = 1.0
        with self.assertRaisesRegex(ValueError, "no usable loop duration"):
            await store.prepare(event)

    async def test_event_schema_uses_real_voluptuous_and_rejects_bad_values(self):
        spec = importlib.util.spec_from_file_location(
            "test_divoom_orchestrator.actual_event_schema", PACKAGE / "events_ha.py"
        )
        actual = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"voluptuous": real_vol}):
            spec.loader.exec_module(actual)
        event = {"device": "pixoo", "folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "loops", "value": 3},
        ]}
        self.assertEqual(actual.EVENT_SCHEMA(event)["steps"][0]["value"], 3.0)
        self.assertEqual(actual.EVENT_SCHEMA(event)["kind"], "trigger")
        event["trigger"] = {"type": "state", "entity_id": "binary_sensor.door", "to": "on"}
        self.assertEqual(actual.EVENT_SCHEMA(event)["trigger"]["to"], "on")
        event["kind"] = "date"
        self.assertEqual(actual.EVENT_SCHEMA(event)["kind"], "date")
        event["enabled"] = False
        event["schedule"] = {"mode": "annual", "start": "12-20", "end": "01-06"}
        parsed = actual.EVENT_SCHEMA(event)
        self.assertFalse(parsed["enabled"])
        self.assertEqual(parsed["schedule"]["end"], "01-06")
        event["kind"] = "invalid"
        with self.assertRaises(real_vol.Invalid):
            actual.EVENT_SCHEMA(event)
        event["kind"] = "date"
        for value in (0, -1, float("nan"), float("inf"), 3601):
            event["steps"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(real_vol.Invalid):
                actual.EVENT_SCHEMA(event)

    async def test_event_websocket_test_plays_saved_steps_once(self):
        store = self.hass.data["divoom_orchestrator"]["events"]
        brightness = self.hass.data["divoom_orchestrator"]["brightness"]
        brightness.config["device"] = "global_pixoo"
        brightness.config["enabled"] = True
        brightness.controller.refresh = AsyncMock()
        brightness.controller.event_started = unittest.mock.Mock()
        brightness.controller.event_finished = unittest.mock.Mock()
        event = {"device": "pixoo", "folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 0.01},
        ]}
        await store.save("Klingel", event, ["rain/one.gif"])
        handler = sys.modules["test_divoom_orchestrator.events_ha"].websocket_test
        connection = types.SimpleNamespace(send_result=unittest.mock.Mock(), send_error=unittest.mock.Mock())
        await handler(self.hass, connection, {"id": 2, "name": "Klingel"})
        connection.send_result.assert_called_once_with(2)
        await asyncio.sleep(0.05)
        self.assertEqual(self.hass.services.calls, [
            ("divoom", "image", {"device": "global_pixoo", "file": "rain/one.gif"})
        ])
        brightness.controller.event_started.assert_called_once()
        brightness.controller.event_finished.assert_called_once()

    async def test_trigger_test_requires_brightness_enabled(self):
        store = self.hass.data["divoom_orchestrator"]["events"]
        self.hass.data["divoom_orchestrator"]["brightness"].config["device"] = "pixoo"
        event = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1.0},
        ]}
        await store.save("Klingel", event, ["rain/one.gif"])
        handler = sys.modules["test_divoom_orchestrator.events_ha"].websocket_test
        connection = types.SimpleNamespace(send_result=unittest.mock.Mock(), send_error=unittest.mock.Mock())
        await handler(self.hass, connection, {"id": 4, "name": "Klingel"})
        self.assertIn("brightness automation", connection.send_error.call_args.args[2])

    async def test_event_test_requires_global_device(self):
        store = self.hass.data["divoom_orchestrator"]["events"]
        event = {"folder": "rain", "steps": [
            {"file": "rain/one.gif", "mode": "seconds", "value": 1.0},
        ]}
        await store.save("Klingel", event, ["rain/one.gif"])
        handler = sys.modules["test_divoom_orchestrator.events_ha"].websocket_test
        connection = types.SimpleNamespace(send_result=unittest.mock.Mock(), send_error=unittest.mock.Mock())
        await handler(self.hass, connection, {"id": 3, "name": "Klingel"})
        self.assertIn("device in settings", connection.send_error.call_args.args[2])
        self.assertEqual(self.hass.services.calls, [])

    async def test_brightness_ignores_duplicate_connected_event(self):
        runtime = self.hass.data["divoom_orchestrator"]["brightness"]
        runtime.config["connection"] = "sensor.bt"
        connected = types.SimpleNamespace(state="connected")
        runtime.controller.connected = unittest.mock.Mock()
        runtime._state_changed(types.SimpleNamespace(data={
            "entity_id": "sensor.bt", "old_state": connected, "new_state": connected,
        }))
        runtime.controller.connected.assert_not_called()
        runtime._state_changed(types.SimpleNamespace(data={
            "entity_id": "sensor.bt", "old_state": types.SimpleNamespace(state="disconnected"),
            "new_state": connected,
        }))
        runtime.controller.connected.assert_called_once()
