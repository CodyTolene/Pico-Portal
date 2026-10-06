# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import os
import sys
import uasyncio  # type: ignore

from ..apps.submenu import _draw_theme_mask
from ..crt import CELL
from ..storage import save_config


_TEMPLATE_DIR = "/templates/login"
_SUCCESS_TEMPLATE_DIR = "/templates/success"
_MENU_ICON_SIZE = 20
_MENU_ITEMS = (
    (
        "START PORTAL",
        "Launch captive portal",
        "start",
        "/pico-portal-os/images/rocket.bin",
    ),
    (
        "AP SETTINGS",
        "SSID and password",
        "settings",
        "/pico-portal-os/images/ap.bin",
    ),
    (
        "PAGE TEMPLATE",
        "Choose an HTML page",
        "page",
        "/pico-portal-os/images/page.bin",
    ),
    (
        "SUCCESS TEMPLATE",
        "Choose response page",
        "success",
        "/pico-portal-os/images/page.bin",
    ),
    (
        "PORTAL LOG",
        "Logged submissions",
        "log",
        "/pico-portal-os/images/log.bin",
    ),
)
_MENU_LABELS = tuple(item[0] for item in _MENU_ITEMS)
_MENU_DESCRIPTIONS = tuple(item[1] for item in _MENU_ITEMS)


class PortalMenu:
    async def run(self, ctx):
        sel = 0
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return "exit"
            if up:
                sel = (sel - 1) % len(_MENU_ITEMS)
            if down:
                sel = (sel + 1) % len(_MENU_ITEMS)
            if select:
                action = _MENU_ITEMS[sel][2]
                if action == "settings":
                    await self._ap_settings(ctx)
                elif action == "page":
                    await self._choose_template(ctx)
                elif action == "log":
                    await self._view_log(ctx)
                elif action == "start":
                    return "start"
                else:
                    await self._choose_success_template(ctx)
            self._draw_menu(ctx, sel)
            await uasyncio.sleep_ms(50)

    def _draw_menu(self, ctx, sel):
        crt = ctx.crt
        crt.begin()
        top = crt.ui_title("Pico Portal" if crt.h > 160 else "PICO PORTAL")
        ssid = str(ctx.config["portal"].get("ssid", "WiFi Setup"))[:24]
        ap_label = "AP: "
        scale = crt.fit_scale(ap_label + ssid, crt.w - 16)
        label_width = crt.measure(ap_label, scale)
        line_width = label_width + crt.measure(ssid, scale)
        left = (crt.w - line_width) // 2
        crt.text(ap_label, left, top, scale, "p_white")
        crt.text(ssid, left + label_width, top, scale, "mid")
        top += crt.text_height(scale) + 4
        start, visible, row_h = crt.menu_rows(
            _MENU_LABELS,
            sel,
            top,
            crt.ui_bottom(),
            x=6,
            descriptions=_MENU_DESCRIPTIONS,
            leading_width=_MENU_ICON_SIZE + 6,
            min_row_height=_MENU_ICON_SIZE + 4,
        )
        for row in range(visible):
            index = start + row
            if index >= len(_MENU_ITEMS):
                break
            icon_y = top + row * row_h + (row_h - _MENU_ICON_SIZE) // 2
            _draw_theme_mask(
                crt,
                _MENU_ITEMS[index][3],
                6,
                icon_y,
                _MENU_ICON_SIZE,
                "hi" if index == sel else "fg",
            )
        crt.button_hints(
            top_left="BACK",
            top_right="SEL",
            bottom_left="UP",
            bottom_right="DWN",
        )
        crt.end()

    async def _choose_template(self, ctx):
        await self._choose_template_from(
            ctx, _TEMPLATE_DIR, "template", "PAGE TEMPLATE"
        )

    async def _choose_success_template(self, ctx):
        await self._choose_template_from(
            ctx,
            _SUCCESS_TEMPLATE_DIR,
            "success_template",
            "SUCCESS PAGE",
            default_name="success.html",
        )

    async def _choose_template_from(
        self, ctx, directory, config_key, title, default_name=""
    ):
        templates = self._template_files(directory)
        if not templates:
            await self._message(ctx, "NO HTML FILES", directory + " is empty")
            return
        current = ctx.config["portal"].get(config_key, default_name)
        sel = templates.index(current) if current in templates else 0
        labels = [self._template_label(name) for name in templates]
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                sel = (sel - 1) % len(templates)
            if down:
                sel = (sel + 1) % len(templates)
            if select:
                ctx.config["portal"][config_key] = templates[sel]
                self._save(ctx)
                return
            crt = ctx.crt
            crt.begin()
            top = crt.ui_title(title)
            crt.menu_rows(labels, sel, top, crt.ui_bottom(), x=6)
            crt.button_hints(
                top_left="BACK",
                top_right="SEL",
                bottom_left="UP",
                bottom_right="DWN",
            )
            crt.end()
            await uasyncio.sleep_ms(50)

    async def _ap_settings(self, ctx):
        from ..apps.keyboard import edit_text

        try:
            ssid = await edit_text(
                ctx,
                "PORTAL SSID",
                str(ctx.config["portal"].get("ssid", "WiFi Setup")),
                max_length=32,
            )
            if not ssid:
                return
            password = await edit_text(
                ctx,
                "AP PASSWORD",
                str(ctx.config["portal"].get("password", "")),
                secret=True,
                max_length=63,
            )
            if password is None:
                return
            if password and len(password) < 8:
                await self._message(
                    ctx, "PASSWORD TOO SHORT", "use 8+ or leave blank"
                )
                return
            ctx.config["portal"]["ssid"] = ssid
            ctx.config["portal"]["password"] = password
            self._save(ctx)
        finally:
            del edit_text
            sys.modules.pop("pico-portal-os.apps.keyboard", None)
            package = sys.modules.get("pico-portal-os.apps")
            if package is not None and hasattr(package, "keyboard"):
                delattr(package, "keyboard")
            gc.collect()

    def _template_files(self, directory):
        templates = []
        try:
            names = os.listdir(directory)
        except OSError:
            return templates
        for name in names:
            if not self._valid_template_name(name):
                continue
            try:
                if os.stat(directory + "/" + name)[0] & 0x4000:
                    continue
            except OSError:
                continue
            templates.append(name)
        templates.sort()
        return templates

    def _valid_template_name(self, name):
        if not isinstance(name, str) or len(name) <= 4:
            return False
        lower = name.lower()
        valid_suffix = lower.endswith(".html") or lower.endswith(".htm")
        return valid_suffix and "/" not in name and "\\" not in name

    def _template_label(self, name):
        return name[:-5] if name.lower().endswith(".html") else name[:-4]

    def _save(self, ctx):
        try:
            save_config(ctx.config)
        except OSError:
            pass

    async def _message(self, ctx, title, detail):
        await ctx.lamp.feedback("warning")
        ctx.lamp.status("warning")
        end = 0
        try:
            while end < 1400:
                _up, _down, _select, back = ctx.input.poll()
                if back:
                    return
                crt = ctx.crt
                crt.begin()
                crt.text_center(title, crt.h // 2 - CELL, 1, "alarm")
                crt.text_center(
                    crt.clip_text(detail, crt.w - 16, 1),
                    crt.h // 2 + 5,
                    1,
                    "mid",
                )
                crt.end()
                await uasyncio.sleep_ms(50)
                end += 50
        finally:
            ctx.lamp.status("idle")

    async def _view_log(self, ctx):
        crt = ctx.crt
        lines = self._read_log_lines(crt)
        content_top = 2 * CELL + 9
        row_h = CELL + 3
        visible = max(1, (crt.ui_bottom() - content_top) // row_h)
        max_off = max(0, len(lines) - visible)
        offset = max_off
        while True:
            up, down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                offset = max(0, offset - 1)
            if down:
                offset = min(max_off, offset + 1)
            if select and lines and await self._confirm_clear_log(ctx):
                try:
                    with open("/portal.log", "w") as log:
                        log.write("")
                    lines = []
                    max_off = 0
                    offset = 0
                except OSError:
                    await self._message(
                        ctx, "CLEAR FAILED", "unable to write log"
                    )
            crt.begin()
            crt.text_center("PORTAL LOG", 3, 1, "hi")
            crt.text_center("LOGGED VALUES BELOW", CELL + 6, 1, "warn")
            stop = offset + visible
            for index, line in enumerate(lines[offset:stop]):
                crt.text(
                    line,
                    6,
                    content_top + index * row_h,
                    1,
                    "mid",
                )
            if not lines:
                crt.text_center("NO FORM EVENTS", crt.h // 2, 1, "dim")
            crt.button_hints(
                top_left="BACK",
                top_right="CLEAR" if lines else None,
                bottom_left="UP" if offset else None,
                bottom_right="DWN" if offset < max_off else None,
            )
            crt.end()
            await uasyncio.sleep_ms(80)

    async def _confirm_clear_log(self, ctx):
        """Require an explicit second action before erasing the portal log."""
        while True:
            _up, _down, select, back = ctx.input.poll()
            if back:
                return False
            if select:
                return True

            crt = ctx.crt
            crt.begin()
            top = crt.ui_title("CLEAR PORTAL LOG")
            crt.text_center("ARE YOU SURE?", top + 12, 2, "warn")
            crt.text_center("THIS CANNOT BE UNDONE", top + 40, 1, "dim")
            crt.button_hints(top_left="CANCEL", top_right="YES")
            crt.end()
            await uasyncio.sleep_ms(80)

    def _read_log_lines(self, crt):
        """Read all saved events and wrap every character for the log view."""
        lines = []
        try:
            with open("/portal.log", "r") as log:
                for line in log:
                    lines.extend(self._wrap_log_entry(crt, line))
        except OSError:
            pass
        return lines

    def _wrap_log_entry(self, crt, text):
        """Wrap words or long unbroken values, indenting continuation lines."""
        remaining = str(text).strip()
        if not remaining:
            return [""]
        lines = []
        indent = "  "
        width = crt.w - 12
        while remaining:
            prefix = indent if lines else ""
            available = width - crt.measure(prefix, 1)
            end = len(remaining)
            while end > 1 and crt.measure(remaining[:end], 1) > available:
                end -= 1
            if end < len(remaining):
                space = remaining.rfind(" ", 0, end + 1)
                if space > 0:
                    end = space
            piece = remaining[:end].rstrip()
            lines.append(prefix + piece)
            remaining = remaining[end:].lstrip()
        return lines
