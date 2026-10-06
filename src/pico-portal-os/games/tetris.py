# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import random
import time
import uasyncio  # type: ignore

from ..apps import App

_SHAPES = (
    ((0, 0), (1, 0), (2, 0), (3, 0)),
    ((0, 0), (1, 0), (0, 1), (1, 1)),
    ((1, 0), (0, 1), (1, 1), (2, 1)),
    ((0, 0), (0, 1), (1, 1), (2, 1)),
    ((2, 0), (0, 1), (1, 1), (2, 1)),
    ((1, 0), (2, 0), (0, 1), (1, 1)),
    ((0, 0), (1, 0), (1, 1), (2, 1)),
)


class Tetris(App):

    async def run(self, ctx):
        state = self._new()
        while True:
            left, right, rotate, back = ctx.input.poll()
            if back:
                return
            if state["game_over"]:
                if rotate:
                    state = self._new()
            else:
                if left:
                    self._move(state, -1, 0)
                if right:
                    self._move(state, 1, 0)
                if rotate:
                    self._rotate(state)
                now = time.ticks_ms()
                if time.ticks_diff(now, state["next"]) >= 0:
                    if not self._move(state, 0, 1):
                        self._lock(state)
                    state["next"] = time.ticks_add(
                        now, max(65, 260 - state["lines"] * 9)
                    )
            self._draw(ctx.crt, state)
            await uasyncio.sleep_ms(20)

    def _new(self):
        state = {
            "board": [[0] * 10 for _ in range(18)],
            "piece": (),
            "x": 3,
            "y": 0,
            "kind": 0,
            "lines": 0,
            "next": time.ticks_add(time.ticks_ms(), 250),
            "game_over": False,
        }
        self._spawn(state)
        return state

    def _spawn(self, state):
        state["kind"] = random.getrandbits(8) % len(_SHAPES)
        state["piece"] = _SHAPES[state["kind"]]
        state["x"], state["y"] = 3, 0
        if self._blocked(state, state["piece"], 3, 0):
            state["game_over"] = True

    def _blocked(self, state, piece, px, py):
        for x, y in piece:
            bx, by = px + x, py + y
            if (
                bx < 0
                or bx >= 10
                or by >= 18
                or (by >= 0 and state["board"][by][bx])
            ):
                return True
        return False

    def _move(self, state, dx, dy):
        nx, ny = state["x"] + dx, state["y"] + dy
        if self._blocked(state, state["piece"], nx, ny):
            return False
        state["x"], state["y"] = nx, ny
        return True

    def _rotate(self, state):
        rotated = tuple((-y, x) for x, y in state["piece"])
        min_x = min(point[0] for point in rotated)
        min_y = min(point[1] for point in rotated)
        rotated = tuple((x - min_x, y - min_y) for x, y in rotated)
        if not self._blocked(state, rotated, state["x"], state["y"]):
            state["piece"] = rotated

    def _lock(self, state):
        for x, y in state["piece"]:
            bx, by = state["x"] + x, state["y"] + y
            if 0 <= by < 18:
                state["board"][by][bx] = state["kind"] + 1
        kept = [row for row in state["board"] if not all(row)]
        cleared = 18 - len(kept)
        state["board"] = [[0] * 10 for _ in range(cleared)] + kept
        state["lines"] += cleared
        self._spawn(state)

    def _draw(self, crt, state):
        cell = 6 if crt.h <= 160 else 10
        left = (crt.w - 10 * cell) // 2
        top = 16 if crt.h <= 160 else 38
        crt.begin()
        crt.text_center(
            "TETRIS // LINES {:02d}".format(state["lines"]),
            3 if crt.h <= 160 else 12,
            1,
            "hi",
        )
        crt.box(left - 2, top - 2, 10 * cell + 3, 18 * cell + 3, "dim")
        for y, row in enumerate(state["board"]):
            for x, value in enumerate(row):
                if value:
                    crt.use("fg" if value % 2 else "mid")
                    crt.g.rectangle(
                        left + x * cell + 1,
                        top + y * cell + 1,
                        cell - 1,
                        cell - 1,
                    )
        if not state["game_over"]:
            crt.use("hi")
            for x, y in state["piece"]:
                crt.g.rectangle(
                    left + (state["x"] + x) * cell + 1,
                    top + (state["y"] + y) * cell + 1,
                    cell - 1,
                    cell - 1,
                )
        else:
            crt.text_center("STACKED // ROT RESTART", crt.h // 2, 1, "alarm")
        crt.button_hints(
            top_left="BACK",
            top_right="ROT",
            bottom_left="LEFT",
            bottom_right="RIGHT",
        )
        crt.end()
