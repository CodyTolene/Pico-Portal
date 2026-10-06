# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import random
import uasyncio  # type: ignore

from . import App
from ..crt import CELL

_MODES = ["D6", "D20", "COIN", "FORTUNE"]

_FORTUNES = [
    "YES",
    "NO",
    "MAYBE",
    "ASK AGAIN",
    "DEFINITELY",
    "NOT NOW",
    "SIGNS SAY YES",
    "DOUBTFUL",
    "GO FOR IT",
    "SLEEP ON IT",
    "OUTLOOK GOOD",
    "NO WAY",
]

_PIPS = {
    1: [(1, 1)],
    2: [(0, 0), (2, 2)],
    3: [(0, 0), (1, 1), (2, 2)],
    4: [(0, 0), (2, 0), (0, 2), (2, 2)],
    5: [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)],
    6: [(0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2)],
}


class DiceRoller(App):

    async def run(self, ctx):
        crt = ctx.crt
        mode = 0
        result, text_result = self._sample(mode)

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                ctx.lamp.set((0, 70, 30))
                return
            if up:
                mode = (mode - 1) % len(_MODES)
                result, text_result = self._sample(mode)
            if down:
                mode = (mode + 1) % len(_MODES)
                result, text_result = self._sample(mode)
            if select:
                result, text_result = await self._roll(ctx, mode)

            self._draw(crt, mode, result, text_result)
            await uasyncio.sleep(0.04)

    async def _roll(self, ctx, mode):
        ctx.lamp.set((0, 255, 120))
        for _ in range(8):
            r, t = self._sample(mode)
            crt = ctx.crt
            self._draw(crt, mode, r, t, rolling=True)
            await uasyncio.sleep(0.045)
        ctx.lamp.set((0, 90, 40))
        return self._sample(mode)

    def _sample(self, mode):
        name = _MODES[mode]
        if name == "D6":
            v = random.randint(1, 6)
            return v, str(v)
        if name == "D20":
            v = random.randint(1, 20)
            return v, str(v)
        if name == "COIN":
            return 0, random.choice(("HEADS", "TAILS"))
        return 0, random.choice(_FORTUNES)

    def _draw(self, crt, mode, result, text_result, rolling=False):
        crt.begin()
        top = crt.ui_title("DICE ROLLER")
        mode_scale = crt.fit_scale(_MODES[mode], crt.w - 24)
        crt.text_center(_MODES[mode], top, mode_scale, "mid")
        content_top = top + crt.text_height(mode_scale) + 3
        content_bottom = crt.ui_bottom() - 2
        cy = (content_top + content_bottom) // 2
        self._draw_result(
            crt,
            mode,
            result,
            text_result,
            "mid" if rolling else "fg",
            cy,
            max(20, content_bottom - content_top),
        )
        if rolling:
            crt.text_center("ROLLING...", content_bottom - CELL, 1, "dim")
        crt.button_hints(
            top_left="BACK",
            top_right="ROLL",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    def _draw_result(
        self, crt, mode, result, text_result, pen, cy, available_h
    ):
        name = _MODES[mode]
        cx = crt.w // 2
        if name == "D6":
            self._draw_die(crt, cx, cy, result, pen, min(56, available_h - 4))
        elif name == "D20":
            scale = 5
            too_wide = crt.measure(text_result, scale) > crt.w - 24
            too_tall = crt.text_height(scale) > available_h - CELL
            while scale > 1 and (too_wide or too_tall):
                scale -= 1
                too_wide = crt.measure(text_result, scale) > crt.w - 24
                too_tall = crt.text_height(scale) > available_h - CELL
            crt.text_center(
                text_result, cy - crt.text_height(scale) // 2, scale, pen
            )
        elif name == "COIN":
            radius = max(12, min(30, available_h // 2 - 3))
            crt.use("dim")
            crt.g.circle(cx, cy, radius)
            crt.use("bg")
            crt.g.circle(cx, cy, max(9, radius - 3))
            scale = crt.fit_scale(text_result, radius * 2 - 8)
            crt.text_center(
                text_result, cy - crt.text_height(scale) // 2, scale, pen
            )
        else:  # FORTUNE
            scale = crt.fit_scale(text_result, crt.w - 24)
            crt.text_center(
                text_result, cy - crt.text_height(scale) // 2, scale, pen
            )

    def _draw_die(self, crt, cx, cy, value, pen, size):
        size = max(24, size)
        x0 = cx - size // 2
        y0 = cy - size // 2
        crt.use("dim")
        crt.g.rectangle(x0, y0, size, size)
        crt.use("bg")
        crt.g.rectangle(x0 + 3, y0 + 3, size - 6, size - 6)
        crt.use(pen)
        step = size // 3
        r = max(2, min(5, size // 10))
        for gx, gy in _PIPS.get(value, _PIPS[1]):
            px = x0 + step // 2 + gx * step
            py = y0 + step // 2 + gy * step
            crt.g.circle(px, py, r)
