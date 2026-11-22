import asyncio
import importlib.util
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import AsyncMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "custom_components" / "divoom_orchestrator" / "playlist.py"
spec = importlib.util.spec_from_file_location("playlist", SCRIPT)
playlist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(playlist)


class ScanTests(unittest.TestCase):
    def test_selects_direct_gifs_sorted_relative_to_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "wetter" / "regen"
            folder.mkdir(parents=True)
            for name in ("b.GIF", "A.gif", "note.txt"):
                (folder / name).write_bytes(b"test")
            (folder / "nested").mkdir()
            (folder / "nested" / "other.gif").write_bytes(b"test")
            self.assertEqual(
                playlist.scan_gifs(root, "wetter/regen", False),
                ["wetter/regen/A.gif", "wetter/regen/b.GIF"],
            )

    def test_rejects_escape_and_missing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            root.mkdir()
            with self.assertRaises(ValueError):
                playlist.scan_gifs(root, "..", False)
            with self.assertRaises(FileNotFoundError):
                playlist.scan_gifs(root, "missing", False)

    def test_shuffle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("a.gif", "b.gif"):
                (root / name).write_bytes(b"test")
            with patch.object(random, "shuffle", side_effect=lambda values: values.reverse()):
                self.assertEqual(playlist.scan_gifs(root, ".", True), ["b.gif", "a.gif"])

    def test_scans_real_directory_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "old.gif").write_bytes(b"test")
            self.assertEqual(playlist.scan_gifs(root, ".", False), ["old.gif"])
            (root / "old.gif").unlink()
            (root / "new.gif").write_bytes(b"test")
            self.assertEqual(playlist.scan_gifs(root, ".", False), ["new.gif"])

    def test_empty_and_absolute_folder_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ("", str(root)):
                with self.subTest(folder=folder), self.assertRaises(ValueError):
                    playlist.scan_gifs(root, folder, False)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def test_higher_priority_interrupts_event_at_safe_point_and_discards_remaining(self):
        first_started = asyncio.Event()
        release = asyncio.Event()
        resumed = asyncio.Event()
        rotation_started = asyncio.Event()
        shown = []

        async def show(filename):
            shown.append(filename)
            if filename == "rotation-1.gif":
                rotation_started.set()
            if filename == "low-1.gif":
                first_started.set()
                await release.wait()
            if filename == "rotation-2.gif":
                resumed.set()

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        await controller.start(
            AsyncMock(return_value=["rotation-1.gif", "rotation-2.gif"]), show, 3600, device="pixoo"
        )
        await asyncio.wait_for(rotation_started.wait(), 1)
        await controller.start_event(
            [("low-1.gif", 10), ("low-2.gif", 10)], show, "pixoo", priority=3, name="motion"
        )
        await asyncio.wait_for(first_started.wait(), 1)
        with self.assertRaisesRegex(ValueError, "equal or higher"):
            await controller.start_event([("same.gif", 1)], show, "pixoo", priority=3, name="other")
        with self.assertRaisesRegex(ValueError, "equal or higher"):
            await controller.start_event([("repeat.gif", 1)], show, "pixoo", priority=1, name="motion")
        await controller.start_event([("door.gif", 0.01)], show, "pixoo", priority=2, name="door")
        release.set()
        await asyncio.wait_for(resumed.wait(), 1)
        await controller.stop()
        self.assertIn("door.gif", shown)
        self.assertNotIn("low-2.gif", shown)
        self.assertLess(shown.index("low-1.gif"), shown.index("door.gif"))
        self.assertLess(shown.index("door.gif"), shown.index("rotation-2.gif"))

    async def test_priority_interrupts_event_wait_without_waiting_for_timeout(self):
        started = asyncio.Event()
        high = asyncio.Event()

        async def show(filename):
            if filename == "low.gif":
                started.set()
            if filename == "high.gif":
                high.set()

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        await controller.start_event([("low.gif", 3600)], show, priority=3, name="low")
        await asyncio.wait_for(started.wait(), 1)
        await controller.start_event([("high.gif", 3600)], show, priority=1, name="high")
        await asyncio.wait_for(high.wait(), 1)
        await controller.stop()

    async def test_event_hooks_run_on_stop_and_on_failed_transfer(self):
        begun = asyncio.Event()
        finished = AsyncMock()
        reported = asyncio.Event()

        async def start():
            begun.set()

        async def error(err):
            reported.set()

        controller = playlist.PlaylistController(asyncio.create_task, error)
        await controller.start_event(
            [("a.gif", 3600)], AsyncMock(), on_start=start, on_finish=finished
        )
        await asyncio.wait_for(begun.wait(), 1)
        await controller.stop()
        finished.assert_awaited_once()
        finished.reset_mock()
        await controller.start_event(
            [("a.gif", 1)], AsyncMock(side_effect=OSError("offline")),
            on_start=start, on_finish=finished,
        )
        await asyncio.wait_for(reported.wait(), 1)
        finished.assert_awaited_once()
        await controller.stop()

    async def test_event_interrupts_rotation_and_resumes_with_next_gif(self):
        rotation_started = asyncio.Event()
        resumed = asyncio.Event()
        shown = []

        async def show(filename):
            shown.append(filename)
            if filename == "a.gif":
                rotation_started.set()
            if filename == "b.gif":
                resumed.set()

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        await controller.start(AsyncMock(return_value=["a.gif", "b.gif"]), show, 3600, device="pixoo")
        await asyncio.wait_for(rotation_started.wait(), 1)
        await controller.start_event([("event.gif", 0.01)], show, "pixoo")
        await asyncio.wait_for(resumed.wait(), 1)
        await controller.stop()
        self.assertEqual(shown, ["a.gif", "event.gif", "b.gif"])

    async def test_event_waits_for_transfer_and_rejects_retrigger_and_other_device(self):
        started = asyncio.Event()
        finish = asyncio.Event()
        shown = []

        async def show(filename):
            shown.append(filename)
            if filename == "a.gif":
                started.set()
                await finish.wait()

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        await controller.start(AsyncMock(return_value=["a.gif", "b.gif"]), show, 3600, device="pixoo")
        await started.wait()
        with self.assertRaisesRegex(ValueError, "same device"):
            await controller.start_event([("event.gif", 1)], show, "other")
        await controller.start_event([("event.gif", 3600)], show, "pixoo")
        with self.assertRaisesRegex(ValueError, "already running"):
            await controller.start_event([("event.gif", 1)], show, "pixoo")
        self.assertEqual(shown, ["a.gif"])
        finish.set()
        for _ in range(20):
            await asyncio.sleep(0)
            if len(shown) > 1:
                break
        self.assertEqual(shown, ["a.gif", "event.gif"])
        await asyncio.wait_for(controller.stop(), 1)

    async def test_standalone_event_runs_once(self):
        shown = []
        complete = asyncio.Event()

        async def show(filename):
            shown.append(filename)
            if len(shown) == 2:
                complete.set()

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        await controller.start_event([("a.gif", 0.01), ("b.gif", 0.01)], show)
        await asyncio.wait_for(complete.wait(), 1)
        await asyncio.sleep(0.03)
        self.assertEqual(shown, ["a.gif", "b.gif"])
        await controller.stop()

    async def test_rescans_after_each_cycle(self):
        scan = AsyncMock(side_effect=[["new.gif"], asyncio.CancelledError()])
        show = AsyncMock()
        async def timeout(waiter, *, timeout):
            waiter.close()
            raise TimeoutError

        with patch.object(playlist.asyncio, "wait_for", side_effect=timeout) as wait:
            with self.assertRaises(asyncio.CancelledError):
                await playlist.play(scan, show, 4, asyncio.Event(), ["a.gif", "b.gif"])
        self.assertEqual([call.args[0] for call in show.await_args_list], ["a.gif", "b.gif", "new.gif"])
        self.assertEqual(wait.call_count, 3)
        self.assertTrue(all(call.kwargs == {"timeout": 4} for call in wait.call_args_list))

    async def test_individual_times_and_skip_new_unconfigured_files(self):
        scan = AsyncMock(side_effect=[["b.gif", "new.gif", "a.gif"], asyncio.CancelledError()])
        show = AsyncMock()
        durations = {"a.gif": 3, "b.gif": 7}

        async def timeout(waiter, *, timeout):
            waiter.close()
            raise TimeoutError

        with patch.object(playlist.asyncio, "wait_for", side_effect=timeout) as wait:
            with self.assertRaises(asyncio.CancelledError):
                await playlist.play(
                    scan, show, 10, asyncio.Event(),
                    ["a.gif", "missing.gif", "b.gif"], durations.get,
                )
        self.assertEqual([call.args[0] for call in show.await_args_list],
                         ["a.gif", "b.gif", "b.gif", "a.gif"])
        self.assertEqual([call.kwargs["timeout"] for call in wait.call_args_list], [3, 7, 7, 3])

    async def test_manual_playlist_rejects_all_unconfigured(self):
        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        with self.assertRaisesRegex(ValueError, "configured duration"):
            await controller.start(AsyncMock(return_value=["new.gif"]), AsyncMock(), 10, {}.get)

    async def test_empty_folder_and_send_errors_are_not_silent(self):
        with self.assertRaisesRegex(ValueError, "no GIF"):
            await playlist.play(AsyncMock(), AsyncMock(), 1, asyncio.Event(), [])
        with self.assertRaisesRegex(RuntimeError, "send failed"):
            await playlist.play(AsyncMock(), AsyncMock(side_effect=RuntimeError("send failed")), 1, asyncio.Event(), ["a.gif"])

    async def test_nonpositive_duration_rejected(self):
        with self.assertRaises(ValueError):
            await playlist.play(AsyncMock(), AsyncMock(), 0, asyncio.Event(), ["a.gif"])

    async def test_controller_stop_waits_for_inflight_send(self):
        started = asyncio.Event()
        finish = asyncio.Event()
        shown = []

        async def show(filename):
            shown.append(filename)
            started.set()
            await finish.wait()

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        await controller.start(AsyncMock(return_value=["a.gif", "b.gif"]), show, 10)
        await started.wait()
        stop = asyncio.create_task(controller.stop())
        await asyncio.sleep(0)
        self.assertFalse(stop.done())
        finish.set()
        await stop
        self.assertEqual(shown, ["a.gif"])

    async def test_concurrent_starts_and_restart(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def scan():
            entered.set()
            await release.wait()
            return ["a.gif"]

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        first = asyncio.create_task(controller.start(scan, AsyncMock(), 100))
        await entered.wait()
        second = asyncio.create_task(controller.start(scan, AsyncMock(), 100))
        release.set()
        await first
        with self.assertRaisesRegex(ValueError, "already running"):
            await second
        await controller.stop()
        await controller.start(AsyncMock(return_value=["b.gif"]), AsyncMock(), 100)
        await controller.stop()

    async def test_stop_interrupts_wait(self):
        shown = asyncio.Event()

        async def show(filename):
            shown.set()

        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        await controller.start(AsyncMock(return_value=["a.gif", "b.gif"]), show, 3600)
        await shown.wait()
        await asyncio.wait_for(controller.stop(), timeout=1)

    async def test_background_failure_reported_and_restart_allowed(self):
        reported = asyncio.Event()
        errors = []

        async def on_error(err):
            errors.append(str(err))
            reported.set()

        controller = playlist.PlaylistController(asyncio.create_task, on_error)
        await controller.start(AsyncMock(return_value=["a.gif"]), AsyncMock(side_effect=OSError("offline")), 1)
        await reported.wait()
        self.assertEqual(errors, ["offline"])
        await controller.start(AsyncMock(return_value=["b.gif"]), AsyncMock(), 100)
        await controller.stop()

    async def test_initial_empty_folder_rejected(self):
        controller = playlist.PlaylistController(asyncio.create_task, AsyncMock())
        with self.assertRaisesRegex(ValueError, "no GIF"):
            await controller.start(AsyncMock(return_value=[]), AsyncMock(), 1)

    async def test_directory_becomes_empty_after_cycle(self):
        reported = asyncio.Event()
        errors = []

        async def on_error(err):
            errors.append(str(err))
            reported.set()

        async def timeout(waiter, *, timeout):
            waiter.close()
            raise TimeoutError

        controller = playlist.PlaylistController(asyncio.create_task, on_error)
        with patch.object(playlist.asyncio, "wait_for", side_effect=timeout):
            await controller.start(AsyncMock(side_effect=[["one.gif"], []]), AsyncMock(), 1)
            await reported.wait()
        self.assertIn("no GIF", errors[0])
        await controller.stop()


if __name__ == "__main__":
    unittest.main()
