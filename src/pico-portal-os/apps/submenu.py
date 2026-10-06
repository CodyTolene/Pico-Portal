# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import sys
import uasyncio  # type: ignore

_TRANSIENT_MODULES = (
    "pico-portal-os.apps.keyboard",
    "pico-portal-os.radio",
    "pico-portal-os.savers.catalog",
    "pico-portal-os.savers.effect_pixel",
    "pico-portal-os.savers.effect_sim",
    "pico-portal-os.savers.effect_space",
    "pico-portal-os.savers.effect_text",
    "pico-portal-os.savers.prng",
    "pico-portal-os.settings.clocksettings",
    "ntptime",
    "random",
    "urequests",
)

_MENU_ICON_SIZE = 20
_MENU_MASK_CACHE = {}


def _drop_module(name):
    sys.modules.pop(name, None)
    if "." not in name:
        return
    parent_name, child_name = name.rsplit(".", 1)
    package = sys.modules.get(parent_name)
    if package is not None and hasattr(package, child_name):
        delattr(package, child_name)


async def run_submenu(ctx, title, items):
    sel = 0
    labels, descriptions = _menu_text(ctx.crt, items)
    has_icons = any(len(item) > 5 and item[5] for item in items)
    ctx.idle_saver_allowed = True
    dirty = True
    while True:
        up, down, select, back = ctx.input.poll()
        try:
            idle_seconds = int(ctx.config["screensaver"].get("timeout", 60))
        except (TypeError, ValueError):
            idle_seconds = 60
        if idle_seconds > 0 and ctx.input.idle_ms() >= idle_seconds * 1000:
            labels = None
            descriptions = None
            gc.collect()
            from ..shell import run_idle_screensaver

            await run_idle_screensaver(ctx)
            labels, descriptions = _menu_text(ctx.crt, items)
            dirty = True
            continue
        if back:
            ctx.idle_saver_allowed = False
            return
        if up:
            sel = (sel - 1) % len(items)
            dirty = True
        if down:
            sel = (sel + 1) % len(items)
            dirty = True
        if select:
            ctx.idle_saver_allowed = False
            labels = None
            descriptions = None
            try:
                await _run_item(ctx, items[sel])
            finally:
                labels, descriptions = _menu_text(ctx.crt, items)
                ctx.idle_saver_allowed = True
                dirty = True

        if dirty:
            dirty = False
            _draw(ctx.crt, title, items, labels, descriptions, has_icons, sel)
        await uasyncio.sleep_ms(50)


def _menu_text(crt, items):
    labels = tuple(item[1] if crt.h > 160 else item[0] for item in items)
    descriptions = tuple(
        str(item[4])[:1].upper() + str(item[4])[1:] if len(item) > 4 else ""
        for item in items
    )
    return labels, descriptions


def _draw(crt, title, items, labels, descriptions, has_icons, sel):
    crt.begin()
    top = crt.ui_title(title)
    leading_width = _MENU_ICON_SIZE + 6 if has_icons else 0
    start, visible, row_h = crt.menu_rows(
        labels,
        sel,
        top,
        crt.ui_bottom(),
        x=6,
        descriptions=descriptions,
        leading_width=leading_width,
        min_row_height=_MENU_ICON_SIZE + 4 if has_icons else 0,
    )
    if has_icons:
        for row in range(visible):
            index = start + row
            if index >= len(items):
                break
            item = items[index]
            if len(item) <= 5 or not item[5]:
                continue
            icon_y = top + row * row_h + (row_h - _MENU_ICON_SIZE) // 2
            _draw_theme_mask(
                crt,
                item[5],
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


def _draw_theme_mask(crt, path, left, top, size, pen):
    """Draw a black-background RGB565 icon using the current theme color."""
    runs = _MENU_MASK_CACHE.get(path)
    if runs is None:
        try:
            encoded = bytearray()
            row_size = size * 2
            with open(path, "rb") as image:
                for y in range(size):
                    row = image.read(row_size)
                    if len(row) != row_size:
                        raise OSError("short icon")
                    x = 0
                    while x < size:
                        if row[x * 2] or row[x * 2 + 1]:
                            start = x
                            while x < size and (row[x * 2] or row[x * 2 + 1]):
                                x += 1
                            encoded.append(start)
                            encoded.append(y)
                            encoded.append(x - start)
                        else:
                            x += 1
                if image.read(1):
                    raise OSError("long icon")
            runs = bytes(encoded)
        except Exception:  # noqa: BLE001 - optional, may be missing
            runs = b""
        _MENU_MASK_CACHE[path] = runs
    if not runs:
        return

    crt.use(pen)
    for i in range(0, len(runs), 3):
        crt.g.rectangle(left + runs[i], top + runs[i + 1], runs[i + 2], 1)


async def _run_item(ctx, item):
    name = "pico-portal-os." + item[2]
    module = None
    app = None
    gc.collect()
    try:
        module = __import__(name, None, None, (item[3],))
        app = getattr(module, item[3])()
        await app.run(ctx)
    finally:
        _drop_module(name)
        if app is not None:
            del app
        if module is not None:
            del module
        for transient_name in _TRANSIENT_MODULES:
            _drop_module(transient_name)
        gc.collect()
