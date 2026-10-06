# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL
from ..storage import save_config

_ROWS = (
    ("CLOCK", "hour_format"),
    ("TEMPERATURE", "temperature_unit"),
    ("UNITS", "unit_system"),
)


class RegionalSettings(App):

    async def run(self, ctx):
        sel = 0
        dirty = False
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                if dirty:
                    save_config(ctx.config)
                return
            if up:
                sel = (sel - 1) % len(_ROWS)
            if down:
                sel = (sel + 1) % len(_ROWS)
            if select:
                self._change(ctx.config["regional"], _ROWS[sel][1])
                dirty = True
            self._draw(ctx.crt, ctx.config["regional"], sel)
            await uasyncio.sleep_ms(50)

    def _change(self, config, key):
        if key == "hour_format":
            config[key] = 12 if config.get(key, 24) == 24 else 24
        elif key == "temperature_unit":
            config[key] = "F" if config.get(key, "C") == "C" else "C"
        else:
            config[key] = (
                "metric"
                if config.get(key, "imperial") == "imperial"
                else "imperial"
            )

    def _draw(self, crt, config, sel):
        values = (
            "{} HOUR".format(config.get("hour_format", 24)),
            config.get("temperature_unit", "C"),
            str(config.get("unit_system", "imperial")).upper(),
        )
        scale = crt.fit_scale_many(tuple((row[0] for row in _ROWS)), crt.w - 16)
        stacked = scale > 1
        text_h = crt.text_height(scale)
        row_h = 2 * text_h + 6 if stacked else text_h + 8

        crt.begin()
        top = crt.ui_title("REGIONAL SETTINGS")
        bottom = crt.ui_bottom()
        visible = max(1, (bottom - top) // row_h)
        start = max(0, min(sel - visible + 1, len(_ROWS) - visible))
        for slot in range(visible):
            index = start + slot
            if index >= len(_ROWS):
                break
            row = _ROWS[index]
            y = top + slot * row_h
            selected = index == sel
            if selected:
                crt.use("mid")
                crt.g.rectangle(4, y, crt.w - 8, row_h - 2)
            pen = "bg" if selected else "fg"
            label_x = 8
            crt.text(row[0], label_x, y + 2, scale, pen)
            value_y = y + text_h + 3 if stacked else y + 2
            if stacked:
                crt.text(values[index], label_x + text_h, value_y, scale, pen)
            else:
                crt.text_right(values[index], crt.w - 10, value_y, scale, pen)
        if start > 0:
            crt.text_right("^", crt.w - 3, top, 1, "dim")
        if start + visible < len(_ROWS):
            crt.text_right("v", crt.w - 3, bottom - CELL, 1, "dim")
        crt.button_hints(
            top_left="BACK",
            top_right="SET",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()
