"""Tests for the brightness schedule and controller."""

import asyncio
from datetime import time
import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "custom_components" / "divoom_orchestrator" / "brightness.py"
spec = importlib.util.spec_from_file_location("brightness_test_module", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BrightnessController = module.BrightnessController
scheduled_brightness = module.scheduled_brightness


class ScheduleTests(unittest.TestCase):
    def test_schedule_boundaries(self):
        def level(now, elevation, rising):
            return scheduled_brightness(now, time(5), elevation, rising, 100, 50, 10)

        self.assertEqual(level(time(4, 59), 10, True), 10)
        self.assertEqual(level(time(5), -20, True), 50)
        self.assertEqual(level(time(5), 1, True), 100)
        self.assertEqual(level(time(7), 0, True), 100)
        self.assertEqual(level(time(18), -0.01, False), 50)
        self.assertEqual(level(time(19), -6, False), 50)
        self.assertEqual(level(time(19), -6.01, False), 10)
        self.assertEqual(level(time(23), -20, False), 10)


class BrightnessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 0.0
        self.level = 10
        self.calls = []
        self.errors = []

        async def send(action, value):
            self.calls.append((action, value))

        async def error(err):
            self.errors.append(str(err))

        async def sleep(seconds):
            pass

        self.controller = BrightnessController(
            lambda: self.level, send, error,
            clock=lambda: self.now, sleep=sleep,
        )

    async def test_motion_at_least_30_seconds_and_while_on(self):
        self.controller.motion_changed(True)
        await self.controller.refresh()
        self.assertEqual(self.calls, [("on", None), ("brightness", 100)])
        self.now = 20
        self.controller.motion_changed(False)
        self.assertEqual(self.controller.target(), 100)
        self.now = 30
        self.assertEqual(self.controller.target(), 10)
        await self.controller.refresh()
        self.assertEqual(self.calls[-4:], [
            ("brightness", 78), ("brightness", 55),
            ("brightness", 32), ("brightness", 10),
        ])
        self.now = 31
        self.controller.motion_changed(True)
        self.now = 300
        self.assertEqual(self.controller.target(), 100)
        self.controller.motion_changed(False)
        self.assertEqual(self.controller.target(), 10)

    async def test_event_overrides_test_and_expires_after_end_and_minimum(self):
        self.controller.test(20)
        self.controller.event_started()
        await self.controller.refresh()
        self.assertEqual(self.controller.target(), 100)
        self.now = 20
        self.controller.event_finished()
        self.assertEqual(self.controller.target(), 100)
        self.now = 30
        self.assertEqual(self.controller.target(), 10)
        self.now = 31
        self.controller.event_started()
        self.now = 100
        self.assertEqual(self.controller.target(), 100)
        self.controller.event_finished()
        self.assertEqual(self.controller.target(), 10)

    async def test_zero_wake_and_return(self):
        self.level = 0
        await self.controller.refresh()
        self.assertEqual(self.calls, [("off", None)])
        self.controller.motion_changed(True)
        await self.controller.refresh()
        self.assertEqual(self.calls[-2:], [("on", None), ("brightness", 100)])
        self.controller.motion_changed(False)
        self.now = 30
        await self.controller.refresh()
        self.assertEqual(self.calls[-1], ("off", None))

    async def test_test_override_expires_and_restores_current_schedule(self):
        self.controller.test(50)
        await self.controller.refresh()
        self.assertEqual(self.controller.target(), 50)
        self.level = 100
        self.now = 30
        await self.controller.refresh()
        self.assertEqual(self.calls[-1], ("brightness", 100))

    async def test_reconnect_resends_and_errors_are_not_silent(self):
        await self.controller.refresh()
        self.calls.clear()
        self.controller.connected()
        await self.controller.refresh()
        self.assertEqual(self.calls, [("on", None), ("brightness", 10)])

        async def fail(action, value):
            raise OSError("offline")

        self.controller._send = fail
        self.controller.connected()
        with self.assertRaisesRegex(OSError, "offline"):
            await self.controller.refresh()
        self.assertEqual(self.errors, ["offline"])

    async def test_retarget_during_command(self):
        gate = asyncio.Event()
        started = asyncio.Event()
        original_send = self.controller._send

        async def slow(action, value):
            if action == "on":
                started.set()
                await gate.wait()
            await original_send(action, value)

        self.controller._send = slow
        task = asyncio.create_task(self.controller.refresh())
        await started.wait()
        self.level = 0
        gate.set()
        await task
        self.assertEqual(self.calls[-1], ("off", None))


if __name__ == "__main__":
    unittest.main()
