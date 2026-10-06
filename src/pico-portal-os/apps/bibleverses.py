# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time
import uasyncio  # type: ignore

from . import App

_VERSE_PATH = "/pico-portal-os/apps/bible_verses.txt"


class BibleVerses(App):

    def __init__(self):
        self._state = (time.ticks_ms() ^ 0x5A17) & 0x7FFF

    async def run(self, ctx):
        count = self._count_verses()
        if count:
            index = self._random_index(count, -1)
            reference, verse = self._load_verse(index)
            error = ""
        else:
            index = 0
            reference, verse = "CATALOG", ""
            error = "bible_verses.txt missing or empty"
        scroll = 0
        max_scroll = 0

        while True:
            previous, following, randomize, back = ctx.input.poll()
            if back:
                return
            if count and previous:
                if scroll:
                    scroll -= 1
                else:
                    index = (index - 1) % count
                    reference, verse = self._load_verse(index)
                    scroll = 0
            if count and following:
                if scroll < max_scroll:
                    scroll += 1
                else:
                    index = (index + 1) % count
                    reference, verse = self._load_verse(index)
                    scroll = 0
            if count and randomize:
                index = self._random_index(count, index)
                reference, verse = self._load_verse(index)
                scroll = 0

            max_scroll = self._draw(ctx.crt, reference, verse, error, scroll)
            await uasyncio.sleep_ms(55)

    def _count_verses(self):
        count = 0
        try:
            with open(_VERSE_PATH, "r") as catalog:
                for line in catalog:
                    if "|" in line and not line.startswith("#"):
                        count += 1
        except OSError:
            return 0
        return count

    def _load_verse(self, wanted):
        current = 0
        try:
            with open(_VERSE_PATH, "r") as catalog:
                for line in catalog:
                    if "|" not in line or line.startswith("#"):
                        continue
                    if current == wanted:
                        reference, verse = line.rstrip().split("|", 1)
                        return reference, verse
                    current += 1
        except OSError:
            pass
        return "CATALOG", "Unable to read verse data."

    def _random_index(self, count, current):
        self._state = (self._state * 109 + 1021) & 0x7FFF
        selected = self._state % count
        if count > 1 and selected == current:
            selected = (selected + 1) % count
        return selected

    def _draw(self, crt, reference, verse, error, scroll):
        crt.begin()
        top = crt.ui_title("BIBLE VERSES")
        bottom = crt.ui_bottom()

        reference_scale = crt.fit_scale(reference, crt.w - 16)
        crt.text_center(reference, top, reference_scale, "hi")
        y = top + crt.text_height(reference_scale) + 2

        crt.rule(y - 2, "dim")

        message = error or verse
        pen = "alarm" if error else "fg"
        scale = crt.preferred_scale()
        while True:
            lines = crt.wrap_lines(message, crt.w - 20, scale)
            line_height = crt.text_height(scale) + 2
            if scale <= 1 or len(lines) * line_height <= bottom - y:
                break
            scale = crt.smaller_scale(scale)

        visible = max(1, (bottom - y) // line_height)
        max_scroll = max(0, len(lines) - visible)
        scroll = max(0, min(scroll, max_scroll))
        stop = scroll + visible
        shown = lines[scroll:stop]
        text_height = len(shown) * line_height
        draw_y = y + (
            max(0, (bottom - y - text_height) // 2) if not max_scroll else 0
        )
        for line in shown:
            crt.text_center(line, draw_y, scale, pen)
            draw_y += line_height

        crt.button_hints(
            top_left="BACK",
            top_right="RAND",
            bottom_left="UP" if scroll else "PREV",
            bottom_right="DWN" if scroll < max_scroll else "NEXT",
        )
        crt.end()
        return max_scroll
