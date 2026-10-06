# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL
from ..units import format_temperature, temperature_unit, temperature_value

_HIST = 48
_STALE_MS = 120000  # two mins


def _bars(rssi):
    return (
        4 if rssi >= -60 else (3 if rssi >= -72 else (2 if rssi >= -84 else 1))
    )


def _age(ms):
    if ms < 1000:
        return "now"
    if ms < 60000:
        return "{}s".format(ms // 1000)
    return "{}m".format(ms // 60000)


class SensorReader(App):

    async def run(self, ctx):
        if not ctx.ble.start(sensors=True):
            await self._unavailable(ctx)
            return

        sel = 0
        mode = "LIST"
        tracked = None
        hist = []

        while True:
            up, down, select, back = ctx.input.poll()
            rows = ctx.ble.readings()

            if mode == "LIST":
                if back:
                    ctx.ble.stop()
                    ctx.lamp.set((0, 70, 30))
                    return
                if up:
                    sel = (sel - 1) % max(1, len(rows))
                if down:
                    sel = (sel + 1) % max(1, len(rows))
                if select and rows:
                    tracked = rows[sel][0]
                    hist = []
                    mode = "DETAIL"
                    continue
                self._draw_list(ctx, rows, sel)
            else:
                if back or select:
                    mode = "LIST"
                    continue
                if (up or down) and rows:
                    sel = (sel + (1 if down else -1)) % len(rows)
                    tracked = rows[sel][0]
                    hist = []

                row = None
                for candidate in rows:
                    if candidate[0] == tracked:
                        row = candidate
                        break
                if (
                    row is not None
                    and row[4] is not None
                    and row[8] < _STALE_MS
                ):
                    if not hist or hist[-1] != row[4]:
                        hist.append(row[4])
                        if len(hist) > _HIST:
                            hist.pop(0)
                self._draw_detail(ctx, tracked, row, hist, ctx.config)

            await uasyncio.sleep(0.05)

    def _draw_list(self, ctx, rows, sel):
        crt = ctx.crt
        crt.begin()
        title = "Sensor Reader" if crt.h > 160 else "SENSORS"
        crt.text_center("{}  {}".format(title, len(rows)), 3, 1, "hi")
        crt.hline(CELL + 5, "dim")

        row_h = CELL + 3
        top_y = CELL + 9
        visible = max(1, (crt.h - top_y - CELL - 2) // row_h)
        start = 0
        if sel >= visible:
            start = sel - visible + 1

        if not rows:
            crt.text("listening for sensors...", 8, top_y, 1, "mid")
            crt.text("BTHome / Mijia / Govee", 8, top_y + row_h, 1, "dim")
            crt.text("ATC / pvvx broadcasts", 8, top_y + 2 * row_h, 1, "dim")
            crt.text("they report every 10-60s", 8, top_y + 4 * row_h, 1, "dim")

        for i in range(visible):
            index = start + i
            if index >= len(rows):
                break
            _mac, name, rssi, kind, temp, humidity, _batt, _mv, age = rows[
                index
            ]
            y = top_y + i * row_h
            stale = age >= _STALE_MS
            pen = "dim" if stale else ("hi" if index == sel else "mid")
            if index == sel:
                crt.use("dim")
                crt.g.rectangle(2, y - 1, crt.w - 4, row_h - 1)
            self._signal(crt, 4, y, 0 if stale else _bars(rssi))
            reading = (
                format_temperature(temp, ctx.config, decimals=1)
                if temp is not None
                else "--"
            )
            crt.text(reading, 26, y, 1, pen)
            if humidity is not None:
                crt.text("{:.0f}%".format(humidity), 76, y, 1, pen)
            label = name if name else kind
            crt.text(crt.clip_text(label, crt.w - 118, 1), 112, y, 1, pen)

        ctx.lamp.set((40, 60, 220) if rows else (0, 60, 90))
        crt.button_hints(
            top_left="BACK",
            top_right="READ" if rows else None,
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    def _draw_detail(self, ctx, tracked, row, hist, config):
        crt = ctx.crt
        crt.begin()
        crt.text_center(
            "Sensor Reader" if crt.h > 160 else "SENSORS", 3, 1, "hi"
        )
        crt.hline(CELL + 5, "dim")

        if row is None:
            crt.text_center("SENSOR GONE", crt.h // 2 - 10, 2, "alarm")
            crt.text_center("dropped from the table", crt.h // 2 + 14, 1, "mid")
            ctx.lamp.set((200, 40, 20))
            crt.button_hints(top_left="BACK", top_right="LIST")
            crt.end()
            return

        _mac, name, rssi, kind, temp, humidity, battery, millivolts, age = row
        stale = age >= _STALE_MS
        top = CELL + 10

        if temp is None:
            crt.text("--", 8, top, 4, "dim")
        else:
            big = "{:.1f}".format(temperature_value(temp, config))
            crt.text(big, 8, top, 4, "dim" if stale else "fg")
            crt.text(
                temperature_unit(config),
                8 + crt.measure(big, 4) + 3,
                top,
                2,
                "dim" if stale else "hi",
            )
        ctx.lamp.set((90, 90, 90) if stale else (40, 160, 120))

        crt.text(
            kind or "SENSOR",
            crt.w - 8 - crt.measure(kind or "SENSOR", 1),
            top,
            1,
            "hi",
        )
        crt.text_right(
            "{} dBm".format(rssi), crt.w - 8, top + CELL + 2, 1, "mid"
        )
        crt.text_right(_age(age), crt.w - 8, top + 2 * CELL + 4, 1, "dim")

        row_y = top + 4 * CELL + 2
        if humidity is not None:
            crt.text("RH", 8, row_y, 1, "mid")
            crt.text("{:.1f}%".format(humidity), 28, row_y, 1, "fg")
            bar_x = 78
            bar_w = crt.w - bar_x - 8
            if bar_w > 20:
                crt.bar(bar_x, row_y, bar_w, CELL - 2, humidity / 100.0, "fg")
            row_y += CELL + 4

        if battery is not None or millivolts is not None:
            crt.text("BATT", 8, row_y, 1, "mid")
            parts = []
            if battery is not None:
                parts.append("{}%".format(battery))
            if millivolts is not None:
                parts.append("{:.2f}V".format(millivolts / 1000.0))
            pen = "alarm" if battery is not None and battery < 15 else "fg"
            crt.text(" ".join(parts), 44, row_y, 1, pen)
            row_y += CELL + 4

        if name:
            crt.text(crt.clip_text(name, crt.w - 16, 1), 8, row_y, 1, "hi")
            row_y += CELL + 2
        crt.text(
            crt.clip_text(tracked or "", crt.w - 16, 1), 8, row_y, 1, "dim"
        )
        row_y += CELL + 4

        graph_h = 24
        if len(hist) > 1 and row_y + graph_h < crt.ui_bottom():
            crt.box(8, row_y, crt.w - 16, graph_h, "dim", title="TEMP")
            low = min(hist)
            high = max(hist)
            span = high - low
            if span < 0.5:
                low -= 0.25
                span = 0.5
            crt.sparkline(
                10,
                row_y + 3,
                crt.w - 20,
                graph_h - 6,
                hist,
                "fg",
                scale=span,
                minimum=low,
            )
            label_y = row_y + graph_h + 2
            if label_y + CELL <= crt.ui_bottom():
                crt.text_right(
                    "{:.1f} - {:.1f}".format(
                        temperature_value(min(hist), config),
                        temperature_value(max(hist), config),
                    ),
                    crt.w - 10,
                    label_y,
                    1,
                    "dim",
                )

        crt.button_hints(
            top_left="BACK",
            top_right="LIST",
            bottom_left="PREV",
            bottom_right="NEXT",
        )
        crt.end()

    def _signal(self, crt, x, y, bars):
        for i in range(4):
            height = 3 + i * 2
            crt.use("hi" if i < bars else "dim")
            crt.g.rectangle(x + i * 5, y + 9 - height, 3, height)

    async def _unavailable(self, ctx):
        crt = ctx.crt
        ctx.lamp.set((120, 60, 0))
        while True:
            if any(ctx.input.poll()):
                ctx.lamp.set((0, 70, 30))
                return
            crt.begin()
            crt.text_center(
                "Sensor Reader" if crt.h > 160 else "SENSORS", 3, 1, "hi"
            )
            crt.hline(CELL + 5, "dim")
            crt.text_center("BLUETOOTH", crt.h // 2 - 20, 2, "warn")
            crt.text_center("UNAVAILABLE", crt.h // 2, 2, "warn")
            crt.text_center("not in this firmware", crt.h // 2 + 22, 1, "mid")
            crt.button_hints(top_left="BACK")
            crt.end()
            await uasyncio.sleep(0.05)
