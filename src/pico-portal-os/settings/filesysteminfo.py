# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from ..apps import App
from ..crt import CELL


def _size(value):
    if value >= 1024 * 1024:
        return "{:.2f} MB".format(value / (1024 * 1024))
    if value >= 1024:
        return "{:.1f} KB".format(value / 1024)
    return "{} B".format(value)


class FilesystemInfo(App):

    async def run(self, ctx):
        stats = ctx.sensors.filesystem()
        offset = 0
        max_offset = 0
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                offset = max(0, offset - 1)
            if down:
                offset = min(max_offset, offset + 1)
            if select:
                stats = ctx.sensors.filesystem()
            max_offset = self._draw(ctx.crt, stats, offset)
            await uasyncio.sleep_ms(80)

    def _draw(self, crt, stats, offset):
        crt.begin()
        title = "Filesystem Info" if crt.h > 160 else "FILESYSTEM"
        top = crt.ui_title(title)
        fraction = stats["used"] / stats["total"] if stats["total"] else 0
        bar_h = CELL + 4
        crt.bar(10, top, crt.w - 20, bar_h, fraction, "fg", "dim")
        rows = (
            ("USED %", "{:d}%".format(int(fraction * 100))),
            ("TOTAL", _size(stats["total"])),
            ("USED", _size(stats["used"])),
            ("FREE", _size(stats["free"])),
            ("BLOCK", _size(stats["block_size"])),
            ("FILES", str(stats["files"])),
            ("DIRS", str(stats["directories"])),
            ("LARGEST", _size(stats["largest"])),
        )
        rows_top = top + bar_h + 5
        max_offset = crt.stat_rows(rows, rows_top, crt.ui_bottom(), offset)
        crt.button_hints(
            top_left="BACK",
            top_right="SCAN",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()
        return max_offset
