# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import sys
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL
from ..storage import save_config
from .catalog import SAVER_NAMES
from . import prng as random

_GLYPHS = "01<>[]{}/\\|=+*#%$@ABCDEF0123456789"


class Screensavers(App):

    def __init__(self):
        self.auto = False

    async def run(self, ctx):
        try:
            await self._run(ctx)
        finally:
            self._release_effects()

    async def _run(self, ctx):
        if self.auto:
            selected = ctx.config["screensaver"].get("name", "MATRIX")
            if selected not in SAVER_NAMES:
                selected = "MATRIX"
            try:
                await self._launch(ctx, selected)
            except MemoryError:
                if selected == "MATRIX":
                    raise
                self._release_effects()
                gc.collect()
                await self._matrix(ctx)
            return

        sel = 0
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                sel = (sel - 1) % len(SAVER_NAMES)
            if down:
                sel = (sel + 1) % len(SAVER_NAMES)
            if select:
                ctx.config["screensaver"]["name"] = SAVER_NAMES[sel]
                try:
                    save_config(ctx.config)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    await self._launch(ctx, SAVER_NAMES[sel])
                finally:
                    gc.collect()
            self._menu(ctx.crt, sel, ctx.config["screensaver"].get("name"))
            await uasyncio.sleep_ms(50)

    def _menu(self, crt, sel, default_name):
        crt.begin()
        top = crt.ui_title("SCREENSAVERS")
        labels = tuple(
            name + (" *" if name == default_name else "")
            for name in SAVER_NAMES
        )
        crt.menu_rows(labels, sel, top, crt.ui_bottom(), x=6)
        crt.button_hints(
            top_left="BACK",
            top_right="SEL",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    async def _launch(self, ctx, name):
        gc.collect()
        if name == "MATRIX":
            await self._matrix(ctx)
            return
        if name == "STARFIELD":
            await self._starfield(ctx)
            return
        if name == "CIRCUIT TRACE":
            await self._circuit(ctx)
            return

        await self._launch_extended(ctx, name)

    async def _launch_extended(self, ctx, name):
        """Load only the small effect group containing the selected saver."""
        if name in ("AQUARIUM", "DVD BOUNCE", "FIREPLACE", "NYAN CAT"):
            suffix = "effect_pixel"
        elif name in ("GAME OF LIFE", "NEURAL NET", "SORTING", "SYSTEM DASH"):
            suffix = "effect_sim"
        elif name in ("RADAR", "WIREFRAME"):
            suffix = "effect_space"
        else:
            suffix = "effect_text"
        module_name = "pico-portal-os.savers." + suffix
        module = None
        runner = None
        gc.collect()
        try:
            module = __import__(module_name, None, None, ("Effects",))
            runner = module.Effects()
            await runner._launch(ctx, name, not self.auto)
        finally:
            if runner is not None:
                del runner
            if module is not None:
                del module
            self._drop_effect(module_name, suffix)
            gc.collect()

    def _drop_effect(self, module_name, child_name):
        sys.modules.pop(module_name, None)
        package = sys.modules.get("pico-portal-os.savers")
        if package is not None and hasattr(package, child_name):
            delattr(package, child_name)

    def _release_effects(self):
        """Release any partially imported effect group after exit or failure."""
        for suffix in (
            "effect_pixel",
            "effect_sim",
            "effect_space",
            "effect_text",
        ):
            self._drop_effect("pico-portal-os.savers." + suffix, suffix)
        gc.collect()

    def _leave(self, ctx):
        return any(ctx.input.poll())

    def _banner(self, crt, name, y=3):
        """
        Label the effect during menu previews only, never as an idle saver.
        """
        if not self.auto:
            crt.text_center(name, y, 1, "hi")

    async def _matrix(self, ctx):
        crt = ctx.crt
        cols = max(1, crt.w // CELL)
        rows = crt.h // CELL
        tail_length = max(10, rows - 2)
        mid_tail = max(5, tail_length // 3)
        heads = [
            -(random.getrandbits(8) % max(1, rows)) * 256 for _ in range(cols)
        ]
        speeds = [64 + random.getrandbits(8) % 167 for _ in range(cols)]
        while not self._leave(ctx):
            crt.begin()
            for col in range(cols):
                head = heads[col] // 256
                for trail in range(tail_length):
                    row = head - trail
                    if 0 <= row < rows:
                        if trail == 0:
                            pen = "hi"
                        elif trail < 3:
                            pen = "fg"
                        elif trail < mid_tail:
                            pen = "mid"
                        else:
                            pen = "dim"
                        char = _GLYPHS[random.getrandbits(5) % len(_GLYPHS)]
                        crt.text(char, col * CELL, row * CELL, 1, pen)
                heads[col] += speeds[col]
                if heads[col] // 256 - tail_length > rows:
                    heads[col] = -(random.getrandbits(3) % 7) * 256
            self._banner(crt, "MATRIX")
            crt.end()
            await uasyncio.sleep_ms(60)

    async def _starfield(self, ctx):
        import math

        crt = ctx.crt
        cx, cy = crt.w // 2, crt.h // 2
        stars = [self._star(math, random) for _ in range(52)]
        while not self._leave(ctx):
            crt.begin()
            for star in stars:
                angle, radius, speed = star
                old = radius
                speed = min(12.0, speed * 1.035 + 0.04)
                radius += speed
                if radius > max(crt.w, crt.h):
                    angle, radius, speed = self._star(math, random)
                    old = radius
                trail = max(2.0, speed * 2.8)
                x1 = cx + int(math.cos(angle) * max(0, old - trail))
                y1 = cy + int(math.sin(angle) * max(0, old - trail))
                x2 = cx + int(math.cos(angle) * radius)
                y2 = cy + int(math.sin(angle) * radius)
                crt.use("hi" if speed > 5 else "fg")
                crt.g.line(x1, y1, x2, y2)
                star[0], star[1], star[2] = angle, radius, speed
            self._banner(crt, "STARFIELD", 4)
            crt.end()
            await uasyncio.sleep_ms(22)

    def _star(self, math, random):
        return [
            random.random() * math.pi * 2,
            random.random() * 18,
            random.uniform(1.8, 4.2),
        ]

    async def _circuit(self, ctx):
        crt = ctx.crt
        step = 16
        phase = 0
        while not self._leave(ctx):
            crt.begin()
            for y in range(16, crt.h - 8, step):
                crt.use("dim")
                crt.g.line(0, y, crt.w - 1, y)
                offset = (phase + y // step * 19) % max(1, crt.w)
                crt.use("hi")
                crt.g.rectangle(offset, y - 1, 8, 3)
                for x in range(8, crt.w, 32):
                    crt.use("mid")
                    crt.g.circle(x, y, 2)
            for x in range(8, crt.w, 32):
                crt.use("scan")
                crt.g.line(x, 12, x, crt.h - 12)
            self._banner(crt, "CIRCUIT TRACE")
            phase = (phase + 4) % max(1, crt.w)
            crt.end()
            await uasyncio.sleep_ms(55)
