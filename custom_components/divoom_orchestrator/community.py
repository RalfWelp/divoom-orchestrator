"""Anonymous, bounded access to Divoom's unofficial community API."""

import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import io
import json
import math
from pathlib import Path
import re
from struct import error as StructError
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lzallright import LZOError
from servoom import PixelBeanDecoder

API = "https://app.divoom-gz.com/"
FILE_API = "https://f.divoom-gz.com/"
PAGE_SIZE = 18
MAX_SEARCH_RESULTS = 100
MAX_RESPONSE = 2 * 1024 * 1024
MAX_FRAMES = 100
DEFAULT_RETRY_SECONDS = 60


class RateLimited(ValueError):
    """The community API has asked the client to slow down."""

    def __init__(self, retry_seconds: int):
        self.retry_seconds = retry_seconds
        super().__init__(
            f"Divoom-Anfragelimit erreicht; frühestens in {retry_seconds} Sekunden erneut versuchen. "
            "Die Sperre kann länger dauern."
        )


def retry_seconds(value: str | None) -> int:
    """Read Retry-After, using a conservative delay when no usable value is sent."""
    if value:
        try:
            if value.isascii() and value.isdigit():
                seconds = int(value)
            else:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                seconds = math.ceil((date - datetime.now(timezone.utc)).total_seconds())
            if seconds > 0:
                return seconds
        except (ValueError, TypeError, OverflowError):
            pass
    return DEFAULT_RETRY_SECONDS


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_response(req: Request) -> bytes:
    """Read a bounded response without following redirects."""
    try:
        with build_opener(NoRedirect).open(req, timeout=15) as response:
            content = response.read(MAX_RESPONSE + 1)
    except HTTPError as err:
        try:
            if err.code == 429:
                raise RateLimited(retry_seconds(err.headers.get("Retry-After") if err.headers else None)) from err
            raise ValueError(f"Divoom HTTP-Fehler {err.code}") from err
        finally:
            err.close()
    except (URLError, TimeoutError, OSError) as err:
        raise ValueError(f"Divoom ist nicht erreichbar: {err}") from err
    if len(content) > MAX_RESPONSE:
        raise ValueError("Divoom-Antwort ist zu groß")
    return content


def request(command: str, payload: dict) -> dict:
    """Call a fixed API endpoint, rejecting redirects and oversized responses."""
    if command != "SearchGalleryV3":
        raise ValueError("Unknown community endpoint")
    data = json.dumps(payload).encode("utf-8")
    req = Request(API + command, data=data, headers={"Content-Type": "application/json"})
    content = read_response(req)
    try:
        result = json.loads(content)
    except (ValueError, UnicodeDecodeError) as err:
        raise ValueError("Ungültige Divoom-Antwort") from err
    empty_search = (
        command == "SearchGalleryV3" and isinstance(result, dict)
        and result.get("ReturnCode") == 8
        and result.get("ReturnMessage") == "Get condition is not match"
        and result.get("CurListNum") == 0 and result.get("FileList") == []
    )
    if not isinstance(result, dict) or (result.get("ReturnCode") != 0 and not empty_search):
        code = result.get("ReturnCode") if isinstance(result, dict) else "?"
        raise ValueError(f"Divoom meldet Fehler {code}")
    return result


def search(query: str, page: int, sort: int) -> dict:
    """Search public 16x16 works; retain explicit visibility and rights flags."""
    if (not query.strip() or len(query) > 100
            or not 1 <= page <= (MAX_SEARCH_RESULTS + PAGE_SIZE - 1) // PAGE_SIZE
            or sort not in (0, 1)):
        raise ValueError("Ungültige Suche")
    end = min(page * PAGE_SIZE, MAX_SEARCH_RESULTS)
    result = request("SearchGalleryV3", {
        "Keywords": query.strip(), "KeywordsEn": query.strip(), "FileSize": 1,
        "FileType": 5, "FileSort": sort, "Classify": 1,
        "StartNum": 1, "EndNum": end,
        "Version": 19, "RefreshIndex": 0,
    })
    records = result.get("FileList")
    if not isinstance(records, list) or len(records) > end:
        raise ValueError("Ungültige Divoom-Ergebnisliste")
    works = []
    for record in records[(page - 1) * PAGE_SIZE:end]:
        if not isinstance(record, dict):
            raise ValueError("Ungültiger Divoom-Eintrag")
        gallery_id = record.get("GalleryId")
        if type(gallery_id) is not int or gallery_id <= 0 or record.get("FileSize") != 1:
            raise ValueError("Ungültiger Divoom-Eintrag")
        if any(record.get(flag) != 0 for flag in ("PrivateFlag", "HideFlag", "IsDel")):
            continue
        title, author = record.get("FileName"), record.get("UserName")
        if not isinstance(title, str) or not isinstance(author, str):
            raise ValueError("Ungültige Divoom-Metadaten")
        works.append({
            "id": gallery_id, "title": title.strip()[:200], "author": author.strip()[:200],
            "importable": record.get("CopyrightFlag") == 0, "file_id": record.get("FileId"),
        })
    return {"works": works, "has_more": len(records) == end and end < MAX_SEARCH_RESULTS}


def render(file_id: str) -> bytes:
    """Download and decode a public 16x16 artwork into a GIF."""
    if (not isinstance(file_id, str) or len(file_id) > 256
            or not re.fullmatch(r"[A-Za-z0-9._/-]+", file_id)
            or any(part in ("", ".", "..") for part in file_id.split("/"))):
        raise ValueError("Ungültige Divoom-Dateikennung")
    data = read_response(Request(FILE_API + file_id))
    if not data:
        raise ValueError("Dieses Divoom-Format oder seine Framezeiten werden nicht unterstützt")
    fmt = data[0]
    valid = (
        (fmt == 8 and len(data) == 769)
        or (fmt == 9 and len(data) > 4 and (len(data) - 4) % 768 == 0
            and (len(data) - 4) // 768 <= MAX_FRAMES)
        or (fmt == 12 and len(data) == 3076)
        or (fmt == 17 and len(data) >= 23 and data[1:3] == b"\x01\x01"
            and (len(data) - 7) % 16 == 0)
        or (fmt == 18 and len(data) >= 22 and 1 <= data[1] <= MAX_FRAMES
            and data[4:6] == b"\x01\x01" and (len(data) - 6) % 16 == 0)
    )
    if not valid:
        raise ValueError("Dieses Divoom-Format oder seine Framezeiten werden nicht unterstützt")
    try:
        bean = PixelBeanDecoder.decode_stream(io.BytesIO(data))
        if (bean is None or bean.width != 16 or bean.height != 16
                or not 1 <= bean.total_frames <= MAX_FRAMES
                or len(bean.frames_data) != bean.total_frames
                or (bean.total_frames > 1 and not 10 <= bean.speed <= 655350)):
            raise ValueError("Dieses Divoom-Format oder seine Framezeiten werden nicht unterstützt")
        images = [bean.get_frame_image(i + 1) for i in range(bean.total_frames)]
    except (IndexError, TypeError, StructError, LZOError) as err:
        raise ValueError("Divoom-Datei ist beschädigt oder wird nicht unterstützt") from err
    output = io.BytesIO()
    images[0].save(output, format="GIF", save_all=True, append_images=images[1:],
                   duration=bean.speed, loop=0, optimize=False)
    content = output.getvalue()
    if len(content) > MAX_RESPONSE:
        raise ValueError("GIF ist zu groß")
    return content


def save(root: Path, folder: str, gallery_id: int, content: bytes) -> str:
    """Save without overwriting an existing file in a confined existing folder."""
    root = root.resolve(strict=True)
    relative = Path(folder)
    if not folder or relative.is_absolute():
        raise ValueError("Ordner muss innerhalb von pixelart liegen")
    directory = (root / relative).resolve(strict=True)
    if not directory.is_relative_to(root) or not directory.is_dir():
        raise ValueError("Ordner muss innerhalb von pixelart liegen")
    path = directory / f"divoom-{gallery_id}.gif"
    target = path.open("xb")
    try:
        with target:
            target.write(content)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path.relative_to(root).as_posix()


def encoded(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")
