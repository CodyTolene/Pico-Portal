# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL, lerp_rgb
from ..units import format_temperature, temperature_unit, temperature_value

_COOL = (0, 200, 90)
_WARM = (255, 150, 0)
_HOT = (255, 40, 20)

_T_LO = 20.0
_T_HI = 50.0
_HIST = 64


def _temp_color(t):
    if t < 38.0:
        return lerp_rgb(_COOL, _WARM, (t - _T_LO) / 18.0)
    return lerp_rgb(_WARM, _HOT, (t - 38.0) / 17.0)


class SystemMonitor(App):

    async def run(self, ctx):
        crt = ctx.crt
        sen = ctx.sensors
        hist = []
        mem_used, mem_total = sen.memory()
        flash_used, flash_total = sen.flash()
        mhz = sen.cpu_mhz()
        power = (None, None)
        next_stats = time.ticks_add(time.ticks_ms(), 1000)
        next_power = 0

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return

            temp = sen.temperature()
            now = time.ticks_ms()
            if time.ticks_diff(now, next_stats) >= 0:
                mem_used, mem_total = sen.memory()
                next_stats = time.ticks_add(now, 1000)
            if time.ticks_diff(now, next_power) >= 0:
                power = sen.power()
                next_power = time.ticks_add(now, 1000)

            norm_temp = (temp - _T_LO) / (_T_HI - _T_LO)
            hist.append(max(0.0, min(1.0, norm_temp)))
            if len(hist) > _HIST:
                hist.pop(0)

            ctx.lamp.set(_temp_color(temp))

            crt.begin()

            title = "System Monitor" if crt.h > 160 else "SYS.MON"
            crt.text_center(title, 3, 1, "hi")
            crt.hline(CELL + 4, "dim")

            temp_text = "{:.1f}".format(temperature_value(temp, ctx.config))
            crt.text(temp_text, 6, 18, 3, "fg")
            deg_x = 6 + crt.measure(temp_text, 3) + 2
            crt.text(temperature_unit(ctx.config), deg_x, 22, 2, "mid")

            gx = crt.w // 2 + 6
            gy = 18
            gw = crt.w - gx - 6
            gh = 26
            crt.box(gx, gy, gw, gh, "dim")
            crt.sparkline(gx + 1, gy + 1, gw - 2, gh - 2, hist, "fg")

            self._meter(crt, 56, "SRAM", mem_used, mem_total, "K", 1024)
            self._meter(crt, 72, "FLASH", flash_used, flash_total, "K", 1024)

            crt.text("PWR", 6, 88, 1, "mid")
            crt.text(self._power_text(power), 6 + 6 * CELL, 88, 1, "fg")

            if crt.h > 160:
                self._chip_panel(
                    crt,
                    sen,
                    temp,
                    mem_used,
                    mem_total,
                    flash_used,
                    flash_total,
                    ctx.config,
                )

            crt.hline(crt.h - CELL - 6, "dim")
            fy = crt.h - CELL - 2
            crt.text("CPU {} MHz".format(mhz), 4, fy, 1, "mid")
            crt.button_hints(top_left="BACK")

            crt.end()
            await uasyncio.sleep(0.1)

    def _chip_panel(
        self, crt, sen, temp, used, total, flash_used, flash_total, config
    ):
        top = 112
        bottom = crt.h - CELL - 20
        height = max(56, bottom - top)
        crt.box(8, top, crt.w - 16, height, "dim", title="RP2040 CORE MAP")
        cx = crt.w // 2
        cy = top + height // 2
        size = min(64, height - 20)
        crt.use("mid")
        crt.g.rectangle(cx - size // 2, cy - size // 2, size, size)
        crt.use("bg")
        crt.g.rectangle(
            cx - size // 2 + 4, cy - size // 2 + 4, size - 8, size - 8
        )
        for offset in range(-size // 2 + 5, size // 2, 10):
            crt.use("fg")
            crt.g.line(
                cx - size // 2 - 6, cy + offset, cx - size // 2, cy + offset
            )
            crt.g.line(
                cx + size // 2, cy + offset, cx + size // 2 + 6, cy + offset
            )
        crt.text_center("DUAL CORE", cy - 14, 1, "hi")
        crt.text_center(format_temperature(temp, config), cy, 2, "fg")
        crt.text(
            "HEAP {:>3}%".format(int(used * 100 / total) if total else 0),
            14,
            bottom - 12,
            1,
            "mid",
        )
        crt.text_right(
            "UP {}s".format(sen.uptime_ms() // 1000),
            crt.w - 14,
            bottom - 12,
            1,
            "mid",
        )
        crt.text(
            "FLASH FREE {}K".format((flash_total - flash_used) // 1024),
            14,
            top + 9,
            1,
            "dim",
        )

    def _power_text(self, power):
        on_usb, volts = power
        if on_usb is True:
            src = "USB"
        elif on_usb is False:
            src = "BATT"
        else:
            src = "----"
        return src if volts is None else "{}  {:.2f}V".format(src, volts)

    def _meter(self, crt, y, label, used, total, unit, div):
        crt.text(label, 6, y, 1, "mid")
        bx = 6 + 6 * CELL
        bw = crt.w - bx - 78
        frac = (used / total) if total else 0
        pen = "alarm" if frac > 0.9 else ("warn" if frac > 0.75 else "fg")
        crt.bar(bx, y, bw, CELL - 2, frac, pen, "dim")
        crt.text_right(
            "{}/{}{}".format(used // div, total // div, unit),
            crt.w - 4,
            y,
            1,
            "fg",
        )
