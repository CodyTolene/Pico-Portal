# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL

_SAMPLE_MS = 2500
_LOST_MS = 8000  # drop AP after
_MAX_EVENTS = 6
_HIST = 56


def _fmt_ts(ms):
    s = ms // 1000
    return "{:02d}:{:02d}".format((s // 60) % 100, s % 60)


class NetWatch(App):

    async def run(self, ctx):
        known = {}  # bssid
        events = []  # Timestamp, kind, and text. Newest first
        counts = []  # AP count history
        aps = []
        last_sample = -100000

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                ctx.wifi.off()
                return
            now = time.ticks_ms()
            due = select or time.ticks_diff(now, last_sample) > _SAMPLE_MS

            self._draw(ctx, aps, events, counts, due)

            if due:
                aps = await self._scan(ctx)
                last_sample = time.ticks_ms()
                self._digest(ctx, aps, known, events, counts)

            await uasyncio.sleep(0.05)

    async def _scan(self, ctx):
        try:
            return ctx.wifi.scan()
        except Exception:  # noqa: BLE001
            return []

    def _digest(self, ctx, aps, known, events, counts):
        now = time.ticks_ms()
        ts = ctx.sensors.uptime_ms()
        for ssid, bssid, ch, rssi, secured in aps:
            name = ssid if ssid else "<hidden>"
            if bssid not in known:
                events.insert(0, (ts, "+", name))
                if not secured:
                    events.insert(0, (ts, "!", name + " OPEN"))
            known[bssid] = [now, name]

        for bssid in list(known.keys()):
            if time.ticks_diff(now, known[bssid][0]) > _LOST_MS:
                events.insert(0, (ts, "-", known[bssid][1]))
                del known[bssid]

        del events[_MAX_EVENTS:]
        counts.append(len(aps))
        if len(counts) > _HIST:
            counts.pop(0)

    def _draw(self, ctx, aps, events, counts, sampling):
        crt = ctx.crt
        ctx.lamp.set((0, 120, 200) if sampling else (0, 80, 90))
        crt.begin()

        title = "Network Monitor" if crt.h > 160 else "NET MON"
        crt.text_center(title + ("  SMPL" if sampling else ""), 3, 1, "hi")
        crt.hline(CELL + 5, "dim")

        # live AP count & activity graph
        crt.text("{}".format(len(aps)), 6, 16, 3, "fg")
        nx = 6 + crt.measure("{}".format(len(aps)), 3) + 3
        crt.text("APs", nx, 20, 1, "mid")
        crt.text("beacons", nx, 32, 1, "dim")

        gx = crt.w // 2 + 8
        gy = 16
        gw = crt.w - gx - 6
        gh = 24
        crt.box(gx, gy, gw, gh, "dim")
        if counts:
            peak = max(counts) or 1
            crt.sparkline(
                gx + 1, gy + 1, gw - 2, gh - 2, counts, "fg", scale=peak
            )

        busy = self._busiest(aps)
        opens = sum(1 for ap in aps if not ap[4])
        crt.text(
            "busy ch {}".format(busy) if busy else "busy ch --", 6, 46, 1, "mid"
        )
        crt.text_right(
            "{} open".format(opens),
            crt.w - 6,
            46,
            1,
            "alarm" if opens else "dim",
        )

        self._channel_strip(crt, aps, 58)

        # event log
        crt.hline(76, "dim")
        row_h = CELL + 2
        top = 80
        pens = {"+": "fg", "-": "dim", "!": "alarm"}
        max_rows = max(1, (crt.h - top - CELL) // row_h)
        for i in range(min(max_rows, len(events))):
            ts, kind, text = events[i]
            y = top + i * row_h
            crt.text(_fmt_ts(ts), 6, y, 1, "dim")
            crt.text(kind, 44, y, 1, pens.get(kind, "mid"))
            crt.text(text[:18], 52, y, 1, pens.get(kind, "mid"))

        crt.button_hints(top_left="BACK", top_right="SAMPLE")
        crt.end()

    def _channel_strip(self, crt, aps, base):
        counts = [0] * 14
        for ap in aps:
            if 1 <= ap[2] <= 13:
                counts[ap[2]] += 1
        peak = max(counts) or 1
        step = (crt.w - 16) / 13
        for channel in range(1, 14):
            x = int(8 + (channel - 1) * step)
            height = 2 + int(12 * counts[channel] / peak)
            crt.use(
                "hi" if counts[channel] == peak and counts[channel] else "mid"
            )
            crt.g.rectangle(
                x, base + 14 - height, max(2, int(step) - 2), height
            )
        crt.text("1", 6, base + 15, 1, "dim")
        crt.text_right("13", crt.w - 5, base + 15, 1, "dim")

    def _busiest(self, aps):
        counts = {}
        for ap in aps:
            ch = ap[2]
            counts[ch] = counts.get(ch, 0) + 1
        best = None
        best_n = 0
        for ch, n in counts.items():
            if n > best_n:
                best_n = n
                best = ch
        return best
