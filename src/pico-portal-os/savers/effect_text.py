# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..crt import CELL
from . import prng as random
from ..units import format_clock


class Effects:
    async def _launch(self, ctx, name, show_title=True):
        self._show_title = show_title
        if name == "BOOT LOOP":
            handler = self._bootloop
        elif name == "CODE CLOCK":
            handler = self._code_clock
        elif name == "HACKER TERM":
            handler = self._hacker
        else:
            handler = self._hex
        await handler(ctx)

    def _leave(self, ctx):
        return any(ctx.input.poll())

    def _banner(self, crt, name, y=3):
        """
        Label the effect during menu previews only, never as an idle saver.
        """
        if self._show_title:
            crt.text_center(name, y, 1, "hi")

    async def _hex(self, ctx):
        crt = ctx.crt
        rows = max(3, crt.h // CELL - 3)
        values = [random.getrandbits(32) for _ in range(rows)]
        tick = 0
        while not self._leave(ctx):
            if tick % 3 == 0:
                values.pop(0)
                values.append(random.getrandbits(32))
            crt.begin()
            for index, value in enumerate(values):
                address = (tick * 16 + index * 16) & 0xFFFF
                crt.text(
                    "{:04X}  {:08X}".format(address, value),
                    8,
                    CELL + 5 + index * CELL,
                    1,
                    "fg" if index == rows - 1 else "dim",
                )
            self._banner(crt, "HEX STREAM")
            tick += 1
            crt.end()
            await uasyncio.sleep_ms(70)

    async def _hacker(self, ctx):
        crt = ctx.crt
        lines = []
        commands = (
            "> mounting /dev/field",
            "[ok] entropy pool ready",
            "> scan --passive wlan0",
            "host 10.0.0.{} alive",
            "tls tunnel established",
            "hash {:08X} verified",
            "access policy: root",
            "packet trace {:04X}:{:04X}",
        )
        tick = 0
        while not self._leave(ctx):
            if tick % 4 == 0:
                template = commands[random.getrandbits(8) % len(commands)]
                try:
                    line = template.format(
                        random.getrandbits(8),
                        random.getrandbits(32),
                        random.getrandbits(16),
                        random.getrandbits(16),
                    )
                except Exception:  # noqa: BLE001
                    line = template
                lines.append(line)
                while len(lines) > max(1, crt.h // (CELL + 3) - 2):
                    lines.pop(0)
            crt.begin()
            for index, line in enumerate(lines):
                crt.text(
                    line[: crt.w // CELL],
                    4,
                    CELL + 5 + index * (CELL + 3),
                    1,
                    "hi" if index == len(lines) - 1 else "dim",
                )
            crt.cursor(
                4,
                CELL + 5 + len(lines) * (CELL + 3),
                1,
                "fg",
                crt.blink(250),
            )
            self._banner(crt, "HACKER TERM")
            crt.end()
            tick += 1
            await uasyncio.sleep_ms(55)

    async def _bootloop(self, ctx):
        crt = ctx.crt
        messages = (
            "BIOS v4.20",
            "COUNTING MEMORY",
            "640K BASE OK",
            "FLOPPY A: SEEK",
            "IDE0 MASTER OS",
            "LOADING KERNEL",
            "CHECKING FILESYSTEM",
            "LOGIN: root",
        )
        shown = 0
        tick = 0
        while not self._leave(ctx):
            if tick % 8 == 0:
                shown += 1
                if shown > len(messages) + 4:
                    shown = 0
            crt.begin()
            self._banner(crt, "BOOT LOOP")
            for index in range(min(shown, len(messages))):
                suffix = " ... OK" if index else ""
                crt.text(
                    messages[index] + suffix,
                    6,
                    CELL + 6 + index * (CELL + 4),
                    1,
                    "fg",
                )
            if shown > len(messages):
                crt.text_center("REBOOTING...", crt.h - 24, 1, "warn")
            crt.end()
            tick += 1
            await uasyncio.sleep_ms(55)

    async def _code_clock(self, ctx):
        crt = ctx.crt
        from ..storage import local_time

        while not self._leave(ctx):
            now, offset = local_time(ctx.clock_config)
            clock = format_clock(now, ctx.config, seconds=True)
            crt.begin()
            for row in range(max(1, crt.h // CELL)):
                value = (now[5] * 257 + row * 4099 + now[4] * 17) & 0xFFFFFFFF
                crt.text(
                    "{:08X} {:08X}".format(value, value ^ 0xA5A55A5A),
                    (row % 3) * -20,
                    row * CELL,
                    1,
                    "dim",
                )
            timezone = "{} UTC{:+d}".format(
                ctx.clock_config.get("timezone_name", "Central"), offset
            )
            scale = 3
            while scale > 1 and crt.measure(clock, scale) > crt.w - 24:
                scale -= 1
            timezone_scale = 1
            time_h = crt.text_height(scale)
            gap = 5
            pad_x = 10
            pad_y = 8
            content_width = max(
                crt.measure(clock, scale),
                crt.measure(timezone, timezone_scale),
            )
            width = min(crt.w - 8, content_width + pad_x * 2)
            height = pad_y * 2 + time_h + gap + crt.text_height(timezone_scale)
            x = (crt.w - width) // 2
            panel_y = (crt.h - height) // 2
            time_y = panel_y + pad_y
            timezone_y = time_y + time_h + gap
            crt.use("bg")
            crt.g.rectangle(x, panel_y, width, height)
            crt.box(x, panel_y, width, height, "fg")
            crt.text_center(clock, time_y, scale, "hi")
            crt.text_center(timezone, timezone_y, timezone_scale, "mid")
            self._banner(crt, "CODE CLOCK")
            crt.end()
            await uasyncio.sleep_ms(180)
