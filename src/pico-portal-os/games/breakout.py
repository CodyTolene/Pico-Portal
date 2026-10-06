# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL


class Breakout(App):

    async def run(self, ctx):
        state = self._new(ctx.crt)
        while True:
            left, right, action, back = ctx.input.poll()
            if back:
                return
            if left:
                state["paddle"] = max(0, state["paddle"] - 14)
            if right:
                state["paddle"] = min(ctx.crt.w - 42, state["paddle"] + 14)
            if action:
                if state["lost"] or not state["bricks"]:
                    state = self._new(ctx.crt)
                else:
                    state["running"] = True
            if state["running"] and not state["lost"]:
                self._step(ctx.crt, state)
            self._draw(ctx.crt, state)
            await uasyncio.sleep_ms(10)

    def _new(self, crt):
        brick_w = max(18, (crt.w - 18) // 10)
        play_top = crt.ui_top() + CELL + 5
        bricks = []
        for row in range(4):
            for col in range(10):
                bricks.append(
                    [9 + col * brick_w, play_top + row * 10, brick_w - 2, 7]
                )
        return {
            "bricks": bricks,
            "total": len(bricks),
            "top": play_top - 4,
            "paddle": crt.w // 2 - 21,
            "x": crt.w / 2,
            "y": crt.h - 28,
            "dx": 5.0,
            "dy": -5.5,
            "running": False,
            "lost": False,
        }

    def _step(self, crt, state):
        steps = int(max(abs(state["dx"]), abs(state["dy"]))) + 1
        paddle_y = crt.h - 18
        hit_brick = False
        for _ in range(steps):
            old_y = state["y"]
            state["x"] += state["dx"] / steps
            state["y"] += state["dy"] / steps
            if state["x"] <= 3:
                state["x"] = 3
                state["dx"] = abs(state["dx"])
            elif state["x"] >= crt.w - 3:
                state["x"] = crt.w - 3
                state["dx"] = -abs(state["dx"])
            if state["y"] <= state["top"]:
                state["y"] = state["top"]
                state["dy"] = abs(state["dy"])

            paddle_hit = all(
                (
                    state["dy"] > 0,
                    old_y + 3 < paddle_y <= state["y"] + 3,
                    state["paddle"] - 3 <= state["x"] <= state["paddle"] + 45,
                )
            )
            if paddle_hit:
                state["y"] = paddle_y - 3
                state["dy"] = -abs(state["dy"])
                state["dx"] += (state["x"] - state["paddle"] - 21) / 18
                state["dx"] = max(-7.0, min(7.0, state["dx"]))

            for brick in state["bricks"]:
                brick_hit = all(
                    (
                        brick[0] - 3 <= state["x"] <= brick[0] + brick[2] + 3,
                        brick[1] - 3 <= state["y"] <= brick[1] + brick[3] + 3,
                    )
                )
                if brick_hit:
                    state["bricks"].remove(brick)
                    vertical = (
                        old_y + 3 < brick[1] or old_y - 3 > brick[1] + brick[3]
                    )
                    if vertical:
                        state["dy"] = -state["dy"]
                    else:
                        state["dx"] = -state["dx"]
                    hit_brick = True
                    break
            if hit_brick:
                break
        if state["y"] > crt.h:
            state["lost"] = True
            state["running"] = False

    def _draw(self, crt, state):
        crt.begin()
        crt.text_center(
            "BREAKOUT  SCORE {:02d}".format(
                state["total"] - len(state["bricks"])
            ),
            crt.ui_top(),
            1,
            "hi",
        )
        for brick in state["bricks"]:
            crt.use("hi" if (brick[1] // 10) % 2 else "mid")
            crt.g.rectangle(*brick)
        crt.use("fg")
        crt.g.rectangle(state["paddle"], crt.h - 18, 42, 4)
        crt.use("hi")
        crt.g.circle(int(state["x"]), int(state["y"]), 3)
        if state["lost"]:
            crt.text_center("MISSED // SEL RESTART", crt.h // 2, 1, "alarm")
        elif not state["running"]:
            crt.text_center("SEL TO LAUNCH", crt.h // 2, 1, "mid")
        elif not state["bricks"]:
            crt.text_center("CLEARED // SEL AGAIN", crt.h // 2, 1, "hi")
        crt.button_hints(
            top_left="BACK",
            top_right="LAUNCH",
            bottom_left="LEFT",
            bottom_right="RIGHT",
        )
        crt.end()
