"""Tests for authenticated preview data preparation."""

import base64
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest

from PIL import Image


PACKAGE = Path(__file__).resolve().parents[1] / "custom_components" / "divoom_orchestrator"
package = types.ModuleType("preview_test_package")
package.__path__ = [str(PACKAGE)]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location(
    "preview_test_package.gif_preview", PACKAGE / "gif_preview.py"
)
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def gif(durations):
    images = [Image.new("RGB", (2, 2), color) for color in ("red", "blue")]
    output = io.BytesIO()
    images[0].save(
        output, format="GIF", save_all=True, append_images=images[1:],
        duration=durations, loop=0,
    )
    return output.getvalue()


class GifPreviewTests(unittest.TestCase):
    def test_preview_uses_real_frame_durations_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "event").mkdir()
            content = gif([120, 230])
            (root / "event" / "a.gif").write_bytes(content)
            result = preview.gif_preview(root, "event", "event/a.gif")
            self.assertEqual(base64.b64decode(result["data"]), content)
            self.assertAlmostEqual(result["cycle_seconds"], 0.35)

    def test_zero_frame_duration_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.gif").write_bytes(gif([0, 100]))
            self.assertIsNone(preview.gif_preview(root, ".", "a.gif")["cycle_seconds"])

    def test_invalid_images_and_preview_size_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bad.gif").write_bytes(b"not a GIF")
            with self.assertRaisesRegex(ValueError, "Cannot read GIF"):
                preview.gif_preview(root, ".", "bad.gif")
            (root / "bad.gif").write_bytes(b"x" * (preview.MAX_PREVIEW_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "2 MiB"):
                preview.gif_preview(root, ".", "bad.gif")

    def test_rejects_other_folders_and_parent_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one").mkdir()
            (root / "two").mkdir()
            (root / "two" / "a.gif").write_bytes(gif([100, 100]))
            with self.assertRaisesRegex(ValueError, "not in the selected folder"):
                preview.gif_preview(root, "one", "two/a.gif")
            with self.assertRaises(ValueError):
                preview.gif_preview(root, "..", "../a.gif")


if __name__ == "__main__":
    unittest.main()
