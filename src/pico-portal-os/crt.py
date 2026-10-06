# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import math
import time

THEMES = {
    "green": {
        "bg": (0, 8, 3),
        "scan": (0, 24, 11),
        "dim": (0, 70, 32),
        "mid": (0, 150, 70),
        "fg": (30, 240, 120),
        "hi": (170, 255, 195),
    },
    "amber": {
        "bg": (10, 5, 0),
        "scan": (28, 14, 0),
        "dim": (95, 48, 0),
        "mid": (175, 92, 0),
        "fg": (255, 176, 32),
        "hi": (255, 228, 165),
    },
    "cyan": {
        "bg": (0, 7, 10),
        "scan": (0, 22, 28),
        "dim": (0, 70, 85),
        "mid": (0, 150, 175),
        "fg": (35, 225, 245),
        "hi": (185, 250, 255),
    },
    "blue": {
        "bg": (2, 4, 14),
        "scan": (8, 15, 36),
        "dim": (30, 55, 110),
        "mid": (55, 105, 205),
        "fg": (90, 165, 255),
        "hi": (200, 225, 255),
    },
    "purple": {
        "bg": (9, 2, 12),
        "scan": (28, 8, 34),
        "dim": (85, 28, 105),
        "mid": (165, 55, 205),
        "fg": (225, 95, 255),
        "hi": (245, 205, 255),
    },
    "red": {
        "bg": (12, 2, 2),
        "scan": (34, 7, 7),
        "dim": (105, 25, 22),
        "mid": (195, 55, 42),
        "fg": (255, 100, 72),
        "hi": (255, 215, 195),
    },
    "white": {
        "bg": (5, 6, 7),
        "scan": (20, 22, 24),
        "dim": (75, 80, 85),
        "mid": (145, 155, 165),
        "fg": (220, 228, 235),
        "hi": (255, 255, 255),
    },
}

THEME_NAMES = ("amber", "blue", "cyan", "green", "purple", "red", "white")

_ACCENTS = {
    "warn": (255, 188, 40),
    "alarm": (255, 74, 52),
    "black": (0, 0, 0),
}

_PREVIEW_COLORS = {
    "p_red": (255, 0, 0),
    "p_orange": (255, 128, 0),
    "p_yellow": (255, 255, 0),
    "p_green": (0, 255, 0),
    "p_cyan": (0, 255, 255),
    "p_blue": (0, 64, 255),
    "p_purple": (190, 0, 255),
    "p_white": (255, 255, 255),
    "p_black": (0, 0, 0),
}

CELL = 8


class CRT:
    def __init__(self, screen, config):
        self.screen = screen
        self.g = screen.graphics
        self.w = screen.width
        self.h = screen.height
        self.base_brightness = screen.base_brightness
        self.config = config
        self.g.set_font("bitmap8")

        self.pen = {}
        self._theme_pens = {}
        self._accent_pens = {
            name: self.g.create_pen(*rgb) for name, rgb in _ACCENTS.items()
        }
        self._preview_pens = {
            name: self.g.create_pen(*rgb)
            for name, rgb in _PREVIEW_COLORS.items()
        }
        self.set_theme(config["display"].get("theme", "green"))

        self.scanlines_on = config["display"].get("scanlines", True)

    def set_theme(self, name):
        """Apply a phosphor palette immediately and return its resolved name."""
        if name not in THEMES:
            name = "green"
        if name not in self._theme_pens:
            self._theme_pens[name] = {
                pen_name: self.g.create_pen(*rgb)
                for pen_name, rgb in THEMES[name].items()
            }
        self.pen = dict(self._theme_pens[name])
        self.pen.update(self._accent_pens)
        self.pen.update(self._preview_pens)
        return name

    def preview_pen(self, rgb):
        """
        Return a fixed nearest-color pen without consuming P8 palette slots.
        """
        best_name = "p_black"
        best_distance = None
        for name, color in _PREVIEW_COLORS.items():
            distance = sum(
                (
                    (rgb[0] - color[0]) * (rgb[0] - color[0]),
                    (rgb[1] - color[1]) * (rgb[1] - color[1]),
                    (rgb[2] - color[2]) * (rgb[2] - color[2]),
                )
            )
            if best_distance is None or distance < best_distance:
                best_name = name
                best_distance = distance
        return self.pen[best_name]

    def set_scanlines(self, enabled):
        self.scanlines_on = bool(enabled)

    def set_brightness(self, level):
        self.screen.set_brightness(level)
        self.base_brightness = self.screen.base_brightness

    def use(self, name):
        self.g.set_pen(self.pen[name])

    def begin(self):
        """
        Start a frame: clear to background and lay down the scanline texture.
        """
        self.use("bg")
        self.g.clear()
        if self.scanlines_on:
            self.use("scan")
            y = 0
            while y < self.h:
                self.g.line(0, y, self.w - 1, y)
                y += 3

    def begin_black(self):
        """Start an effect-free, true-black frame for the opening logo."""
        self.use("black")
        self.g.clear()

    def end(self):
        """Finish a frame and push it to the panel."""
        self.g.update()

    def _text_scale(self, scale):
        """Round a UI scale down to a whole bitmap-font multiple."""
        return max(1.0, float(int(max(1.0, float(scale)) + 0.001)))

    def supported_text_pixels(self):
        """Return the UI glyph heights bitmap8 can render: 1x and 2x."""
        return (8, 16)

    def text_pixels(self):
        """Return the configured base UI glyph height, safely normalized."""
        try:
            pixels = int(self.config["display"].get("font_px", 8))
        except (TypeError, ValueError):
            pixels = 8
        supported = self.supported_text_pixels()
        nearest = supported[0]
        distance = abs(nearest - pixels)
        for candidate in supported[1:]:
            candidate_distance = abs(candidate - pixels)
            if candidate_distance <= distance:
                nearest = candidate
                distance = candidate_distance
        return nearest

    def text_height(self, scale=1):
        """Return the actual integer pixel height reserved for text."""
        return max(CELL, int(CELL * self._text_scale(scale)))

    def smaller_scale(self, scale):
        """Step a font down one whole multiple, never below 1x."""
        return max(1.0, self._text_scale(scale) - 1.0)

    def measure(self, text, scale=1):
        return self.g.measure_text(text, self._text_scale(scale))

    def preferred_scale(self):
        """Resolve the global pixel-height preference to a draw scale."""
        return self.text_pixels() / CELL

    def fit_scale(self, text, max_width):
        """Honor UI size, then shrink only as needed to keep text on-screen."""
        scale = self.preferred_scale()
        while scale > 1 and self.measure(text, scale) > max_width:
            scale = self.smaller_scale(scale)
        return scale

    def fit_scale_many(self, texts, max_width):
        """Use one consistent scale for a related group of labels."""
        scale = self.preferred_scale()
        while scale > 1:
            if all(self.measure(text, scale) <= max_width for text in texts):
                break
            scale = self.smaller_scale(scale)
        return scale

    def ui_top(self, gap=3):
        """First safe row below globally scaled top button hints."""
        return self.text_height(self.preferred_scale()) + gap

    def ui_bottom(self, gap=3):
        """Last safe coordinate above globally scaled bottom button hints."""
        return self.h - self.text_height(self.preferred_scale()) - gap

    def ui_title(self, text, pen="hi"):
        """Draw a scaled page title below the top control-hint row."""
        scale = self.fit_scale(text, self.w - 12)
        y = self.ui_top()
        self.text_center(text, y, scale, pen)
        bottom = y + self.text_height(scale)
        self.rule(bottom + 2, "dim")
        return bottom + 6

    def wrap_lines(self, text, max_width, scale=1):
        """Return word-wrapped lines using actual bitmap-font measurements."""
        lines = []
        line = ""
        for word in str(text).split():
            candidate = word if not line else line + " " + word
            if line and self.measure(candidate, scale) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines or [""]

    def clip_text(self, text, max_width, scale=1):
        """Clip a single-line label with an ASCII ellipsis at a fixed scale."""
        text = str(text)
        if self.measure(text, scale) <= max_width:
            return text
        suffix = "..."
        while text and self.measure(text + suffix, scale) > max_width:
            text = text[:-1]
        return text + suffix if text else suffix

    def text(self, text, x, y, scale=1, pen="fg", wrap=0):
        self.use(pen)
        draw_scale = self._text_scale(scale)
        self.g.text(text, int(x), int(y), wrap if wrap else self.w, draw_scale)

    def text_center(self, text, y, scale=1, pen="fg"):
        x = (self.w - self.measure(text, scale)) // 2
        self.text(text, x, y, scale, pen)

    def text_right(self, text, x_right, y, scale=1, pen="fg"):
        x = x_right - self.measure(text, scale)
        self.text(text, x, y, scale, pen)

    def stat_rows(self, rows, top, bottom, offset=0):
        """Draw scrollable, globally scaled label/value telemetry rows."""
        scale = self.preferred_scale()
        text_h = self.text_height(scale)
        stacked = text_h > CELL
        row_h = 2 * text_h + 5 if stacked else text_h + 5
        visible = max(1, (bottom - top) // row_h)
        max_offset = max(0, len(rows) - visible)
        offset = max(0, min(offset, max_offset))
        for row in range(visible):
            index = offset + row
            if index >= len(rows):
                break
            label, value = rows[index]
            y = top + row * row_h
            label_scale = self.fit_scale(label, self.w - 20)
            value_scale = self.fit_scale(value, self.w - 20)
            self.text(label, 10, y, label_scale, "dim")
            value_y = y + self.text_height(label_scale) + 2 if stacked else y
            self.text_right(value, self.w - 10, value_y, value_scale, "fg")
        if offset > 0:
            self.text_right("^", self.w - 3, top, 1, "dim")
        if offset < max_offset:
            self.text_right("v", self.w - 3, bottom - CELL, 1, "dim")
        return max_offset

    def menu_rows(
        self,
        labels,
        selected,
        top,
        bottom,
        x=6,
        descriptions=None,
        leading_width=0,
        min_row_height=0,
    ):
        """Draw the shared highlight list used by every menu."""
        labels = tuple(str(label) for label in labels)
        scale = self.preferred_scale()
        has_descriptions = descriptions is not None
        available_h = max(1, bottom - top)

        while True:
            text_h = self.text_height(scale)
            text_x = x + leading_width
            max_width = self.w - text_x - x
            words_fit = all(
                self.measure(word, scale) <= max_width
                for label in labels
                for word in (label.split() or ("",))
            )
            wrapped_labels = []
            label_lines = 1
            for label in labels:
                lines = self.wrap_lines(label, max_width, scale)
                if len(lines) > 2:
                    lines = [lines[0], " ".join(lines[1:])]
                lines = tuple(
                    self.clip_text(line, max_width, scale) for line in lines
                )
                wrapped_labels.append(lines)
                label_lines = max(label_lines, len(lines))
            row_h = text_h * label_lines + 6
            if has_descriptions:
                row_h += text_h + 2
            row_h = max(row_h, min_row_height)
            if scale <= 1 or (words_fit and row_h <= available_h):
                break
            scale = self.smaller_scale(scale)
        visible = max(1, (bottom - top) // row_h)
        start = max(0, min(selected - visible + 1, len(labels) - visible))
        for row in range(visible):
            index = start + row
            if index >= len(labels):
                break
            y = top + row * row_h
            is_selected = index == selected
            if is_selected:
                self.use("mid")
                self.g.rectangle(x - 4, y, self.w - 2 * x + 8, row_h - 2)
            for line_index, line in enumerate(wrapped_labels[index]):
                self.text(
                    line,
                    text_x,
                    y + 2 + line_index * self.text_height(scale),
                    scale,
                    "bg" if is_selected else "fg",
                )
            if has_descriptions:
                description = self.clip_text(
                    descriptions[index],
                    max_width,
                    scale,
                )
                self.text(
                    description,
                    text_x,
                    y + self.text_height(scale) * label_lines + 4,
                    scale,
                    "bg" if is_selected else "dim",
                )
        if start > 0:
            self.text_right("^", self.w - 3, top, 1, "dim")
        if start + visible < len(labels):
            self.text_right("v", self.w - 3, bottom - CELL, 1, "dim")
        return start, visible, row_h

    def cursor(self, x, y, scale=1, pen="fg", on=True):
        """A solid block cursor, one character cell wide."""
        if not on:
            return
        self.use(pen)
        height = self.text_height(scale)
        width = max(1, self.measure("M", scale))
        self.g.rectangle(int(x), int(y), int(width), int(height))

    def blink(self, period_ms=530):
        """True/False square wave for cursors and warnings."""
        return (time.ticks_ms() // period_ms) % 2 == 0

    def hline(self, y, pen="dim", x=0, x2=None):
        self.use(pen)
        self.g.line(
            int(x), int(y), int(self.w - 1 if x2 is None else x2), int(y)
        )

    def rule(self, y, pen="dim"):
        """A dashed divider line, terminal-report style."""
        self.use(pen)
        x = 0
        while x < self.w:
            self.g.rectangle(x, int(y), min(3, self.w - x), 1)
            x += 6

    def box(self, x, y, w, h, pen="dim", title=None, title_pen="fg"):
        """A hollow rectangle panel with an optional inset title label."""
        x, y, w, h = int(x), int(y), int(w), int(h)
        self.use(pen)
        self.g.line(x, y, x + w, y)
        self.g.line(x, y + h, x + w, y + h)
        self.g.line(x, y, x, y + h)
        self.g.line(x + w, y, x + w, y + h)
        if title:
            label = " " + title + " "
            tw = self.measure(label, 1)
            self.use("bg")
            self.g.rectangle(x + 6, y - 3, tw, CELL - 1)
            self.text(label, x + 6, y - 4, 1, title_pen)

    def bar(self, x, y, w, h, frac, pen="fg", track="dim"):
        """A horizontal meter: a track outline with a filled proportion."""
        x, y, w, h = int(x), int(y), int(w), int(h)
        frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
        self.use(track)
        self.g.line(x, y, x + w, y)
        self.g.line(x, y + h, x + w, y + h)
        self.g.line(x, y, x, y + h)
        self.g.line(x + w, y, x + w, y + h)
        fill = int((w - 2) * frac)
        if fill > 0:
            self.use(pen)
            self.g.rectangle(x + 1, y + 1, fill, h - 1)

    def sparkline(self, x, y, w, h, series, pen="fg", scale=1.0, minimum=0.0):
        """Draw a tiny graph, optionally scaling raw samples by `scale`."""
        n = len(series)
        if n < 2 or scale <= 0:
            return
        x, y, w, h = int(x), int(y), int(w), int(h)
        self.use(pen)
        step = w / (n - 1)
        prev_x = x
        first = (series[0] - minimum) / scale
        first = max(0.0, min(1.0, first))
        prev_y = y + h - int(first * h)
        for i in range(1, n):
            cx = x + int(step * i)
            frac = (series[i] - minimum) / scale
            frac = max(0.0, min(1.0, frac))
            cy = y + h - int(frac * h)
            self.g.line(prev_x, prev_y, cx, cy)
            prev_x, prev_y = cx, cy

    def button_hints(
        self,
        top_left=None,
        top_right=None,
        bottom_left=None,
        bottom_right=None,
        pen="mid",
    ):
        """Draw compact tags in the four corners that point at the buttons.

        Pass a short action word per physical position; omit unused controls.
        Case labels are deliberately hidden because they are not user-visible.
        """
        scale = self.preferred_scale()
        while scale > 1:
            top_width = self._tag_width(top_left, scale) + self._tag_width(
                top_right, scale
            )
            bottom_width = self._tag_width(
                bottom_left, scale
            ) + self._tag_width(bottom_right, scale)
            if max(top_width, bottom_width) <= self.w - 4:
                break
            scale = self.smaller_scale(scale)
        by = self.h - self.text_height(scale)
        if top_left:
            self._corner_tag(top_left, 2, 1, "l", pen, scale)
        if top_right:
            self._corner_tag(top_right, self.w - 2, 1, "r", pen, scale)
        if bottom_left:
            self._corner_tag(bottom_left, 2, by, "l", pen, scale)
        if bottom_right:
            self._corner_tag(bottom_right, self.w - 2, by, "r", pen, scale)

    def _tag_width(self, action, scale):
        return self.measure(action, scale) + 4 if action else 0

    def _corner_tag(self, action, x, y, align, pen, scale):
        tag_w = self._tag_width(action, scale)
        if align == "r":
            x -= tag_w
        self.use(pen)
        self.g.rectangle(x, y - 1, tag_w, self.text_height(scale) + 1)
        self.text(action, x + 2, y, scale, "bg")

    def radar(self, cx, cy, r, frac, sweep, pen="fg"):
        """
        A 'signal proximity' radar: reference rings, a decorative rotating
        sweep, and a blob at the center that grows as the signal strengthens.

        This is strength-as-range, NOT a bearing - one antenna can't sense
        direction, so nothing here claims an angle. `frac` is 0..1
        (1=strongest), `sweep` is the sweep angle in radians.
        """
        frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
        self._ring(cx, cy, r, "mid")
        self._ring(cx, cy, r * 3 // 4, "dim")
        self._ring(cx, cy, r // 2, "dim")
        self._ring(cx, cy, r // 4, "dim")

        self.use("scan")
        self.g.line(cx - r, cy, cx + r, cy)
        self.g.line(cx, cy - r, cx, cy + r)
        for tick in range(-r, r + 1, max(4, r // 4)):
            self.g.line(cx + tick, cy - 2, cx + tick, cy + 2)
            self.g.line(cx - 2, cy + tick, cx + 2, cy + tick)
        for offset, sweep_pen in ((-0.18, "dim"), (-0.09, "mid"), (0, "fg")):
            angle = sweep + offset
            ex = cx + int(r * math.cos(angle))
            ey = cy + int(r * math.sin(angle))
            self.use(sweep_pen)
            self.g.line(cx, cy, ex, ey)

        segments = 8
        lit = int(frac * segments + 0.5)
        for i in range(segments):
            self.use(pen if i < lit else "dim")
            self.g.rectangle(cx - r + i * (2 * r // segments), cy + r + 3, 3, 3)

        self.use(pen)
        self.g.circle(cx, cy, max(2, int(frac * r // 3)))
        self.use("hi")
        self.g.circle(cx, cy, 2)

    def _ring(self, cx, cy, r, pen):
        if r < 2:
            return
        self.use(pen)
        steps = max(10, int(r * 1.2))
        for i in range(steps):
            ang = 2.0 * math.pi * i / steps
            self.g.pixel(
                cx + int(r * math.cos(ang)), cy + int(r * math.sin(ang))
            )


def lerp_rgb(a, b, t):
    """Blend two (r,g,b) tuples; t in 0..1. Handy for temperature colors etc."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )
