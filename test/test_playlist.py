import asyncio
import importlib.util
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import AsyncMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "custom_components" / "divoom_playlist" / "playlist.py"
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


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def test_rescans_after_each_cycle(self):
        scan = AsyncMock(side_effect=[["a.gif", "b.gif"], ["new.gif"], asyncio.CancelledError()])
        show = AsyncMock()
        with patch.object(playlist.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await playlist.play(scan, show, 4)
        self.assertEqual([call.args[0] for call in show.await_args_list], ["a.gif", "b.gif", "new.gif"])
        self.assertEqual(sleep.await_count, 3)
        self.assertTrue(all(call.args == (4,) for call in sleep.await_args_list))

    async def test_empty_folder_and_send_errors_are_not_silent(self):
        with self.assertRaisesRegex(ValueError, "no GIF"):
            await playlist.play(AsyncMock(return_value=[]), AsyncMock(), 1)
        with self.assertRaisesRegex(RuntimeError, "send failed"):
            await playlist.play(AsyncMock(return_value=["a.gif"]), AsyncMock(side_effect=RuntimeError("send failed")), 1)

    async def test_nonpositive_duration_rejected(self):
        with self.assertRaises(ValueError):
            await playlist.play(AsyncMock(), AsyncMock(), 0)


if __name__ == "__main__":
    unittest.main()
