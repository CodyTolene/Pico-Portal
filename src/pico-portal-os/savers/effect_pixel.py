# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import math
import uasyncio  # type: ignore

from ..crt import CELL
from . import prng as random


class Effects:
    async def _launch(self, ctx, name, show_title=True):
        self._show_title = show_title
        if name == "AQUARIUM":
            handler = self._aquarium
        elif name == "DVD BOUNCE":
            handler = self._dvd
        elif name == "FIREPLACE":
            handler = self._fireplace
        else:
            handler = self._nyan
        await handler(ctx)

    def _leave(self, ctx):
        return any(ctx.input.poll())

    def _banner(self, crt, name, y=3):
        """
        Label the effect during menu previews only, never as an idle saver.
        """
        if self._show_title:
            crt.text_center(name, y, 1, "hi")

    async def _nyan(self, ctx):
        crt = ctx.crt
        x = -40
        phase = 0
        colors = (
            "p_red",
            "p_orange",
            "p_yellow",
            "p_green",
            "p_cyan",
            "p_purple",
        )
        while not self._leave(ctx):
            crt.begin()
            cy = crt.h // 2 + int(math.sin(phase * 0.35) * 12)
            for index, color in enumerate(colors):
                crt.use(color)
                crt.g.rectangle(0, cy - 18 + index * 6, max(0, x + 4), 5)
            crt.use("p_orange")
            crt.g.rectangle(x, cy - 16, 42, 30)
            crt.use("p_red")
            crt.g.rectangle(x + 5, cy - 11, 32, 20)
            crt.use("p_white")
            crt.g.rectangle(x + 34, cy - 12, 22, 22)
            crt.use("p_black")
            crt.g.rectangle(x + 39, cy - 5, 3, 3)
            crt.g.rectangle(x + 49, cy - 5, 3, 3)
            crt.g.rectangle(x + 44, cy + 2, 5, 2)
            crt.g.rectangle(x + 4, cy + 14, 8, 5)
            crt.g.rectangle(x + 30, cy + 14, 8, 5)
            crt.use("p_white")
            crt.g.rectangle(x - 8, cy - 3 + (phase % 2) * 4, 10, 5)
            self._banner(crt, "NYAN CAT", 4)
            crt.end()
            x += 4
            if x > crt.w + 10:
                x = -58
            phase += 1
            await uasyncio.sleep_ms(55)

    async def _dvd(self, ctx):
        crt = ctx.crt
        x, y, dx, dy = 10, CELL + 8, 3, 2
        width, height = 52, 28
        min_y = CELL + 5
        while not self._leave(ctx):
            x += dx
            y += dy
            if x <= 0 or x + width >= crt.w:
                dx = -dx
                x = max(0, min(crt.w - width, x))
            if y <= min_y or y + height >= crt.h:
                dy = -dy
                y = max(min_y, min(crt.h - height, y))
            crt.begin()
            self._banner(crt, "DVD BOUNCE")
            self._dvd_logo(crt, x, y)
            crt.end()
            await uasyncio.sleep_ms(35)

    def _dvd_logo(self, crt, x, y):
        crt.text("DVD", x + 2, y, 2, "fg")
        crt.use("mid")
        crt.g.line(x + 3, y + 20, x + 10, y + 17)
        crt.g.line(x + 10, y + 17, x + 42, y + 17)
        crt.g.line(x + 42, y + 17, x + 49, y + 20)
        crt.g.line(x + 49, y + 20, x + 42, y + 23)
        crt.g.line(x + 42, y + 23, x + 10, y + 23)
        crt.g.line(x + 10, y + 23, x + 3, y + 20)
        crt.use("hi")
        crt.g.line(x + 13, y + 20, x + 39, y + 20)

    async def _aquarium(self, ctx):
        crt = ctx.crt
        fish = [
            [
                random.getrandbits(8) % crt.w,
                20 + random.getrandbits(8) % max(1, crt.h - 40),
                1 + random.getrandbits(2),
            ]
            for _ in range(8)
        ]
        bubbles = [
            [random.getrandbits(8) % crt.w, random.getrandbits(8) % crt.h]
            for _ in range(12)
        ]
        tuft = "_/|__|\\_  "
        grass = tuft * (crt.w // max(1, crt.measure(tuft, 1)) + 1)
        while not self._leave(ctx):
            crt.begin()
            for item in fish:
                item[0] = (item[0] + item[2]) % (crt.w + 32)
                crt.text("><(((('>", item[0] - 32, item[1], 1, "fg")
            for bubble in bubbles:
                bubble[1] -= 2
                if bubble[1] < 10:
                    bubble[0], bubble[1] = (
                        random.getrandbits(8) % crt.w,
                        crt.h - 2,
                    )
                crt.use("mid")
                crt.g.circle(bubble[0], bubble[1], 2)
            crt.text(grass, 0, crt.h - 12, 1, "dim", wrap=crt.w * 2)
            self._banner(crt, "AQUARIUM")
            crt.end()
            await uasyncio.sleep_ms(70)

    async def _fireplace(self, ctx):
        crt = ctx.crt
        cols = crt.w // 6
        flames = [0] * cols
        while not self._leave(ctx):
            crt.begin()
            for index in range(cols):
                target = 3 + random.getrandbits(5) % max(4, crt.h // 7)
                flames[index] = (flames[index] * 2 + target) // 3
                height = flames[index] * 4
                crt.use("warn" if index % 3 else "alarm")
                crt.g.rectangle(index * 6, crt.h - height, 5, height)
                crt.use("hi")
                crt.g.rectangle(
                    index * 6 + 1, crt.h - height // 2, 3, height // 2
                )
            self._banner(crt, "FIREPLACE", 4)
            crt.end()
            await uasyncio.sleep_ms(75)
