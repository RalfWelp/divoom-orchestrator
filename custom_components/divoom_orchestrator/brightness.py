"""Time and motion based brightness control."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import time
import logging
import time as monotonic_time

_LOGGER = logging.getLogger(__name__)


def scheduled_brightness(
    now: time, start: time, elevation: float, rising: bool,
    day: int, twilight: int, night: int,
) -> int:
    """Choose the configured level using civil twilight (-6 degrees)."""
    if now < start:
        return night
    if elevation >= 0:
        return day
    if rising or elevation >= -6:
        return twilight
    return night


class BrightnessController:
    """Serialize and coalesce brightness commands without cancelling transfers."""

    def __init__(
        self,
        read_schedule: Callable[[], int],
        send: Callable[[str, int | None], Awaitable[None]],
        on_error: Callable[[Exception], Awaitable[None]],
        *,
        clock: Callable[[], float] = monotonic_time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._read_schedule = read_schedule
        self._send = send
        self._on_error = on_error
        self._clock = clock
        self._sleep = sleep
        self._motion = False
        self._motion_until = 0.0
        self._test_value: int | None = None
        self._test_until = 0.0
        self._current: int | None = None
        self._powered: bool | None = None
        self._lock = asyncio.Lock()
        self._error_reported = False
        self._invalidate = False

    def motion_changed(self, active: bool) -> None:
        if active and not self._motion:
            self._motion_until = self._clock() + 30
        self._motion = active

    def connected(self) -> None:
        """Force the desired state to be re-applied after a reconnect."""
        self._invalidate = True

    def test(self, value: int) -> None:
        if not 0 <= value <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        self._test_value = value
        self._test_until = self._clock() + 30

    async def reconfigure(self, update: Callable[[], None]) -> None:
        """Apply settings only after any ongoing device command has finished."""
        async with self._lock:
            update()
            self._test_value = None
            self._invalidate = True

    def target(self) -> int:
        now = self._clock()
        if self._test_value is not None and now < self._test_until:
            return self._test_value
        self._test_value = None
        if self._motion or now < self._motion_until:
            return 100
        value = self._read_schedule()
        if not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError("Invalid scheduled brightness")
        return value

    async def refresh(self) -> None:
        """Apply the latest target, retrying on the next refresh after errors."""
        async with self._lock:
            try:
                if self._invalidate:
                    self._current = None
                    self._powered = None
                    self._invalidate = False
                await self._apply()
            except Exception as err:
                self._current = None
                self._powered = None
                if not self._error_reported:
                    self._error_reported = True
                    await self._on_error(err)
                else:
                    _LOGGER.warning("Brightness retry failed: %s", err)
                raise
            else:
                self._error_reported = False

    async def _apply(self) -> None:
        while True:
            target = self.target()
            if target == 0:
                if self._powered is True and self._current is not None and self._current > 1:
                    start = self._current
                    for step in range(1, 5):
                        if self.target() != 0:
                            break
                        value = max(1, round(start + (1 - start) * step / 4))
                        if value != self._current:
                            await self._send("brightness", value)
                            self._current = value
                        if step < 4:
                            await self._sleep(0.25)
                    if self.target() != 0:
                        continue
                if self._powered is not False:
                    await self._send("off", None)
                    self._powered = False
                self._current = 0
            else:
                if self._powered is not True:
                    await self._send("on", None)
                    self._powered = True
                if self._current is None or self._current == 0:
                    await self._send("brightness", target)
                    self._current = target
                elif self._current != target:
                    start = self._current
                    for step in range(1, 5):
                        if self.target() != target:
                            break
                        value = round(start + (target - start) * step / 4)
                        if value != self._current:
                            await self._send("brightness", value)
                            self._current = value
                        if step < 4:
                            await self._sleep(0.25)
            if target == self.target():
                return
