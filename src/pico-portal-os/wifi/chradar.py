# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL

_CHANNELS = 13  # 2.4GHz channels 1..13
_NONOVERLAP = (1, 6, 11)


class ChannelRadar(App):

    async def run(self, ctx):
        crt = ctx.crt
        counts = [0] * (_CHANNELS + 1)
        total = 0
        best = None
        need_scan = True
        error = None

        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                ctx.wifi.off()
                return
            if select:
                need_scan = True

            if need_scan:
                self._scanning_frame(crt)
                counts = [0] * (_CHANNELS + 1)
                try:
                    aps = ctx.wifi.scan()
                    error = None
                    for ap in aps:
                        ch = ap[2]
                        if 1 <= ch <= _CHANNELS:
                            counts[ch] += 1
                    total = sum(counts)
                    best = self._recommend(counts)
                except Exception as exc:  # noqa: BLE001
                    error = str(exc)
                need_scan = False
                ctx.lamp.set((0, 120, 200))

            crt.begin()
            title = "Channel Radar" if crt.h > 160 else "CH.RADAR"
            crt.text_center("{}  {} APs".format(title, total), 3, 1, "hi")
            crt.hline(CELL + 5, "dim")

            if error:
                crt.text("radio error:", 6, CELL + 12, 1, "alarm")
                crt.text(
                    error, 6, CELL + 12 + CELL + 3, 1, "warn", wrap=crt.w - 12
                )
            else:
                self._graph(crt, counts, best)
                if best is not None:
                    crt.text(
                        "clearest: ch {}".format(best),
                        4,
                        crt.h - 2 * CELL - 6,
                        1,
                        "hi",
                    )

            crt.hline(crt.h - CELL - 6, "dim")
            crt.button_hints(top_left="BACK", top_right="SCAN")
            crt.end()
            await uasyncio.sleep(0.05)

    def _recommend(self, counts):
        best_ch = _NONOVERLAP[0]
        best_load = None
        for ch in _NONOVERLAP:
            load = 0
            for c in range(ch - 2, ch + 3):
                if 1 <= c <= _CHANNELS:
                    load += counts[c]
            if best_load is None or load < best_load:
                best_load = load
                best_ch = ch
        return best_ch

    def _graph(self, crt, counts, best):
        peak = max(counts) if any(counts) else 1
        loads = self._spectral_load(counts)
        load_peak = max(loads) or 1
        top = CELL + 12
        base = crt.h - 3 * CELL - 12
        height = base - top
        span = crt.w - 16
        step = span / _CHANNELS

        crt.hline(base, "dim")
        previous = None
        for ch in range(1, _CHANNELS + 1):
            cx = int(8 + step * (ch - 0.5))
            bw = max(3, int(step) - 3)
            bh = int(height * counts[ch] / peak) if counts[ch] else 0
            if bh:
                pen = (
                    "hi"
                    if ch == best
                    else ("fg" if ch in _NONOVERLAP else "mid")
                )
                crt.use(pen)
                crt.g.rectangle(cx - bw // 2, base - bh, bw, bh)
            if ch in _NONOVERLAP or ch % 2 == 1:
                lpen = "warn" if ch in _NONOVERLAP else "dim"
                label = str(ch)
                crt.text(
                    label, cx - crt.measure(label, 1) // 2, base + 3, 1, lpen
                )
            line_y = base - int(height * loads[ch] / load_peak)
            if previous is not None:
                crt.use("hi")
                crt.g.line(previous[0], previous[1], cx, line_y)
            crt.use("warn" if ch in _NONOVERLAP else "fg")
            crt.g.rectangle(cx - 1, line_y - 1, 3, 3)
            previous = (cx, line_y)

    def _spectral_load(self, counts):
        loads = [0] * (_CHANNELS + 1)
        for channel in range(1, _CHANNELS + 1):
            total = counts[channel] * 3
            if channel > 1:
                total += counts[channel - 1] * 2
            if channel < _CHANNELS:
                total += counts[channel + 1] * 2
            if channel > 2:
                total += counts[channel - 2]
            if channel < _CHANNELS - 1:
                total += counts[channel + 2]
            loads[channel] = total
        return loads

    def _scanning_frame(self, crt):
        crt.begin()
        title = "Channel Radar" if crt.h > 160 else "CH.RADAR"
        crt.text(title, 4, 3, 1, "hi")
        crt.hline(CELL + 5, "dim")
        crt.text_center("SCANNING...", crt.h // 2 - 6, 2, "fg")
        crt.text_center("mapping channels", crt.h // 2 + 14, 1, "mid")
        crt.end()
