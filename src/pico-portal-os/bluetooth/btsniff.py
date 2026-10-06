# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL
from ..radio import estimated_feet, format_distance

_HIST = 48
_RSSI_LO = -100
_RSSI_HI = -40
_LOST_MS = 4000


def _norm(rssi):
    f = (rssi - _RSSI_LO) / (_RSSI_HI - _RSSI_LO)
    return 0.0 if f < 0 else (1.0 if f > 1 else f)


def _bars(rssi):
    return (
        4 if rssi >= -60 else (3 if rssi >= -72 else (2 if rssi >= -84 else 1))
    )


class BtSniff(App):

    async def run(self, ctx):
        if not ctx.ble.start():
            await self._unavailable(ctx)
            return

        sel = 0
        tracked = None
        hist = []
        sweep = 0.0
        mode = "LIST"

        while True:
            up, down, select, back = ctx.input.poll()
            devices = ctx.ble.results()

            if mode == "LIST":
                if back:
                    ctx.ble.stop()
                    ctx.lamp.set((0, 70, 30))
                    return
                if up:
                    sel = (sel - 1) % max(1, len(devices))
                if down:
                    sel = (sel + 1) % max(1, len(devices))
                if select and devices:
                    tracked = devices[sel][0]
                    hist = []
                    mode = "TRACK"
                    continue
                self._draw_list(ctx, devices, sel)

            else:  # TRACK
                if back or select:
                    mode = "LIST"
                    continue
                if up or down:
                    if devices:
                        sel = (sel + (1 if down else -1)) % len(devices)
                        tracked = devices[sel][0]
                        hist = []

                info = ctx.ble.track(tracked) if tracked else None
                device = None
                for candidate in devices:
                    if candidate[0] == tracked:
                        device = candidate
                        break
                if info is not None and info[1] < _LOST_MS:
                    hist.append(info[0])
                    if len(hist) > _HIST:
                        hist.pop(0)
                sweep += 0.35
                self._draw_track(ctx, tracked, device, info, hist, sweep)

            await uasyncio.sleep(0.05)

    def _draw_list(self, ctx, devices, sel):
        crt = ctx.crt
        crt.begin()
        title = "Bluetooth Sniffer" if crt.h > 160 else "BT Sniffer"
        crt.text_center("{}  {}".format(title, len(devices)), 3, 1, "hi")
        crt.hline(CELL + 5, "dim")

        row_h = CELL + 3
        top_y = CELL + 9
        visible = max(1, (crt.h - top_y - CELL - 2) // row_h)
        start = 0
        if sel >= visible:
            start = sel - visible + 1

        if not devices:
            crt.text("listening...", 8, top_y, 1, "mid")
        for i in range(visible):
            idx = start + i
            if idx >= len(devices):
                break
            mac, name, rssi = devices[idx]
            y = top_y + i * row_h
            pen = "hi" if idx == sel else "mid"
            if idx == sel:
                crt.use("dim")
                crt.g.rectangle(2, y - 1, crt.w - 4, row_h - 1)
            self._signal(crt, 4, y, _bars(rssi))
            crt.text("{:>4}".format(rssi), 26, y, 1, pen)
            crt.text((name if name else mac)[:15], 62, y, 1, pen)

        ctx.lamp.set((40, 60, 220))
        crt.button_hints(
            top_left="BACK",
            top_right="TRACK",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    def _draw_track(self, ctx, tracked, device, info, hist, sweep):
        crt = ctx.crt
        crt.begin()
        crt.text_center(
            "Bluetooth Sniffer" if crt.h > 160 else "BT Sniffer", 3, 1, "hi"
        )
        crt.hline(CELL + 5, "dim")

        cx = crt.w // 4 + 4
        cy = crt.h // 2 + 4
        r = min(cx - 6, (crt.h - CELL * 3) // 2)

        lost = info is None or info[1] >= _LOST_MS
        if lost:
            crt.radar(cx, cy, r, 0.0, sweep, "dim")
            ctx.lamp.set((200, 40, 20))
        else:
            rssi = info[0]
            frac = _norm(rssi)
            crt.radar(cx, cy, r, frac, sweep, "fg")
            ctx.lamp.set((int(220 * (1 - frac)), int(220 * frac), 60))

        rx = crt.w // 2 + 6
        if lost:
            crt.text("LOST", rx, CELL + 16, 3, "alarm")
            crt.text("out of range", rx, CELL + 46, 1, "mid")
        else:
            crt.text("{}".format(info[0]), rx, CELL + 12, 3, "fg")
            crt.text("dBm", rx, CELL + 40, 1, "mid")
            crt.text(
                format_distance(
                    estimated_feet(info[0], reference=-59, exponent=2.0),
                    ctx.config,
                ),
                rx + 42,
                CELL + 40,
                1,
                "hi",
            )
            name = device[1] if device and device[1] else "<unnamed>"
            crt.text(name[:17], rx, CELL + 54, 1, "hi")
            crt.text((tracked or "")[:17], rx, CELL + 66, 1, "mid")
            if crt.h > 160:
                crt.text("age {}ms".format(info[1]), rx, CELL + 78, 1, "dim")
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
        delta = sum(hist[-3:]) / 3.0 - sum(hist[-6:-3]) / 3.0
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

    async def _unavailable(self, ctx):
        crt = ctx.crt
        ctx.lamp.set((120, 60, 0))
        while True:
            up, down, select, back = ctx.input.poll()
            if any((up, down, select, back)):
                ctx.lamp.set((0, 70, 30))
                return
            crt.begin()
            crt.text_center(
                "Bluetooth Sniffer" if crt.h > 160 else "BT Sniffer", 3, 1, "hi"
            )
            crt.hline(CELL + 5, "dim")
            crt.text_center("BLUETOOTH", crt.h // 2 - 20, 2, "warn")
            crt.text_center("UNAVAILABLE", crt.h // 2, 2, "warn")
            crt.text_center("not in this firmware", crt.h // 2 + 22, 1, "mid")
            crt.button_hints(top_left="BACK")
            crt.end()
            await uasyncio.sleep(0.05)
