# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL

_CHANNELS = 13
_REFRESH_MS = 2800
_RSSI_FLOOR = -95
_RSSI_CEIL = -35


class WifiAnalyzer(App):

    async def run(self, ctx):
        aps = []
        history = []
        last_scan = -100000
        scanning = False

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            now = time.ticks_ms()
            due = select or time.ticks_diff(now, last_scan) >= _REFRESH_MS
            if due:
                scanning = True
                self._draw(ctx.crt, aps, history, scanning)
                try:
                    aps = ctx.wifi.scan()
                except Exception:  # noqa: BLE001
                    aps = []
                history.append(self._counts(aps))
                if len(history) > 16:
                    history.pop(0)
                last_scan = time.ticks_ms()
                scanning = False

            self._draw(ctx.crt, aps, history, scanning)
            await uasyncio.sleep_ms(80)

    def _draw(self, crt, aps, history, scanning):
        crt.begin()
        title = "WiFi Analyzer" if crt.h > 160 else "WIFI ANALYZ"
        crt.text_center(title + ("  SCAN" if scanning else ""), 2, 1, "hi")

        left = 8
        right = crt.w - 8
        top = CELL + 10
        base = min(crt.h // 2, 112)
        span = right - left
        crt.use("dim")
        crt.g.line(left, base, right, base)
        for channel in range(1, _CHANNELS + 1):
            x = left + int((channel - 1) * span / (_CHANNELS - 1))
            crt.use("scan")
            crt.g.line(x, top, x, base)
            if channel in (1, 6, 11, 13):
                crt.text(str(channel), x - 4, base + 3, 1, "mid")

        for ssid, bssid, channel, rssi, secured in reversed(aps[:16]):
            self._lobe(crt, channel, rssi, secured, left, span, top, base)

        peak = _RSSI_FLOOR
        for ap in aps:
            if ap[3] > peak:
                peak = ap[3]
        crt.text("AP {:02d}".format(len(aps)), left, top, 1, "fg")
        crt.text_right("PEAK {}dBm".format(peak), right, top, 1, "mid")
        self._waterfall(crt, history, left, right, base + CELL + 5)
        crt.button_hints(top_left="BACK", top_right="SCAN")
        crt.end()

    def _lobe(self, crt, channel, rssi, secured, left, span, top, base):
        if not 1 <= channel <= _CHANNELS:
            return
        strength = (rssi - _RSSI_FLOOR) / (_RSSI_CEIL - _RSSI_FLOOR)
        strength = max(0.05, min(1.0, strength))
        center = left + (channel - 1) * span / (_CHANNELS - 1)
        width = span * 2.2 / (_CHANNELS - 1)
        height = int((base - top - 4) * strength)
        points = (
            (int(center - width), base),
            (int(center - width / 2), base - height // 2),
            (int(center), base - height),
            (int(center + width / 2), base - height // 2),
            (int(center + width), base),
        )
        crt.use("fg" if secured else "warn")
        for i in range(1, len(points)):
            crt.g.line(
                points[i - 1][0], points[i - 1][1], points[i][0], points[i][1]
            )

    def _waterfall(self, crt, history, left, right, top):
        available = crt.h - top - CELL - 3
        if available < 6:
            return
        rows = min(len(history), available // 4)
        if not rows:
            return
        crt.text("CHANNEL WATERFALL", left, top, 1, "dim")
        top += CELL + 2
        cell_w = max(2, (right - left) // _CHANNELS)
        for row in range(rows):
            counts = history[-rows + row]
            peak = max(counts) or 1
            for channel in range(1, _CHANNELS + 1):
                count = counts[channel]
                crt.use("hi" if count == peak else ("mid" if count else "scan"))
                crt.g.rectangle(
                    left + (channel - 1) * cell_w, top + row * 4, cell_w - 1, 3
                )

    def _counts(self, aps):
        counts = [0] * (_CHANNELS + 1)
        for ap in aps:
            channel = ap[2]
            if 1 <= channel <= _CHANNELS:
                counts[channel] += 1
        return counts
