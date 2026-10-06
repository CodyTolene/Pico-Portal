# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time
import uasyncio  # type: ignore

from . import App
from ..crt import CELL

_MAX_LAPS = 3


def _fmt(ms):
    cs = (ms // 10) % 100
    s = (ms // 1000) % 60
    m = ms // 60000
    return "{:02d}:{:02d}.{:02d}".format(m, s, cs)


class Stopwatch(App):

    async def run(self, ctx):
        crt = ctx.crt
        running = False
        accrued = 0
        start = 0
        laps = []

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                ctx.lamp.set((0, 70, 30))
                return

            if select:  # start / stop
                if running:
                    accrued += time.ticks_diff(time.ticks_ms(), start)
                    running = False
                else:
                    start = time.ticks_ms()
                    running = True
            if down and running:  # lap
                laps.append(self._elapsed(running, accrued, start))
                if len(laps) > _MAX_LAPS:
                    laps.pop(0)
            if up and not running:  # reset
                accrued = 0
                laps = []

            elapsed = self._elapsed(running, accrued, start)
            ctx.lamp.set((0, 220, 90) if running else (0, 60, 26))

            crt.begin()
            state = "RUN" if running else ("STOP" if elapsed else "READY")
            title = "Stopwatch" if crt.h > 160 else "STOPWATCH"
            crt.text_center(title + "  [" + state + "]", 3, 1, "hi")
            crt.hline(CELL + 4, "dim")

            big = _fmt(elapsed)
            crt.text_center(big, 22, 3, "fg" if running else "hi")

            ly = 58
            if laps:
                crt.text("LAPS", 6, ly, 1, "mid")
                for i, lp in enumerate(laps):
                    crt.text(
                        "{}  {}".format(i + 1, _fmt(lp)),
                        6,
                        ly + 12 + i * 11,
                        1,
                        "mid",
                    )

            crt.hline(crt.h - CELL - 6, "dim")
            crt.button_hints(
                top_left="BACK",
                top_right="STOP" if running else "RUN",
                bottom_left="RESET",
                bottom_right="LAP",
            )
            crt.end()
            await uasyncio.sleep(0.03)

    def _elapsed(self, running, accrued, start):
        if running:
            return accrued + time.ticks_diff(time.ticks_ms(), start)
        return accrued
