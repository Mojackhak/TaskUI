from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, Tuple

from PyQt5 import QtCore


@dataclass
class Stopwatch:
    start_datetime: datetime = field(default_factory=datetime.now)
    start_perf: float = field(default_factory=time.perf_counter)

    def reset(self) -> None:
        self.start_datetime = datetime.now()
        self.start_perf = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self.start_perf

    def elapsed_ms(self) -> int:
        return int(self.elapsed() * 1000)

    def timestamp_pair(self) -> Tuple[datetime, float]:
        return datetime.now(), self.elapsed()


def elapsed_since(start_perf: float) -> float:
    return time.perf_counter() - start_perf


def timestamp_pair_from_perf(start_perf: float) -> Tuple[datetime, float]:
    return datetime.now(), elapsed_since(start_perf)


def start_countdown_timer(
    parent: QtCore.QObject,
    duration_s: float,
    on_tick: Callable[[int], None],
    on_finished: Optional[Callable[[], None]] = None,
    interval_ms: int = 50,
    register_timer: Optional[Callable[[QtCore.QTimer], None]] = None,
) -> QtCore.QTimer:
    """Start a Qt countdown timer that calls on_tick with remaining milliseconds."""
    duration_s = max(0.0, duration_s)
    start_perf = time.perf_counter()
    remaining_ms = max(0, int(math.ceil(duration_s * 1000)))
    on_tick(remaining_ms)

    timer = QtCore.QTimer(parent)
    timer.setInterval(interval_ms)

    def _handle_timeout() -> None:
        nonlocal remaining_ms
        elapsed = time.perf_counter() - start_perf
        remaining_ms = max(0, int(math.ceil((duration_s - elapsed) * 1000)))
        if remaining_ms <= 0:
            timer.stop()
            if on_finished:
                on_finished()
            return
        on_tick(remaining_ms)

    timer.timeout.connect(_handle_timeout)
    timer.start()
    if register_timer:
        register_timer(timer)
    return timer


def format_countdown_text(message: str, remaining_ms: int, use_html: bool = False) -> str:
    """Return a formatted countdown string; use_html adds monospace styling like GoStop."""
    countdown_str = f"{remaining_ms/1000:06.3f}s"
    if use_html:
        return f"{message}<br><span style='font-family: \"Courier New\", monospace;'>{countdown_str}</span>"
    return f"{message}\n{countdown_str}"


def run_blocking_countdown(
    duration_s: float,
    on_tick: Callable[[int], None],
    on_finished: Optional[Callable[[], None]] = None,
    check_abort: Optional[Callable[[], bool]] = None,
    step_s: float = 0.01,
) -> None:
    """Blocking countdown loop for contexts without Qt timers (keeps updating on_tick)."""
    end_time = time.perf_counter() + max(0.0, duration_s)
    last_ms = None
    while True:
        if check_abort and check_abort():
            break
        now = time.perf_counter()
        remaining_ms = max(0, int(math.ceil((end_time - now) * 1000)))
        if remaining_ms != last_ms:
            on_tick(remaining_ms)
            last_ms = remaining_ms
        if now >= end_time:
            break
        time.sleep(step_s)
    if on_finished and (not check_abort or not check_abort()):
        on_finished()
