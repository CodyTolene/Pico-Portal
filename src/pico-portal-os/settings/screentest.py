# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import math
import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL

_EFFECTS = ["SOLID", "BREATHE", "RAINBOW", "STROBE", "OFF"]


def hsv_to_rgb(h, s, v):
    """h in 0..1, s/v in 0..1 -> (r, g, b) 0..255."""
    scaled = h * 6
    i = int(scaled) % 6
    f = scaled - int(scaled)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)


class ScreenTest(App):

    async def run(self, ctx):
        crt = ctx.crt
        effect = 0
        hue = 0.33
        speed = 1.0

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                ctx.lamp.set((0, 70, 30))
                return
            if up:
                effect = (effect - 1) % len(_EFFECTS)
            if down:
                effect = (effect + 1) % len(_EFFECTS)
            if select:
                name = _EFFECTS[effect]
                if name == "SOLID":
                    hue = (hue + 1.0 / 12) % 1.0
                else:
                    speed = 0.5 if speed >= 4.0 else speed * 2

            rgb = self._compute(_EFFECTS[effect], hue, speed)
            ctx.lamp.set(rgb)

            crt.begin()
            crt.text_center("SCREEN TEST  " + _EFFECTS[effect], 3, 1, "hi")
            crt.hline(CELL + 4, "dim")

            sx, sy = 8, 22
            sw, sh = crt.w - 16, crt.h - 64
            crt.use("dim")
            crt.g.rectangle(sx - 1, sy - 1, sw + 2, sh + 2)
            crt.g.set_pen(crt.preview_pen(rgb))
            crt.g.rectangle(sx, sy, sw, sh)

            info = "rgb {:>3} {:>3} {:>3}".format(*rgb)
            crt.text(info, 6, crt.h - 40, 1, "mid")
            if _EFFECTS[effect] == "SOLID":
                crt.text("SEL changes hue", 6, crt.h - 28, 1, "mid")
            elif _EFFECTS[effect] != "OFF":
                crt.text(
                    "SEL speed {:.0f}x".format(speed), 6, crt.h - 28, 1, "mid"
                )

            crt.hline(crt.h - CELL - 6, "dim")
            crt.button_hints(
                top_left="BACK",
                top_right="SET",
                bottom_left="UP",
                bottom_right="DWN",
            )
            crt.end()
            await uasyncio.sleep(0.03)

    def _compute(self, name, hue, speed):
        phase = (time.ticks_ms() / 1000.0) * speed
        if name == "SOLID":
            return hsv_to_rgb(hue, 1.0, 1.0)
        if name == "BREATHE":
            v = 0.15 + 0.85 * (0.5 + 0.5 * math.sin(phase * 2))
            return hsv_to_rgb(hue, 1.0, v)
        if name == "RAINBOW":
            return hsv_to_rgb((phase * 0.15) % 1.0, 1.0, 1.0)
        if name == "STROBE":
            on = int(phase * 6) % 2 == 0
            return (255, 255, 255) if on else (0, 0, 0)
        return (0, 0, 0)  # OFF
