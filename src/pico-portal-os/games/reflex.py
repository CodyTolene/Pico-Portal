# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import random
import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL

# states
_IDLE = 0
_WAIT = 1
_GO = 2
_RESULT = 3
_EARLY = 4


class Reflex(App):

    async def run(self, ctx):
        state = _IDLE
        go_at = 0
        started = 0
        result = 0
        best = None

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                ctx.lamp.set((0, 70, 30))
                return

            now = time.ticks_ms()

            action = select or up or down
            if action:
                if state in (_IDLE, _RESULT, _EARLY):
                    state = _WAIT
                    go_at = time.ticks_add(now, random.randint(1400, 4200))
                elif state == _WAIT:
                    state = _EARLY
                elif state == _GO:
                    result = time.ticks_diff(now, started)
                    if best is None or result < best:
                        best = result
                    state = _RESULT

            if state == _WAIT and time.ticks_diff(go_at, now) <= 0:
                state = _GO
                started = now

            action_label = "STOP" if state in (_WAIT, _GO) else "START"
            self._draw(ctx, state, result, best, now, started, action_label)
            await uasyncio.sleep(0.02)

    def _draw(self, ctx, state, result, best, now, started, action_label):
        crt = ctx.crt

        if state == _GO:
            ctx.lamp.set((0, 255, 90))
            crt.use("fg")
            crt.g.clear()
            crt.text_center("NOW!", crt.h // 2 - 16, 4, "bg")
            live = time.ticks_diff(now, started)
            crt.text_center("{} ms".format(live), crt.h // 2 + 24, 1, "bg")
            crt.button_hints(
                top_left="BACK",
                top_right=action_label,
                bottom_left=action_label,
                bottom_right=action_label,
            )
            crt.g.update()
            return

        crt.begin()
        crt.ui_title("REFLEX")

        cy = crt.h // 2 - 8
        if state == _IDLE:
            ctx.lamp.set((0, 60, 26))
            crt.text_center("REACTION TEST", cy - 14, 2, "fg")
            crt.text_center("ANY START TO ARM", cy + 12, 1, "mid")
        elif state == _WAIT:
            ctx.lamp.set((220, 40, 20))
            crt.text_center("WAIT...", cy, 3, "alarm")
            crt.text_center("hold steady", cy + 30, 1, "mid")
        elif state == _EARLY:
            ctx.lamp.set((220, 40, 20))
            crt.text_center("TOO SOON!", cy, 3, "alarm")
            crt.text_center("ANY START TO RETRY", cy + 30, 1, "mid")
        elif state == _RESULT:
            ctx.lamp.set((0, 200, 90))
            crt.text_center("{} ms".format(result), cy - 6, 4, "fg")
            crt.text_center("ANY START TO RETRY", cy + 34, 1, "mid")

        if best is not None:
            crt.text_center(
                "best {} ms".format(best), crt.h - 2 * CELL - 8, 1, "mid"
            )

        crt.hline(crt.ui_bottom() - 3, "dim")
        crt.button_hints(
            top_left="BACK",
            top_right=action_label,
            bottom_left=action_label,
            bottom_right=action_label,
        )
        crt.end()
