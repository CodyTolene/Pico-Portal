# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import math
import uasyncio  # type: ignore

from . import prng as random


class Effects:
    async def _launch(self, ctx, name, show_title=True):
        self._show_title = show_title
        handler = self._radar_saver if name == "RADAR" else self._wireframe
        await handler(ctx)

    def _leave(self, ctx):
        return any(ctx.input.poll())

    def _banner(self, crt, name, y=3):
        """
        Label the effect during menu previews only, never as an idle saver.
        """
        if self._show_title:
            crt.text_center(name, y, 1, "hi")

    async def _wireframe(self, ctx):
        crt = ctx.crt
        phase = 0
        horizon = crt.h // 3
        while not self._leave(ctx):
            crt.begin()
            crt.hline(horizon, "mid")
            for index in range(1, 12):
                frac = ((index * 13 + phase) % 140) / 140
                y = horizon + int(frac * frac * (crt.h - horizon))
                crt.hline(y, "dim")
            center = crt.w // 2
            for x in range(-crt.w, crt.w * 2, 24):
                crt.use("mid")
                crt.g.line(center, horizon, x, crt.h - 1)
            self._banner(crt, "WIREFRAME", 4)
            crt.end()
            phase = (phase + 5) % 140
            await uasyncio.sleep_ms(45)

    async def _radar_saver(self, ctx):
        crt = ctx.crt
        sweep = 0.0
        contacts = [
            [
                random.random() * 6.28,
                random.uniform(0.15, 0.9),
                random.getrandbits(8),
            ]
            for _ in range(9)
        ]
        radius = min(crt.h // 2 - 13, crt.w // 3)
        while not self._leave(ctx):
            crt.begin()
            cx, cy = crt.w // 2, crt.h // 2
            crt.radar(cx, cy, radius, 0, sweep, "fg")
            for angle, distance, ident in contacts:
                x = cx + int(math.cos(angle) * radius * distance)
                y = cy + int(math.sin(angle) * radius * distance)
                crt.use("hi")
                crt.g.circle(x, y, 2)
                if abs(((sweep - angle) % 6.28)) < 0.25:
                    crt.text("T{:02X}".format(ident), x + 4, y - 4, 1, "fg")
            self._banner(crt, "RADAR")
            crt.end()
            sweep = (sweep + 0.12) % 6.28
            await uasyncio.sleep_ms(45)
