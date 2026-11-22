"""Read confined GIF previews and their nominal animation duration."""

import base64
import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .playlist import scan_gifs

MAX_PREVIEW_BYTES = 2 * 1024 * 1024


def gif_preview(root: Path, folder: str, filename: str) -> dict:
    """Return a GIF preview and the sum of its frame times when available."""
    if filename not in scan_gifs(root, folder, False):
        raise ValueError("GIF is not in the selected folder")
    root = root.resolve(strict=True)
    path = (root / filename).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("GIF is outside the Divoom directory")
    with path.open("rb") as source:
        content = source.read(MAX_PREVIEW_BYTES + 1)
    if len(content) > MAX_PREVIEW_BYTES:
        raise ValueError("GIF exceeds the 2 MiB preview limit")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != "GIF":
                raise ValueError("File is not a GIF")
            durations = []
            for frame in range(image.n_frames):
                image.seek(frame)
                duration = image.info.get("duration")
                if not isinstance(duration, int) or duration <= 0:
                    durations = []
                    break
                durations.append(duration)
            cycle_seconds = sum(durations) / 1000 if len(durations) > 1 else None
    except (UnidentifiedImageError, EOFError) as err:
        raise ValueError(f"Cannot read GIF: {err}") from err
    return {
        "data": base64.b64encode(content).decode("ascii"),
        "cycle_seconds": cycle_seconds,
    }
