# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from . import NAME, VERSION
from .apps import App


class About(App):

    async def run(self, ctx):
        crt = ctx.crt
        sen = ctx.sensors
        _, mem_total = sen.memory()
        _, flash_total = sen.flash()

        lines = [
            (NAME.upper() + "  v" + VERSION, "hi"),
            ("a pocket cyber toolkit", "mid"),
            ("", "fg"),
            ("HARDWARE", "fg"),
            (" Raspberry Pi Pico W", "mid"),
            (" RP2040 @ {} MHz".format(sen.cpu_mhz()), "mid"),
            (" SRAM  {} KB".format(mem_total // 1024), "mid"),
            (" FLASH {} KB".format(flash_total // 1024), "mid"),
            (" {}x{} ST7789".format(crt.w, crt.h), "mid"),
            (" MicroPython {}".format(sen.firmware()), "mid"),
            ("", "fg"),
            ("TIPS", "fg"),
            ("- Hold bottom-left at boot to re-pick the screen.", "mid"),
            (
                "- WiFi is optional; connect it to set the clock and use "
                "online tools like Weather.",
                "mid",
            ),
            ("", "fg"),
            ("LEGAL / USE", "fg"),
            (" For lawful, authorized use only.", "mid"),
            (
                " Get permission before scanning networks or devices "
                "you do not own.",
                "mid",
            ),
            (
                " You are responsible for your actions and legal compliance.",
                "mid",
            ),
            (" Provided AS-IS, without warranty.", "dim"),
            (
                " To the extent allowed by law, the authors and contributors "
                "are not liable for misuse, damage, loss, or other "
                "consequences.",
                "dim",
            ),
            ("", "fg"),
            ("BUILT BY", "fg"),
            (" Code", "mid"),
            (" CC-BY-NC-4.0", "dim"),
        ]

        scale = crt.preferred_scale()
        expanded = []
        for text, pen in lines:
            if not text:
                expanded.append(("", pen))
                continue
            for wrapped in crt.wrap_lines(text, crt.w - 16, scale):
                expanded.append((wrapped, pen))
        lines = expanded

        title_scale = crt.fit_scale("ABOUT", crt.w - 12)
        title_y = crt.ui_top()
        top = title_y + crt.text_height(title_scale) + 5
        row_h = crt.text_height(scale) + 2
        view_h = crt.ui_bottom() - top
        per_page = max(1, view_h // row_h)
        max_off = max(0, len(lines) - per_page)
        off = 0
        sections = [
            i
            for i, line in enumerate(lines)
            if line[0] in ("HARDWARE", "TIPS", "LEGAL / USE", "BUILT BY")
        ]

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                off = max(0, off - 1)
            if down:
                off = min(max_off, off + 1)
            if select and sections:
                target = sections[0]
                for anchor in sections:
                    if anchor > off:
                        target = anchor
                        break
                off = min(max_off, target)

            crt.begin()
            crt.text_center("ABOUT", title_y, title_scale, "hi")
            crt.hline(top - 3, "dim")

            for i in range(per_page):
                idx = off + i
                if idx >= len(lines):
                    break
                text, pen = lines[idx]
                crt.text(text, 6, top + i * row_h, scale, pen)

            # scrollbar
            if max_off:
                bar_h = max(6, view_h * per_page // len(lines))
                bar_y = top + (view_h - bar_h) * off // max_off
                crt.use("dim")
                crt.g.rectangle(crt.w - 3, top, 2, view_h)
                crt.use("fg")
                crt.g.rectangle(crt.w - 3, int(bar_y), 2, int(bar_h))

            crt.button_hints(
                top_left="BACK",
                top_right="NEXT",
                bottom_left="UP",
                bottom_right="DWN",
            )
            crt.end()
            await uasyncio.sleep(0.05)
