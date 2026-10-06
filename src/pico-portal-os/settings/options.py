# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL, THEME_NAMES
from ..storage import save_config

_ROWS = (
    ("IDLE SAVER", "screensaver", "timeout"),
    ("LED", "led", "brightness"),
    ("SAVER", "screensaver", "name"),
    ("SCANLINES", "display", "scanlines"),
    ("SCREEN", "display", "brightness"),
    ("STATUS LED", "led", "status"),
    ("TEXT PX", "display", "font_px"),
    ("THEME", "display", "theme"),
)
_SCREEN_LEVELS = (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
_LED_LEVELS = (0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0)
_IDLE_LEVELS = (0, 60, 120, 300)


def _next_level(current, levels):
    """
    Cycle from the nearest configured level, tolerating edited JSON values.
    """
    nearest = 0
    best = abs(levels[0] - current)
    for i in range(1, len(levels)):
        distance = abs(levels[i] - current)
        if distance < best:
            nearest = i
            best = distance
    return levels[(nearest + 1) % len(levels)]


class Options(App):

    async def run(self, ctx):
        config = ctx.config["display"]
        stored_font_px = config.get("font_px", 8)
        config["font_px"] = ctx.crt.text_pixels()
        sel = 0
        dirty = stored_font_px != config["font_px"]

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                if dirty:
                    try:
                        save_config(ctx.config)
                    except Exception as exc:  # noqa: BLE001
                        await self._notice(ctx, "SAVE FAILED", str(exc))
                return
            if up:
                sel = (sel - 1) % len(_ROWS)
            if down:
                sel = (sel + 1) % len(_ROWS)
            if select:
                self._change(ctx, _ROWS[sel][1], _ROWS[sel][2])
                dirty = True

            self._draw(ctx, sel)
            await uasyncio.sleep_ms(50)

    def _change(self, ctx, section, key):
        config = ctx.config[section]
        if key == "theme":
            current = config.get(key, "green")
            index = THEME_NAMES.index(current) if current in THEME_NAMES else 0
            value = THEME_NAMES[(index + 1) % len(THEME_NAMES)]
            config[key] = ctx.crt.set_theme(value)
        elif key == "scanlines":
            value = not config.get(key, True)
            config[key] = value
            ctx.crt.set_scanlines(value)
        elif section == "display" and key == "brightness":
            value = _next_level(config.get(key, 0.9), _SCREEN_LEVELS)
            config[key] = value
            ctx.crt.set_brightness(value)
        elif section == "led" and key == "brightness":
            value = _next_level(config.get(key, 0.05), _LED_LEVELS)
            config[key] = value
            ctx.lamp.set_brightness(value)
            ctx.lamp.set((0, 180, 80))
        elif key == "status":
            modes = ("heartbeat", "off", "on")
            current = config.get(key, "heartbeat")
            index = modes.index(current) if current in modes else 0
            config[key] = modes[(index + 1) % len(modes)]
        elif key == "timeout":
            config[key] = _next_level(config.get(key, 60), _IDLE_LEVELS)
        elif key == "name":
            from ..savers.catalog import SAVER_NAMES

            current = config.get(key, "MATRIX")
            index = SAVER_NAMES.index(current) if current in SAVER_NAMES else 0
            config[key] = SAVER_NAMES[(index + 1) % len(SAVER_NAMES)]
        elif key == "font_px":
            levels = ctx.crt.supported_text_pixels()
            current = ctx.crt.text_pixels()
            index = levels.index(current) if current in levels else 0
            config[key] = levels[(index + 1) % len(levels)]

    def _draw(self, ctx, sel):
        crt = ctx.crt
        config = ctx.config
        scale = crt.fit_scale_many(tuple((row[0] for row in _ROWS)), crt.w - 16)
        text_h = crt.text_height(scale)
        stacked = text_h > CELL
        row_h = (2 * text_h + 6) if stacked else (text_h + 8)

        crt.begin()
        top = crt.ui_title("DISPLAY SETTINGS")
        bottom = crt.ui_bottom()
        visible = max(1, (bottom - top) // row_h)
        start = max(0, min(sel - visible + 1, len(_ROWS) - visible))
        for row in range(visible):
            i = start + row
            if i >= len(_ROWS):
                break
            label, section, key = _ROWS[i]
            y = top + row * row_h
            selected = i == sel
            if selected:
                crt.use("mid")
                crt.g.rectangle(4, y, crt.w - 8, row_h - 2)
            pen = "bg" if selected else "mid"
            value = self._value(config, section, key)
            value_scale = scale
            label_x = 8
            crt.text(label, label_x, y + 2, scale, pen)
            value_y = y + text_h + 3 if stacked else y + 2
            if stacked:
                value_x = label_x + text_h
                value = crt.clip_text(value, crt.w - value_x - 10, value_scale)
                crt.text(value, value_x, value_y, value_scale, pen)
            else:
                crt.text_right(value, crt.w - 10, value_y, value_scale, pen)

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

    def _value(self, config, section, key):
        value = config[section].get(key)
        if key == "theme":
            return str(value).upper()
        if key == "scanlines":
            return "ON" if value else "OFF"
        if key == "timeout":
            return "OFF" if not value else "{}m".format(value // 60)
        if key == "status":
            return str(value).upper()
        if key == "name":
            return str(value).upper()
        if key == "font_px":
            return "{} PX".format(value)
        return "{}%".format(int(float(value) * 100))

    async def _notice(self, ctx, title, detail):
        await ctx.lamp.feedback("error")
        ctx.lamp.status("error")
        try:
            for _ in range(20):
                crt = ctx.crt
                crt.begin()
                crt.text_center(title, crt.h // 2 - 12, 2, "alarm")
                crt.text_center(detail[:24], crt.h // 2 + 12, 1, "warn")
                crt.end()
                await uasyncio.sleep_ms(50)
        finally:
            ctx.lamp.status("idle")
