"""Focused tests for community API validation, GIF conversion and safe imports."""

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from Crypto.Cipher import AES
from PIL import Image
from servoom.pixel_bean_decoder import BaseDecoder


PATH = Path(__file__).resolve().parents[1] / "custom_components" / "divoom_orchestrator" / "community.py"
spec = importlib.util.spec_from_file_location("community_tested", PATH)
community = importlib.util.module_from_spec(spec)
spec.loader.exec_module(community)


def record(gallery_id, **changes):
    result = {
        "GalleryId": gallery_id, "FileSize": 1, "PrivateFlag": 0, "HideFlag": 0,
        "IsDel": 0, "CopyrightFlag": 0, "FileName": "Test", "UserName": "Artist",
        "FileId": f"group1/test/{gallery_id}",
    }
    result.update(changes)
    return result


class CommunityTests(unittest.TestCase):
    @patch.object(community, "build_opener")
    def test_rate_limit_preserves_retry_after_and_defaults_when_absent(self, opener):
        opener.return_value.open.side_effect = HTTPError(
            "https://example.invalid", 429, "Too Many Requests", {"Retry-After": "17"}, None,
        )
        with self.assertRaises(community.RateLimited) as error:
            community.request("SearchGalleryV3", {})
        self.assertEqual(error.exception.retry_seconds, 17)
        opener.return_value.open.side_effect = HTTPError(
            "https://example.invalid", 429, "Too Many Requests", {}, None,
        )
        with self.assertRaises(community.RateLimited) as error:
            community.request("SearchGalleryV3", {})
        self.assertEqual(error.exception.retry_seconds, 60)

    @patch.object(community, "request")
    def test_search_filters_private_and_disables_restricted(self, request):
        request.return_value = {"FileList": [
            record(1), record(2, HideFlag=1), record(3, CopyrightFlag=1),
            record(4, CopyrightFlag=None),
        ]}
        results = community.search("cat", 1, 0)["works"]
        self.assertEqual([(r["id"], r["importable"]) for r in results],
                         [(1, True), (3, False), (4, False)])
        self.assertEqual(results[0]["file_id"], "group1/test/1")
        self.assertEqual(request.call_args.args[1]["StartNum"], 1)
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
        request.return_value = {"FileList": [record(i + 1, HideFlag=1) for i in range(community.PAGE_SIZE)]}
        self.assertEqual(community.search("cat", 1, 1), {"works": [], "has_more": True})

    @patch.object(community, "request")
    def test_pagination_requests_prefix_and_limits_anonymous_results(self, request):
        request.side_effect = lambda command, payload: {
            "FileList": [record(i + 1) for i in range(payload["EndNum"])]
        }
        second = community.search("cat", 2, 1)
        self.assertEqual([work["id"] for work in second["works"]], list(range(19, 37)))
        self.assertTrue(second["has_more"])
        self.assertEqual(request.call_args.args[1]["StartNum"], 1)
        self.assertEqual(request.call_args.args[1]["EndNum"], 36)
        last = community.search("cat", 6, 1)
        self.assertEqual([work["id"] for work in last["works"]], list(range(91, 101)))
        self.assertFalse(last["has_more"])
        with self.assertRaises(ValueError):
            community.search("cat", 7, 1)

    @patch.object(community, "request")
    def test_short_prefix_ends_pagination(self, request):
        request.return_value = {"FileList": [record(i + 1) for i in range(20)]}
        result = community.search("cat", 2, 1)
        self.assertEqual([work["id"] for work in result["works"]], [19, 20])
        self.assertFalse(result["has_more"])

    @patch.object(community, "read_response")
    def test_render_preserves_frames_and_timing(self, read_response):
        cipher = AES.new(BaseDecoder.AES_SECRET_KEY.encode(), AES.MODE_CBC, BaseDecoder.AES_IV)
        pixels = bytes([255, 0, 0] * 256 + [0, 0, 255] * 256)
        read_response.return_value = b"\x09\x00\x00\x96" + cipher.encrypt(pixels)
        with Image.open(io.BytesIO(community.render("group1/test/1"))) as image:
            self.assertEqual(image.size, (16, 16))
            self.assertEqual(image.n_frames, 2)
            self.assertEqual(image.info["duration"], 150)
            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (255, 0, 0))
            image.seek(1)
            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(read_response.call_args.args[0].full_url,
                         "https://f.divoom-gz.com/group1/test/1")

    @patch.object(community, "read_response")
    def test_render_accepts_single_frame(self, read_response):
        cipher = AES.new(BaseDecoder.AES_SECRET_KEY.encode(), AES.MODE_CBC, BaseDecoder.AES_IV)
        read_response.return_value = b"\x08" + cipher.encrypt(bytes([1, 2, 3] * 256))
        with Image.open(io.BytesIO(community.render("group1/test/1"))) as image:
            self.assertEqual(image.size, (16, 16))
            self.assertEqual(image.n_frames, 1)
            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (1, 2, 3))

    @patch.object(community, "read_response")
    def test_render_accepts_legacy_raw_rgb(self, read_response):
        read_response.return_value = b"\x03" + bytes([1, 2, 3] * 256)
        with Image.open(io.BytesIO(community.render("group1/test/1"))) as image:
            self.assertEqual(image.size, (16, 16))
            self.assertEqual(image.n_frames, 1)
            self.assertEqual(image.convert("RGB").getpixel((0, 0)), (1, 2, 3))
        read_response.return_value = b"\x03" + bytes(767)
        with self.assertRaises(ValueError):
            community.render("group1/test/1")

    @patch.object(community, "read_response")
    def test_render_rejects_invalid_paths_and_unbounded_files(self, read_response):
        for file_id in (None, "", "../private", "group1/../private", "//host/file",
                        "group1/file?x=1", "https://example.com/file"):
            with self.subTest(file_id=file_id), self.assertRaises(ValueError):
                community.render(file_id)
        read_response.assert_not_called()
        for data in (b"", b"\x09\x00\x00\x96" + bytes(768 * 101),
                     b"\x09\x00\x00\x00" + bytes(768 * 2),
                     b"\x12\x01\x00\x96\x02\x01" + bytes(16),
                     b"\x09\x00\x00\x96" + bytes(767)):
            read_response.return_value = data
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                community.render("group1/test/1")

    @patch.object(community, "read_response")
    def test_render_reports_corrupt_compressed_file(self, read_response):
        read_response.return_value = b"\x12\x01\x00\x96\x01\x01" + bytes(16)
        with self.assertRaises(ValueError):
            community.render("group1/test/1")

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
