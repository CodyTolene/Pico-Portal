# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================
import random
import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL

_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


class Snake(App):

    async def run(self, ctx):
        state = self._new(ctx.crt)
        while True:
            left, right, action, back = ctx.input.poll()
            if back:
                return
            if left:
                state["direction"] = (state["direction"] - 1) % 4
            if right:
                state["direction"] = (state["direction"] + 1) % 4
            if action:
                if state["dead"]:
                    state = self._new(ctx.crt)
                else:
                    state["paused"] = not state["paused"]
            now = time.ticks_ms()
            ready = all(
                (
                    not state["paused"],
                    not state["dead"],
                    time.ticks_diff(now, state["next"]) >= 0,
                )
            )
            if ready:
                self._step(state)
                state["next"] = time.ticks_add(
                    now, max(65, 180 - len(state["body"]) * 3)
                )
            self._draw(ctx.crt, state)
            await uasyncio.sleep_ms(35)

    def _new(self, crt):
        cell = 6 if crt.h <= 160 else 9
        top = crt.ui_top() + CELL + 5
        cols = (crt.w - 8) // cell
        rows = (crt.h - top - CELL - 4) // cell
        center = (cols // 2, rows // 2)
        state = {
            "cell": cell,
            "cols": cols,
            "rows": rows,
            "top": top,
            "body": [
                center,
                (center[0] - 1, center[1]),
                (center[0] - 2, center[1]),
            ],
            "direction": 0,
            "apple": (2, 2),
            "next": time.ticks_add(time.ticks_ms(), 300),
            "dead": False,
            "paused": False,
        }
        self._apple(state)
        return state

    def _apple(self, state):
        for _ in range(40):
            apple = (
                random.getrandbits(8) % state["cols"],
                random.getrandbits(8) % state["rows"],
            )
            if apple not in state["body"]:
                state["apple"] = apple
                return

    def _step(self, state):
        dx, dy = _DIRECTIONS[state["direction"]]
        head = state["body"][0]
        new = (head[0] + dx, head[1] + dy)
        if any(
            (
                new[0] < 0,
                new[0] >= state["cols"],
                new[1] < 0,
                new[1] >= state["rows"],
                new in state["body"],
            )
        ):
            state["dead"] = True
            return
        state["body"].insert(0, new)
        if new == state["apple"]:
            self._apple(state)
        else:
            state["body"].pop()

    def _draw(self, crt, state):
        cell = state["cell"]
        left = (crt.w - state["cols"] * cell) // 2
        top = state["top"]
        crt.begin()
        crt.text_center(
            "SNAKE  SCORE {:03d}".format(len(state["body"]) - 3),
            crt.ui_top(),
            1,
            "hi",
        )
        crt.use("warn")
        ax, ay = state["apple"]
        crt.g.circle(
            left + ax * cell + cell // 2,
            top + ay * cell + cell // 2,
            max(2, cell // 3),
        )
        for index, segment in enumerate(state["body"]):
            crt.use("hi" if index == 0 else "fg")
            crt.g.rectangle(
                left + segment[0] * cell + 1,
                top + segment[1] * cell + 1,
                cell - 1,
                cell - 1,
            )
        if state["dead"]:
            crt.text_center("CRASH // SEL RESTART", crt.h // 2, 1, "alarm")
        elif state["paused"]:
            crt.text_center("PAUSED", crt.h // 2, 2, "warn")
        crt.button_hints(
            top_left="BACK",
            top_right="PAUSE",
            bottom_left="TURN L",
            bottom_right="TURN R",
        )
        crt.end()
