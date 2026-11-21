"""Filesystem selection and playback for Divoom playlists."""

import asyncio
from pathlib import Path
import random
from collections.abc import Awaitable, Callable


def scan_gifs(root: Path, folder: str, shuffle: bool) -> list[str]:
    """Return confined, direct GIF children relative to the Divoom root."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    subdir = Path(folder)
    if subdir.is_absolute():
        raise ValueError("The playlist folder must be relative to the Divoom directory")
    directory = (root / subdir).resolve(strict=True)
    if not directory.is_relative_to(root):
        raise ValueError("The playlist folder is outside the Divoom directory")
    if not directory.is_dir():
        raise NotADirectoryError(str(directory))
    results = []
    for path in directory.iterdir():
        if path.suffix.lower() != ".gif":
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f"GIF points outside the Divoom directory: {path.name}")
        if resolved.is_file():
            results.append(path.relative_to(root).as_posix())
    results.sort(key=lambda name: (name.casefold(), name))
    if shuffle:
        random.shuffle(results)
    return results


async def play(
    scan: Callable[[], Awaitable[list[str]]],
    show: Callable[[str], Awaitable[None]],
    duration: float,
) -> None:
    """Repeat playlists, refreshing the file list at each cycle."""
    if duration <= 0:
        raise ValueError("Duration must be positive")
    while True:
        files = await scan()
        if not files:
            raise ValueError("The playlist directory contains no GIF files")
        for filename in files:
            await show(filename)
            await asyncio.sleep(duration)
