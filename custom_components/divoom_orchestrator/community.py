"""Anonymous, bounded access to Divoom's unofficial community API."""

import base64
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image

API = "https://app.divoom-gz.com/"
PAGE_SIZE = 9
MAX_RESPONSE = 2 * 1024 * 1024
MAX_FRAMES = 100


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(command: str, payload: dict) -> dict:
    """Call a fixed API endpoint, rejecting redirects and oversized responses."""
    if command not in ("SearchGalleryV3", "Cloud/GetFileData"):
        raise ValueError("Unknown community endpoint")
    data = json.dumps(payload).encode("utf-8")
    req = Request(API + command, data=data, headers={"Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect).open(req, timeout=15) as response:
            content = response.read(MAX_RESPONSE + 1)
    except HTTPError as err:
        if err.code == 429:
            raise ValueError("Divoom-Anfragelimit erreicht; bitte später erneut versuchen") from err
        raise ValueError(f"Divoom HTTP-Fehler {err.code}") from err
    except (URLError, TimeoutError, OSError) as err:
        raise ValueError(f"Divoom ist nicht erreichbar: {err}") from err
    if len(content) > MAX_RESPONSE:
        raise ValueError("Divoom-Antwort ist zu groß")
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
    if not query.strip() or len(query) > 100 or not 1 <= page <= 100 or sort not in (0, 1):
        raise ValueError("Ungültige Suche")
    start = (page - 1) * PAGE_SIZE + 1
    result = request("SearchGalleryV3", {
        "Keywords": query.strip(), "KeywordsEn": query.strip(), "FileSize": 1,
        "FileType": 5, "FileSort": sort, "Classify": 1,
        "StartNum": start, "EndNum": start + PAGE_SIZE - 1,
        "Version": 19, "RefreshIndex": 0,
    })
    records = result.get("FileList")
    if not isinstance(records, list) or len(records) > PAGE_SIZE:
        raise ValueError("Ungültige Divoom-Ergebnisliste")
    works = []
    for record in records:
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
            "importable": record.get("CopyrightFlag") == 0,
        })
    return {"works": works, "has_more": len(records) == PAGE_SIZE}


def render(gallery_id: int) -> bytes:
    """Convert supported raw 16x16 RGB frames into a GIF."""
    result = request("Cloud/GetFileData", {"GalleryId": gallery_id})
    frames, speed, data = result.get("PicCount"), result.get("Speed"), result.get("FileData")
    if (type(frames) is not int or not 1 <= frames <= MAX_FRAMES
            or result.get("xScreenCount") != 1 or result.get("yScreenCount") != 1
            or type(speed) is not int or (frames > 1 and not 10 <= speed <= 655350)
            or not isinstance(data, list) or len(data) != frames * 768
            or any(type(value) is not int or not 0 <= value <= 255 for value in data)):
        raise ValueError("Dieses Divoom-Format oder seine Framezeiten werden nicht unterstützt")
    pixels = bytes(data)
    images = [Image.frombytes("RGB", (16, 16), pixels[i * 768:(i + 1) * 768])
              for i in range(frames)]
    output = io.BytesIO()
    images[0].save(output, format="GIF", save_all=True, append_images=images[1:],
                   duration=speed, loop=0, optimize=False)
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
