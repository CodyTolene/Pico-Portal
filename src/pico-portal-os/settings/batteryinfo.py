# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App

_SHIM_CURVE = (
    (4.20, 100),
    (4.10, 90),
    (4.00, 80),
    (3.90, 65),
    (3.80, 50),
    (3.70, 30),
    (3.60, 15),
    (3.50, 5),
    (3.30, 0),
)
_UPS_CURVE = (
    (4.20, 100),
    (4.10, 90),
    (4.00, 80),
    (3.90, 65),
    (3.80, 50),
    (3.70, 35),
    (3.60, 20),
    (3.40, 8),
    (3.00, 0),
)


def _charge_percent(volts, profile):
    if volts is None:
        return None
    curve = _UPS_CURVE if profile == "PICO_UPS_B" else _SHIM_CURVE
    if volts >= curve[0][0]:
        return 100
    for index in range(1, len(curve)):
        high_v, high_p = curve[index - 1]
        low_v, low_p = curve[index]
        if volts >= low_v:
            fraction = (volts - low_v) / (high_v - low_v)
            return int(low_p + fraction * (high_p - low_p))
    return 0


class BatteryInfo(App):

    async def run(self, ctx):
        reading = ctx.sensors.battery()
        while True:
            _up, refresh, _select, back = ctx.input.poll()
            if back:
                return
            if refresh:
                reading = ctx.sensors.battery(force=True)
            self._draw(ctx, reading)
            await uasyncio.sleep_ms(100)

    def _draw(self, ctx, reading):
        crt = ctx.crt
        profile = reading["profile"]
        voltage = reading["voltage"]
        percent = _charge_percent(voltage, profile)

        crt.begin()
        title = "Battery Info" if crt.h > 160 else "BATTERY INFO"
        top = crt.ui_title(title)
        graphic_h = 34 if crt.h > 160 else 22
        self._battery_graphic(crt, top, graphic_h, percent, reading["usb"])
        status = self._power_state(reading["usb"])
        capacity = "{} mAh LiPo".format(reading["capacity_mah"])
        info_x = 116 if crt.h > 160 else 88
        info_w = crt.w - info_x - 8
        info_scale = crt.fit_scale(status, info_w)
        crt.text(status, info_x, top + 2, info_scale, "hi")
        capacity_scale = crt.fit_scale(capacity, info_w)
        crt.text(
            capacity,
            info_x,
            top + crt.text_height(info_scale) + 4,
            capacity_scale,
            "mid",
        )

        rows = (
            self._ups_rows()
            if profile == "PICO_UPS_B"
            else self._shim_rows(reading)
        )
        rows_top = top + graphic_h + 8
        self._detail_rows(crt, rows, rows_top, crt.ui_bottom())
        crt.button_hints(
            top_left="BACK",
            bottom_right="REFRESH",
        )
        crt.end()

    def _power_state(self, usb):
        if usb is True:
            return "STATUS CHARGE"
        return "STATUS ON BATTERY"

    def _ups_rows(self):
        return (("GAUGE", "INA219 ESTIMATE"),)

    def _shim_rows(self, reading):
        voltage = reading["voltage"]
        cell = (
            "{:.2f} V".format(voltage) if voltage is not None else "USB MASKED"
        )
        return (
            ("GAUGE", "ADC29 ESTIMATE"),
            ("CELL EST", cell),
            ("SHIM", "Pimoroni PIM557"),
            ("CHARGER", "MCP73831 / 215mA"),
            ("PROTECT", "XB6096I2S"),
        )

    def _battery_graphic(self, crt, top, height, percent, charging):
        width = 94 if crt.h > 160 else 66
        x = 8
        y = top + 1
        crt.box(x, y, width, height - 2, "mid")
        crt.use("mid")
        crt.g.rectangle(x + width + 1, y + height // 3, 4, height // 3)
        fraction = (
            percent / 100 if percent is not None else (0.28 if charging else 0)
        )
        fill = int((width - 6) * fraction)
        if fill > 0:
            crt.use("fg")
            crt.g.rectangle(x + 3, y + 3, fill, height - 8)
        percent_text = "{}%".format(percent) if percent is not None else "--%"
        scale = crt.fit_scale(percent_text, width - 8)
        text_x = x + (width - crt.measure(percent_text, scale)) // 2
        crt.text(
            percent_text,
            text_x,
            y + (height - crt.text_height(scale)) // 2,
            scale,
            "hi",
        )
        if charging:
            bolt_x = x + width - 15
            bolt_y = y + 4
            crt.use("hi")
            crt.g.line(bolt_x + 5, bolt_y, bolt_x, bolt_y + height // 2)
            crt.g.line(
                bolt_x, bolt_y + height // 2, bolt_x + 6, bolt_y + height // 2
            )
            crt.g.line(
                bolt_x + 6,
                bolt_y + height // 2,
                bolt_x + 1,
                bolt_y + height - 8,
            )

    def _detail_rows(self, crt, rows, top, bottom):
        scale = crt.preferred_scale()
        row_h = crt.text_height(scale) + 5
        while scale > 1 and len(rows) * row_h > bottom - top:
            scale = crt.smaller_scale(scale)
            row_h = crt.text_height(scale) + 5
        for index, (label, value) in enumerate(rows):
            y = top + index * row_h
            if y + crt.text_height(scale) > bottom:
                break
            crt.text(label, 10, y, scale, "dim")
            value = crt.clip_text(value, crt.w // 2 - 12, scale)
            crt.text_right(value, crt.w - 10, y, scale, "fg")
