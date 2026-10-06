# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..storage import local_time, save_config
from ..units import format_clock

_ZONES = (
    ("Alaska", -9),
    ("Central", -6),
    ("Eastern", -5),
    ("Hawaii", -10),
    ("Mountain", -7),
    ("Pacific", -8),
    ("UTC", 0),
)


class ClockSettings(App):

    async def run(self, ctx):
        items = ("AUTO DST", "SYNC NOW", "TIMEZONE")
        sel = 0
        message = ""
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                sel = (sel - 1) % 3
            if down:
                sel = (sel + 1) % 3
            if select:
                action = items[sel]
                if action == "TIMEZONE":
                    self._next_zone(ctx.clock_config)
                    save_config(ctx.config)
                elif action == "AUTO DST":
                    ctx.clock_config["daylight_saving"] = (
                        not ctx.clock_config.get("daylight_saving", True)
                    )
                    save_config(ctx.config)
                else:
                    try:
                        if ctx.wifi.sync_time():
                            message = "SYNCED"
                        elif ctx.wifi.is_connected():
                            message = "TRY AGAIN LATER"
                        else:
                            message = "NO WIFI"
                    except Exception:  # noqa: BLE001
                        message = (
                            "TRY AGAIN LATER"
                            if ctx.wifi.is_connected()
                            else "NO WIFI"
                        )
            self._draw(ctx, sel, message)
            await uasyncio.sleep_ms(80)

    def _next_zone(self, config):
        current = config.get("timezone_name", "Central")
        index = 0
        for i, zone in enumerate(_ZONES):
            if zone[0] == current:
                index = i
                break
        name, offset = _ZONES[(index + 1) % len(_ZONES)]
        config["timezone_name"] = name
        config["utc_offset_hours"] = offset

    def _draw(self, ctx, sel, message):
        crt = ctx.crt
        now, offset = local_time(ctx.clock_config)
        rows = (
            (
                "AUTO DST",
                (
                    "ON"
                    if ctx.clock_config.get("daylight_saving", True)
                    else "OFF"
                ),
            ),
            (
                "SYNC NOW",
                message or ("ONLINE" if ctx.wifi.is_connected() else "OFFLINE"),
            ),
            ("TIMEZONE", ctx.clock_config.get("timezone_name", "Central")),
        )
        crt.begin()
        top = crt.ui_title("CLOCK SETTINGS")
        clock_text = format_clock(now, ctx.config, seconds=True)
        clock_scale = crt.fit_scale(clock_text, crt.w - 16)
        crt.text_center(
            clock_text,
            top,
            clock_scale,
            "fg",
        )
        top += crt.text_height(clock_scale) + 3
        date_text = "{:04d}-{:02d}-{:02d}  UTC{:+d}".format(
            now[0], now[1], now[2], offset
        )
        date_scale = crt.fit_scale(date_text, crt.w - 16)
        crt.text_center(
            date_text,
            top,
            date_scale,
            "mid",
        )
        top += crt.text_height(date_scale) + 4
        scale = crt.fit_scale_many(tuple((row[0] for row in rows)), crt.w - 16)
        stacked = scale > 1
        text_h = crt.text_height(scale)
        row_h = 2 * text_h + 5 if stacked else text_h + 6
        visible = max(1, (crt.ui_bottom() - top) // row_h)
        start = max(0, min(sel - visible + 1, len(rows) - visible))
        for slot in range(visible):
            i = start + slot
            if i >= len(rows):
                break
            row = rows[i]
            y = top + slot * row_h
            if i == sel:
                crt.use("mid")
                crt.g.rectangle(4, y, crt.w - 8, row_h - 2)
            pen = "bg" if i == sel else "fg"
            label_x = 8
            crt.text(row[0], label_x, y + 2, scale, pen)
            value = str(row[1])
            value_scale = scale
            value_y = y + text_h + 3 if stacked else y + 2
            if stacked:
                value_x = label_x + text_h
                value = crt.clip_text(value, crt.w - value_x - 12, value_scale)
                crt.text(value, value_x, value_y, value_scale, pen)
            else:
                crt.text_right(value, crt.w - 12, value_y, value_scale, pen)
        crt.button_hints(
            top_left="BACK",
            top_right="SET",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()
