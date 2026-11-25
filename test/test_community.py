"""Focused tests for community API validation, GIF conversion and safe imports."""

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


PATH = Path(__file__).resolve().parents[1] / "custom_components" / "divoom_orchestrator" / "community.py"
spec = importlib.util.spec_from_file_location("community_tested", PATH)
community = importlib.util.module_from_spec(spec)
spec.loader.exec_module(community)


def record(gallery_id, **changes):
    result = {
        "GalleryId": gallery_id, "FileSize": 1, "PrivateFlag": 0, "HideFlag": 0,
        "IsDel": 0, "CopyrightFlag": 0, "FileName": "Test", "UserName": "Artist",
    }
    result.update(changes)
    return result


class CommunityTests(unittest.TestCase):
    @patch.object(community, "request")
    def test_search_filters_private_and_disables_restricted(self, request):
        request.return_value = {"FileList": [
            record(1), record(2, HideFlag=1), record(3, CopyrightFlag=1),
            record(4, CopyrightFlag=None),
        ]}
        results = community.search("cat", 2, 0)["works"]
        self.assertEqual([(r["id"], r["importable"]) for r in results],
                         [(1, True), (3, False), (4, False)])
        self.assertEqual(request.call_args.args[1]["StartNum"], 10)
        self.assertEqual(request.call_args.args[1]["FileSize"], 1)

    @patch.object(community, "build_opener")
    def test_empty_search_response_is_not_an_error(self, opener):
        response = opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b'{"ReturnCode":8,"ReturnMessage":"Get condition is not match","CurListNum":0,"FileList":[]}'
        self.assertEqual(community.search("no-results", 1, 1),
                         {"works": [], "has_more": False})
        response.read.return_value = b'{"ReturnCode":8,"ReturnMessage":"Other error","CurListNum":0,"FileList":[]}'
        with self.assertRaises(ValueError):
            community.search("no-results", 1, 1)

    @patch.object(community, "request")
    def test_hidden_results_do_not_end_pagination(self, request):
        request.return_value = {"FileList": [record(i + 1, HideFlag=1) for i in range(9)]}
        self.assertEqual(community.search("cat", 1, 1), {"works": [], "has_more": True})

    @patch.object(community, "request")
    def test_render_preserves_frames_and_timing(self, request):
        request.return_value = {
            "PicCount": 2, "Speed": 150, "xScreenCount": 1, "yScreenCount": 1,
            "FileData": [255, 0, 0] * 256 + [0, 0, 255] * 256,
        }
        with Image.open(io.BytesIO(community.render(1))) as image:
            self.assertEqual(image.size, (16, 16))
            self.assertEqual(image.n_frames, 2)
            self.assertEqual(image.info["duration"], 150)
            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (255, 0, 0))
            image.seek(1)
            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (0, 0, 255))

    @patch.object(community, "request")
    def test_render_rejects_bad_frames_and_dimensions(self, request):
        request.return_value = {
            "PicCount": 2, "Speed": 0, "xScreenCount": 1, "yScreenCount": 1,
            "FileData": [0] * 1536,
        }
        with self.assertRaises(ValueError):
            community.render(1)
        request.return_value.update(Speed=50, xScreenCount=2)
        with self.assertRaises(ValueError):
            community.render(1)
        request.return_value.update(xScreenCount=1, FileData=[0] * 1535)
        with self.assertRaises(ValueError):
            community.render(1)

    def test_save_confines_folder_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "pixelart"
            (root / "folder").mkdir(parents=True)
            self.assertEqual(community.save(root, "folder", 123, b"gif"), "folder/divoom-123.gif")
            with self.assertRaises(FileExistsError):
                community.save(root, "folder", 123, b"other")
            self.assertEqual((root / "folder" / "divoom-123.gif").read_bytes(), b"gif")
            with self.assertRaises(ValueError):
                community.save(root, "..", 123, b"gif")


if __name__ == "__main__":
    unittest.main()
