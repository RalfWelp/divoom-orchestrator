"""Filesystem selection and playback for Divoom playlists."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import math
from pathlib import Path
import random
from typing import Any


def scan_gifs(root: Path, folder: str, shuffle: bool) -> list[str]:
    """Return confined, direct GIF children relative to the Divoom root."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    subdir = Path(folder)
    if not folder or subdir.is_absolute():
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
    stop: asyncio.Event,
    first: list[str],
    duration_for: Callable[[str], float | None] | None = None,
) -> None:
    """Repeat playlists, refreshing the file list at each cycle."""
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Duration must be positive")
    files = first
    while not stop.is_set():
        if not files:
            message = "The playlist directory contains no GIF files"
            if duration_for is not None:
                message += " with a configured duration"
            raise ValueError(message)
        for filename in files:
            if stop.is_set():
                return
            seconds = duration if duration_for is None else duration_for(filename)
            if seconds is None:
                continue
            if not math.isfinite(seconds) or not 1 <= seconds <= 3600:
                raise ValueError(f"Invalid display duration for {filename}")
            await show(filename)
            if stop.is_set():
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=seconds)
                return
            except TimeoutError:
                pass
        if not stop.is_set():
            files = await scan()
            if duration_for is not None:
                files = [filename for filename in files if duration_for(filename) is not None]


class PlaylistController:
    """Run at most one playlist, serializing start and stop requests."""

    def __init__(
        self,
        create_task: Callable[[Coroutine[Any, Any, None]], asyncio.Task[None]],
        on_error: Callable[[Exception], Awaitable[None]],
    ) -> None:
        self._create_task = create_task
        self._on_error = on_error
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(
        self,
        scan: Callable[[], Awaitable[list[str]]],
        show: Callable[[str], Awaitable[None]],
        duration: float,
        duration_for: Callable[[str], float | None] | None = None,
    ) -> None:
        async with self._lock:
            if self._task is not None and not self._task.done():
                raise ValueError("A playlist is already running; stop it first")
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("Duration must be positive")
            first = await scan()
            if duration_for is not None:
                first = [filename for filename in first if duration_for(filename) is not None]
            if not first:
                message = "The playlist directory contains no GIF files"
                if duration_for is not None:
                    message += " with a configured duration"
                raise ValueError(message)
            self._stop = asyncio.Event()

            async def run() -> None:
                try:
                    await play(scan, show, duration, self._stop, first, duration_for)
                except Exception as err:
                    await self._on_error(err)

            self._task = self._create_task(run())

    async def stop(self) -> None:
        async with self._lock:
            task = self._task
            if task is None:
                return
            self._stop.set()
            await asyncio.shield(task)
            self._task = None
