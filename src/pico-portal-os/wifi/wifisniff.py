# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time
import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL
from ..radio import estimated_feet, format_distance

_HIST = 40
_RSSI_LO = -95
_RSSI_HI = -35
_RESCAN_MS = 2500


def _norm(rssi):
    f = (rssi - _RSSI_LO) / (_RSSI_HI - _RSSI_LO)
    return 0.0 if f < 0 else (1.0 if f > 1 else f)


def _bars(rssi):
    return (
        4 if rssi >= -55 else (3 if rssi >= -66 else (2 if rssi >= -78 else 1))
    )


class WifiSniff(App):

    async def run(self, ctx):
        aps = await self._scan(ctx)
        last_scan = time.ticks_ms()
        sel = 0
        tracked = None
        hist = []
        sweep = 0.0
        mode = "LIST"

        while True:
            up, down, select, back = ctx.input.poll()
            now = time.ticks_ms()
            due = time.ticks_diff(now, last_scan) > _RESCAN_MS

            if mode == "LIST":
                if back:
                    ctx.wifi.off()
                    return
                if up:
                    sel = (sel - 1) % max(1, len(aps))
                if down:
                    sel = (sel + 1) % max(1, len(aps))
                if select and aps:
                    tracked = aps[sel][1]
                    hist = []
                    mode = "TRACK"
                    continue
                self._draw_list(ctx, aps, sel, due)
                if due:
                    aps = await self._scan(ctx)
                    last_scan = time.ticks_ms()
                    if sel >= len(aps):
                        sel = max(0, len(aps) - 1)

            else:  # TRACK
                if back or select:
                    mode = "LIST"
                    continue
                if up:
                    sel = (sel - 1) % max(1, len(aps))
                    tracked = aps[sel][1]
                    hist = []
                if down:
                    sel = (sel + 1) % max(1, len(aps))
                    tracked = aps[sel][1]
                    hist = []

                cur = None
                for ap in aps:
                    if ap[1] == tracked:
                        cur = ap
                        break
                sweep += 0.3
                self._draw_track(ctx, cur, hist, sweep, due)
                if due:
                    aps = await self._scan(ctx)
                    last_scan = time.ticks_ms()
                    for ap in aps:
                        if ap[1] == tracked:
                            hist.append(ap[3])
                            if len(hist) > _HIST:
                                hist.pop(0)
                            break

            await uasyncio.sleep(0.04)

    async def _scan(self, ctx):
        try:
            return ctx.wifi.scan()
        except Exception:  # noqa: BLE001
            return []

    def _draw_list(self, ctx, aps, sel, scanning):
        crt = ctx.crt
        crt.begin()
        title = "WiFi Sniffer" if crt.h > 160 else "WiFi Sniffer"
        crt.text_center(
            title + "  " + ("SCAN" if scanning else str(len(aps))),
            3,
            1,
            "hi",
        )
        crt.hline(CELL + 5, "dim")

        row_h = CELL + 3
        top_y = CELL + 9
        visible = max(1, (crt.h - top_y - CELL - 2) // row_h)
        start = 0
        if sel >= visible:
            start = sel - visible + 1

        if not aps:
            crt.text("no networks", 8, top_y, 1, "mid")
        for i in range(visible):
            idx = start + i
            if idx >= len(aps):
                break
            ssid, bssid, ch, rssi, sec = aps[idx]
            y = top_y + i * row_h
            pen = "hi" if idx == sel else "mid"
            if idx == sel:
                crt.use("dim")
                crt.g.rectangle(2, y - 1, crt.w - 4, row_h - 1)
            self._signal(crt, 4, y, _bars(rssi))
            crt.text("{:>4}".format(rssi), 26, y, 1, pen)
            name = ssid if ssid else "<hidden>"
            crt.text(name[:15], 62, y, 1, pen)
            marker = "#" if sec else "o"
            crt.text_right("{}{}".format(ch, marker), crt.w - 4, y, 1, pen)

        ctx.lamp.set((0, 120, 200))
        crt.button_hints(
            top_left="BACK",
            top_right="TRACK",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    def _draw_track(self, ctx, cur, hist, sweep, scanning):
        crt = ctx.crt
        crt.begin()
        title = "WiFi Sniffer" if crt.h > 160 else "WiFi Sniffer"
        crt.text_center(title + ("  SCAN" if scanning else ""), 3, 1, "hi")
        crt.hline(CELL + 5, "dim")

        cx = crt.w // 4 + 4
        cy = crt.h // 2 + 4
        r = min(cx - 6, (crt.h - CELL * 3) // 2)

        if cur is None:
            crt.radar(cx, cy, r, 0.0, sweep, "dim")
            crt.text_center("SIGNAL LOST", crt.h // 2, 1, "alarm")
            ctx.lamp.set((200, 40, 20))
        else:
            rssi = cur[3]
            frac = _norm(rssi)
            crt.radar(cx, cy, r, frac, sweep, "fg")
            ctx.lamp.set((int(220 * (1 - frac)), int(220 * frac), 40))

            rx = crt.w // 2 + 6
            crt.text("{}".format(rssi), rx, CELL + 12, 3, "fg")
            crt.text("dBm", rx, CELL + 40, 1, "mid")
            crt.text(
                format_distance(
                    estimated_feet(rssi, reference=-40, exponent=2.4),
                    ctx.config,
                ),
                rx + 42,
                CELL + 40,
                1,
                "hi",
            )

            ssid = cur[0] if cur[0] else "<hidden>"
            crt.text(ssid[:14], rx, CELL + 54, 1, "hi")
            security = "LOCK" if cur[4] else "OPEN"
            crt.text(
                "ch {}  {}".format(cur[2], security), rx, CELL + 66, 1, "mid"
            )

            if crt.h > 160:
                crt.text(cur[1][:17], rx, CELL + 78, 1, "dim")

            gy = min(crt.h - 48, CELL + (94 if crt.h > 160 else 82))
            gw = crt.w - rx - 6
            crt.box(rx, gy, gw, 22, "dim", title="RSSI")
            crt.sparkline(
                rx + 2,
                gy + 3,
                gw - 4,
                16,
                hist,
                "fg",
                scale=_RSSI_HI - _RSSI_LO,
                minimum=_RSSI_LO,
            )

            self._trend(crt, hist, rx, crt.h - CELL * 3)

        crt.button_hints(
            top_left="BACK",
            top_right="LIST",
            bottom_left="PREV",
            bottom_right="NEXT",
        )
        crt.end()

    def _trend(self, crt, hist, x, y):
        if len(hist) < 6:
            crt.text("hold still...", x, y, 1, "dim")
            return
        recent = sum(hist[-3:]) / 3.0
        older = sum(hist[-6:-3]) / 3.0
        delta = recent - older
        if delta > 1.5:
            crt.text("^ CLOSER", x, y, 1, "fg")
        elif delta < -1.5:
            crt.text("v FARTHER", x, y, 1, "warn")
        else:
            crt.text("= STEADY", x, y, 1, "mid")

    def _signal(self, crt, x, y, bars):
        for i in range(4):
            height = 3 + i * 2
            crt.use("hi" if i < bars else "dim")
            crt.g.rectangle(x + i * 5, y + 9 - height, 3, height)
