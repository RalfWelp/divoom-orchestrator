"""Contract tests with Home Assistant APIs simulated, not a real HA runtime."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch


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
            In=identity, Length=identity,
        )
        ha = module("homeassistant")
        components = module("homeassistant.components")
        panel_custom = module(
            "homeassistant.components.panel_custom",
            async_register_panel=AsyncMock(),
        )
        helpers = module("homeassistant.helpers")
        config_validation = module(
            "homeassistant.helpers.config_validation",
            string=str, config_entry_only_config_schema=identity,
        )
        modules = {
            "voluptuous": vol,
            "homeassistant": ha,
            "homeassistant.components": components,
            "homeassistant.components.panel_custom": panel_custom,
            "homeassistant.components.http": module(
                "homeassistant.components.http",
                StaticPathConfig=lambda url_path, path, cache_headers: types.SimpleNamespace(
                    url_path=url_path, path=path, cache_headers=cache_headers
                ),
            ),
            "homeassistant.config_entries": module("homeassistant.config_entries", ConfigEntry=object),
            "homeassistant.core": module("homeassistant.core", HomeAssistant=object, ServiceCall=object),
            "homeassistant.exceptions": module("homeassistant.exceptions", HomeAssistantError=FakeError),
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.config_validation": config_validation,
            "homeassistant.helpers.typing": module("homeassistant.helpers.typing", ConfigType=dict),
        }
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
        self.assertEqual(options["module_url"], static.url_path)
        self.assertEqual(options["webcomponent_name"], "divoom-orchestrator-panel")
        self.assertTrue(options["require_admin"])
