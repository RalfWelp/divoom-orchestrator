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
    wake: asyncio.Event | None = None,
    run_event: Callable[[], Awaitable[None]] | None = None,
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
            if run_event is not None:
                await run_event()
                if stop.is_set():
                    return
            if duration_for is not None and duration_for(filename) is None:
                continue
            await show(filename)
            if stop.is_set():
                return
            if wake is not None and wake.is_set():
                continue
            seconds = duration if duration_for is None else duration_for(filename)
            if seconds is None or not math.isfinite(seconds) or not 0 < seconds <= 3600:
                raise ValueError(f"Invalid display duration for {filename}")
            try:
                await asyncio.wait_for((wake or stop).wait(), timeout=seconds)
                if stop.is_set():
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
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._event_pending: tuple[
            list[tuple[str, float]], Callable[[str], Awaitable[None]], int, str | None,
            Callable[[], Awaitable[None]] | None, Callable[[], Awaitable[None]] | None,
        ] | None = None
        self._event_active = False
        self._event_priority: int | None = None
        self._event_name: str | None = None
        self._device: str | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def wait_for_interrupt(self, seconds: float) -> bool:
        """Wait for a stop or event while a transfer is being retried."""
        try:
            await asyncio.wait_for(self._wake.wait(), timeout=seconds)
            return True
        except TimeoutError:
            return False

    async def _run_event(self) -> None:
        try:
            while self._event_pending is not None and not self._stop.is_set():
                steps, show, priority, name, on_start, on_finish = self._event_pending
                self._event_pending = None
                self._event_active = True
                self._event_priority = priority
                self._event_name = name
                self._wake.clear()
                try:
                    if on_start is not None:
                        await on_start()
                    for filename, seconds in steps:
                        if self._stop.is_set() or self._event_pending is not None:
                            break
                        await show(filename)
                        if self._stop.is_set() or self._event_pending is not None:
                            break
                        try:
                            await asyncio.wait_for(self._wake.wait(), timeout=seconds)
                        except TimeoutError:
                            pass
                        if self._stop.is_set() or self._event_pending is not None:
                            break
                finally:
                    if on_finish is not None:
                        await on_finish()
            if self._event_pending is None:
                self._wake.clear()
        finally:
            self._event_active = False
            self._event_priority = None
            self._event_name = None

    async def start_event(
        self, steps: list[tuple[str, float]], show: Callable[[str], Awaitable[None]],
        device: str | None = None,
        *, priority: int = 1, name: str | None = None,
        on_start: Callable[[], Awaitable[None]] | None = None,
        on_finish: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Run one event, interrupting a rotation at its next safe point."""
        async with self._lock:
            if not isinstance(priority, int) or isinstance(priority, bool) or priority < 1:
                raise ValueError("Event priority must be a positive integer")
            if self._event_pending is not None:
                _, _, pending_priority, pending_name, _, _ = self._event_pending
                if priority >= pending_priority or (name is not None and name == pending_name):
                    raise ValueError("An event is already running with equal or higher priority")
            if self._event_active and self._event_priority is not None and (
                priority >= self._event_priority or (name is not None and name == self._event_name)
            ):
                raise ValueError("An event is already running with equal or higher priority")
            if not steps or any(not math.isfinite(s) or s <= 0 or s > 3600 for _, s in steps):
                raise ValueError("Event contains no steps or an invalid duration")
            if self._task is not None and self._task.done():
                self._task = None
                self._device = None
            if self._task is not None and self._device is not None and device != self._device:
                raise ValueError("Event and rotation must use the same device")
            if self._task is None:
                self._stop = asyncio.Event()
                self._wake = asyncio.Event()
                self._device = device
            self._event_pending = (list(steps), show, priority, name, on_start, on_finish)
            self._wake.set()
            if self._task is None:
                async def run() -> None:
                    try:
                        await self._run_event()
                    except Exception as err:
                        await self._on_error(err)
                self._task = self._create_task(run())

    async def start(
        self,
        scan: Callable[[], Awaitable[list[str]]],
        show: Callable[[str], Awaitable[None]],
        duration: float,
        duration_for: Callable[[str], float | None] | None = None,
        device: str | None = None,
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
            self._wake = asyncio.Event()
            self._device = device

            async def run() -> None:
                try:
                    await play(scan, show, duration, self._stop, first, duration_for,
                               self._wake, self._run_event)
                except Exception as err:
                    await self._on_error(err)
                finally:
                    self._event_pending = None

            self._task = self._create_task(run())

    async def stop(self) -> None:
        async with self._lock:
            task = self._task
            if task is None:
                return
            self._stop.set()
            self._wake.set()
            await asyncio.shield(task)
            self._task = None
            self._event_pending = None
            self._device = None
