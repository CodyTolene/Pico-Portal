# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import sys
import time
import uasyncio  # type: ignore

from . import NAME, VERSION
from .crt import CELL
from .hardware import reset
from .storage import local_time, save_config
from .units import format_clock, format_temperature

APPS = (
    (
        "BT TOOLS",
        "Bluetooth Tools",
        "Bluetooth LE utilities",
        "bluetooth.bttools",
        "BluetoothTools",
    ),
    (
        "WIFI TOOLS",
        "WiFi Tools",
        "Wireless network utilities",
        "wifi.wifitools",
        "WifiTools",
    ),
    (
        "APPS",
        "Apps",
        "Everyday pocket utilities",
        "apps.apps",
        "Apps",
    ),
    ("GAMES", "Games", "Arcade and tabletop games", "games.games", "Games"),
    (
        "SCREENS",
        "Screensavers",
        "Idle screen visuals",
        "savers.screensavers",
        "Screensavers",
    ),
    (
        "SYS TOOLS",
        "System Tools",
        "Device diagnostics and information",
        "systemtools",
        "SystemTools",
    ),
    (
        "SETTINGS",
        "Settings",
        "WiFi, display, and device setup",
        "settings.settings",
        "Settings",
    ),
    ("ABOUT", "About", "System info and credits", "about", "About"),
)

SCREENSAVER_INDEX = 4

_MENU_ICON_PATHS = (
    "/pico-portal-os/images/bluetooth.bin",
    "/pico-portal-os/images/broadcast.bin",
    "/pico-portal-os/images/apps.bin",
    "/pico-portal-os/images/games.bin",
    "/pico-portal-os/images/screens.bin",
    "/pico-portal-os/images/tools.bin",
    "/pico-portal-os/images/settings.bin",
    "/pico-portal-os/images/about.bin",
)

_TRANSIENT_MODULES = (
    "pico-portal-os.apps.keyboard",
    "pico-portal-os.apps.submenu",
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


def _drop_module(name):
    """Remove a dynamic module and its parent-package reference."""
    sys.modules.pop(name, None)
    if "." not in name:
        return
    parent_name, child_name = name.rsplit(".", 1)
    package = sys.modules.get(parent_name)
    if package is not None and hasattr(package, child_name):
        delattr(package, child_name)


def _release_transients():
    """Reclaim helpers retained by a finished app on the Pico's small heap."""
    for name in _TRANSIENT_MODULES:
        _drop_module(name)
    gc.collect()


def _load_app(spec):
    """Construct one launcher app without loading all app modules at boot."""
    name = "pico-portal-os." + spec[3]
    module = None
    gc.collect()
    try:
        module = __import__(name, None, None, (spec[4],))
        return getattr(module, spec[4])()
    except Exception:
        _drop_module(name)
        if module is not None:
            del module
        gc.collect()
        raise


def _unload_app(spec):
    """Release an app module after exit so another app has room to run."""
    name = "pico-portal-os." + spec[3]
    _drop_module(name)
    _release_transients()


def _app_label(crt, spec):
    return spec[1] if crt.h > 160 else spec[0]


IDLE_LAMP = (0, 70, 30)
FRAME = 0.05
_MENU_LOGO_SIZE = 20
_MENU_ICON_SIZE = 20
_MENU_LOGO_PENS = None
_MENU_LOGO_RUNS = None
_MENU_MASK_CACHE = {}


class Input:
    """Map physical positions to (up, down, select, back) once per frame.

    Portrait layout: bottom-left=up, bottom-right=down, top-right=select,
    top-left=back. The case hides the board's A/B/X/Y markings.
    """

    def __init__(self, buttons):
        self.b = buttons
        self.last_activity = time.ticks_ms()

    def poll(self):
        state = (
            self.b.y.read(),
            self.b.x.read(),
            self.b.a.read(),
            self.b.b.read(),
        )
        if any(state):
            self.last_activity = time.ticks_ms()
        return state

    def idle_ms(self):
        return time.ticks_diff(time.ticks_ms(), self.last_activity)

    def wake(self):
        """Mark fresh activity and drop input queued during a transition."""
        self.b.flush()
        self.last_activity = time.ticks_ms()


class Context:
    """
    Everything an app needs, passed to run(). One instance for the session.
    """

    def __init__(
        self,
        crt,
        lamp,
        inp,
        sensors,
        config,
        wifi,
        ble,
    ):
        self.crt = crt
        self.lamp = lamp
        self.input = inp
        self.sensors = sensors
        self.config = config
        self.wifi = wifi
        self.ble = ble
        self.wifi_config = config["wifi"]
        self.weather_config = config["weather"]
        self.clock_config = config["clock"]
        self.idle_saver_allowed = False


async def heartbeat_task(heart, config):
    """Drive the digital onboard status LED from live settings."""
    while True:
        mode = config["led"].get("status", "heartbeat")
        if mode == "on":
            heart.on()
            await uasyncio.sleep_ms(500)
        elif mode == "off":
            heart.off()
            await uasyncio.sleep_ms(500)
        else:
            heart.on()
            await uasyncio.sleep_ms(60)
            heart.off()
            await uasyncio.sleep_ms(1940)


async def splash(ctx):
    """Show Pico Portal's original 60x60 RGB565 logo before the POST."""
    crt = ctx.crt
    size = 60
    left = (crt.w - size) // 2
    top = max(17, (crt.h - size) // 2 - 10)

    crt.begin_black()
    if not _draw_portal_logo(crt, left, top):
        _draw_fallback_logo(crt, left, top, size)
    crt.text_center("PICO PORTAL", top + size + 10, 1, "p_white")
    crt.end()
    await _sleep_or_skip(ctx, 1.9)
    gc.collect()


def _draw_portal_logo(crt, left, top):
    """Stream and 64-color-quantize the source logo without a 7.2KB buffer."""
    return _draw_rgb565_logo(
        crt,
        "/pico-portal-os/images/logo-dark.bin",
        left,
        top,
        60,
        [None] * 64,
    )


def _draw_rgb565_logo(crt, path, left, top, size, pens):
    """Stream a square big-endian RGB565 logo through a 64-color pen map."""
    try:
        row_size = size * 2
        with open(path, "rb") as image:
            for y in range(size):
                row = image.read(row_size)
                if len(row) != row_size:
                    return False
                for x in range(size):
                    offset = x * 2
                    pixel = row[offset] << 8 | row[offset + 1]
                    red = (pixel >> 11) & 0x1F
                    green = (pixel >> 5) & 0x3F
                    blue = pixel & 0x1F
                    key = (red >> 3) << 4 | (green >> 4) << 2 | (blue >> 3)
                    pen = pens[key]
                    if pen is None:
                        pen = crt.g.create_pen(
                            ((key >> 4) & 3) * 85,
                            ((key >> 2) & 3) * 85,
                            (key & 3) * 85,
                        )
                        pens[key] = pen
                    crt.g.set_pen(pen)
                    crt.g.pixel(left + x, top + y)
        return True
    except Exception:  # noqa: BLE001
        return False


def _rgb565_key(hi, lo):
    """Quantize one big-endian RGB565 pixel to the shared 6-bit pen key."""
    return (hi >> 6) << 4 | ((hi >> 1) & 3) << 2 | ((lo >> 3) & 3)


def _encode_rgb565_runs(path, size):
    """RLE a square big-endian RGB565 asset into (x, y, width, key) rows.

    Each run is 4 bytes; key is the same 6-bit quantized color used by
    _draw_rgb565_logo. Encoding once keeps the per-frame launcher draw free of
    file I/O and per-pixel Python loops.
    """
    try:
        encoded = bytearray()
        row_size = size * 2
        with open(path, "rb") as image:
            for y in range(size):
                row = image.read(row_size)
                if len(row) != row_size:
                    return b""
                x = 0
                while x < size:
                    key = _rgb565_key(row[x * 2], row[x * 2 + 1])
                    start = x
                    x += 1
                    while (
                        x < size
                        and _rgb565_key(row[x * 2], row[x * 2 + 1]) == key
                    ):
                        x += 1
                    encoded.append(start)
                    encoded.append(y)
                    encoded.append(x - start)
                    encoded.append(key)
        return bytes(encoded)
    except Exception:  # noqa: BLE001
        return b""


def _draw_menu_logo(crt, left, top):
    """Draw the compact launcher logo from its cached run-length encoding."""
    global _MENU_LOGO_PENS, _MENU_LOGO_RUNS
    if _MENU_LOGO_PENS is None:
        pens = []
        for key in range(64):
            pens.append(
                crt.preview_pen(
                    (
                        ((key >> 4) & 3) * 85,
                        ((key >> 2) & 3) * 85,
                        (key & 3) * 85,
                    )
                )
            )
        _MENU_LOGO_PENS = pens
    if _MENU_LOGO_RUNS is None:
        _MENU_LOGO_RUNS = _encode_rgb565_runs(
            "/pico-portal-os/images/logo-dark-small.bin",
            _MENU_LOGO_SIZE,
        )
    runs = _MENU_LOGO_RUNS
    if not runs:
        return False
    g = crt.g
    pens = _MENU_LOGO_PENS
    for i in range(0, len(runs), 4):
        g.set_pen(pens[runs[i + 3]])
        g.rectangle(left + runs[i], top + runs[i + 1], runs[i + 2], 1)
    return True


def _draw_theme_mask(crt, path, left, top, size, pen="fg"):
    """Draw a white-on-black RGB565 asset as cached horizontal theme runs.

    Runs are encoded once as (x, y, width) byte triplets; drawing is then a
    handful of rectangle calls instead of a per-pixel Python loop each frame.
    """
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
        except Exception:  # noqa: BLE001
            runs = b""
        _MENU_MASK_CACHE[path] = runs
    if not runs:
        return False

    crt.use(pen)
    g = crt.g
    for i in range(0, len(runs), 3):
        g.rectangle(left + runs[i], top + runs[i + 1], runs[i + 2], 1)
    return True


def _draw_launcher_header(crt):
    """Draw a centered website-style logo and title in the launcher header."""
    gap = 5
    title = NAME.upper()
    scale = 1
    title_width = crt.measure(title, scale)
    header_width = _MENU_LOGO_SIZE + gap + title_width
    left = max(4, (crt.w - header_width) // 2)
    top = 2

    if not _draw_menu_logo(crt, left, top):
        _draw_fallback_logo(crt, left, top, _MENU_LOGO_SIZE, "fg", "bg")
    title_y = top + (_MENU_LOGO_SIZE - crt.text_height(scale)) // 2
    crt.text(title, left + _MENU_LOGO_SIZE + gap, title_y, scale, "hi")
    bottom = top + _MENU_LOGO_SIZE
    crt.rule(bottom + 2, "dim")
    return bottom + 6


def _draw_fallback_logo(
    crt, left, top, size, foreground="p_white", background="black"
):
    """Small phosphor skull used if the RGB565 asset was not deployed."""
    pad = size // 7
    crt.use(foreground)
    crt.g.rectangle(left + pad, top + pad, size - 2 * pad, size // 2)
    crt.g.rectangle(left + 2 * pad, top + size // 2, size - 4 * pad, size // 3)
    crt.use(background)
    eye = max(5, size // 7)
    crt.g.rectangle(left + 2 * pad, top + 2 * pad, eye, eye)
    crt.g.rectangle(left + size - 2 * pad - eye, top + 2 * pad, eye, eye)
    crt.g.rectangle(left + size // 2 - 2, top + size // 2 - 4, 4, 6)


async def boot(ctx):
    """The power-on self test: green text scrolling up a warming CRT."""
    crt = ctx.crt
    sen = ctx.sensors

    mhz = sen.cpu_mhz()
    _, mem_total = sen.memory()
    _, flash_total = sen.flash()

    header = NAME.upper() + "  v" + VERSION
    lines = [
        ("RP2040 core .... {} MHz".format(mhz), "OK"),
        ("SRAM ........... {}K".format(mem_total // 1024), "OK"),
        ("FLASH .......... {}K".format(flash_total // 1024), "OK"),
        ("DISPLAY ST7789 . {}x{}".format(crt.w, crt.h), "OK"),
        (
            "CORE TEMP ...... {}".format(
                format_temperature(sen.temperature(), ctx.config)
            ),
            "OK",
        ),
        ("RADIO CYW43 .... 2.4G", "OK"),
        ("INPUT CORNERS ... 4 keys", "OK"),
        ("RGB LAMP ....... rgb", "OK"),
    ]
    header_scale = 2
    while header_scale > 1 and crt.measure(header, header_scale) > crt.w - 12:
        header_scale -= 1
    rule_y = 4 + crt.text_height(header_scale) + 2
    top = rule_y + 6
    row_h = CELL + 2

    def paint(shown, ready=False, cursor=True):
        crt.begin()
        crt.text_center(header, 4, header_scale, "hi")
        crt.rule(rule_y, "dim")
        for i in range(shown):
            text, status = lines[i]
            y = top + i * row_h
            text = crt.clip_text(text, crt.w - 60, 1)
            crt.text(text, 6, y, 1, "mid")
            crt.text("[", crt.w - 46, y, 1, "dim")
            crt.text(status, crt.w - 40, y, 1, "fg")
            crt.text("]", crt.w - 40 + crt.measure(status, 1) + 2, y, 1, "dim")
        if ready:
            y = top + len(lines) * row_h + 4
            crt.text("READY.", 6, y, 1, "hi")
            px = 6 + crt.measure("> ", 1)
            crt.text(">", 6, y + row_h, 1, "fg")
            crt.cursor(px, y + row_h, 1, "fg", on=cursor)
        crt.end()

    for i in range(len(lines)):
        ctx.lamp.set((0, 40 + i * 20, 20))
        crt.screen.backlight(min(crt.base_brightness, 0.25 + i * 0.12))
        paint(i + 1)
        if await _sleep_or_skip(ctx, 0.16):
            break
    crt.screen.backlight(crt.base_brightness)

    for _ in range(20):
        paint(len(lines), ready=True, cursor=crt.blink(400))
        if await _sleep_or_skip(ctx, 0.05):
            break
    ctx.lamp.set(IDLE_LAMP)
    gc.collect()


async def _sleep_or_skip(ctx, seconds):
    """Sleep, but return True early if any button is pressed (to skip)."""
    steps = max(1, int(seconds / 0.02))
    for _ in range(steps):
        if any(ctx.input.poll()):
            return True
        await uasyncio.sleep(0.02)
    return False


_DISPLAY_OPTIONS = (
    ("2.0 INCH", "320x240", "DISPLAY_PICO_DISPLAY_2"),
    ("1.14 INCH", "240x135", "DISPLAY_PICO_DISPLAY"),
)


async def pick_display(ctx):
    """One-time on-screen chooser for which Display Pack is attached.

    The 1.14" and 2.0" packs share an ST7789 controller, so the size can't be
    auto-detected - we ask once, save the answer, and reboot into it. This is
    drawn at the small size so it stays readable on either panel.
    """
    crt = ctx.crt
    sel = 0
    ctx.lamp.set((0, 120, 200))

    while True:
        up, down, select, back = ctx.input.poll()
        if up:
            sel = (sel - 1) % len(_DISPLAY_OPTIONS)
        if down:
            sel = (sel + 1) % len(_DISPLAY_OPTIONS)
        if select:
            return await _save_display(ctx, _DISPLAY_OPTIONS[sel][2])

        crt.begin()
        title_scale = crt.fit_scale("SELECT DISPLAY", crt.w - 16)
        title_y = crt.ui_top()
        crt.text_center("SELECT DISPLAY", title_y, title_scale, "hi")
        rule_y = title_y + crt.text_height(title_scale) + 3
        crt.rule(rule_y, "dim")
        prompt_y = rule_y + 4
        crt.text_center("Which Pico Display", prompt_y, 1, "mid")
        crt.text_center("Pack is attached?", prompt_y + CELL + 2, 1, "mid")

        labels = tuple(option[0] for option in _DISPLAY_OPTIONS)
        label_scale = crt.fit_scale_many(labels, crt.w - 88)
        top = prompt_y + 2 * CELL + 6
        row_h = crt.text_height(label_scale) + 6
        for i, (label, res, _) in enumerate(_DISPLAY_OPTIONS):
            y0 = top + i * row_h
            if i == sel:
                crt.use("mid")
                crt.g.rectangle(4, y0, crt.w - 8, row_h - 4)
                crt.text(label, 8, y0 + 2, label_scale, "bg")
                crt.text_right(res, crt.w - 8, y0 + 4, 1, "bg")
            else:
                crt.text(label, 8, y0 + 2, label_scale, "mid")
                crt.text_right(res, crt.w - 8, y0 + 4, 1, "dim")

        crt.button_hints(top_right="SEL", bottom_left="UP", bottom_right="DWN")
        crt.end()
        await uasyncio.sleep(FRAME)


async def _save_display(ctx, display_type):
    crt = ctx.crt
    ctx.config["display"]["type"] = display_type
    saved = True
    try:
        save_config(ctx.config)
    except Exception:  # noqa: BLE001
        saved = False

    for _ in range(24):
        crt.begin()
        if saved:
            crt.text_center("SAVED", crt.h // 2 - 16, 3, "fg")
            crt.text_center("rebooting...", crt.h // 2 + 14, 1, "mid")
        else:
            crt.text_center("SAVE FAILED", crt.h // 2 - 12, 2, "alarm")
            crt.text_center("continuing anyway", crt.h // 2 + 12, 1, "mid")
        crt.end()
        await uasyncio.sleep(0.05)

    if saved:
        reset()
    return display_type


async def run(ctx):
    """The main loop: draw the menu, launch apps, come back, repeat. Forever."""
    sel = 0

    while True:
        ctx.lamp.set(IDLE_LAMP)
        sel = await _menu(ctx, sel)
        spec = APPS[sel]
        try:
            app = _load_app(spec)
        except Exception as exc:  # noqa: BLE001
            await _crash(ctx, _app_label(ctx.crt, spec), exc)
            gc.collect()
            continue
        try:
            await app.run(ctx)
        except Exception as exc:  # noqa: BLE001
            await _crash(ctx, _app_label(ctx.crt, spec), exc)
        finally:
            ctx.wifi.stop_ap()
            ctx.wifi.off()
            ctx.ble.stop()
            ctx.lamp.set(IDLE_LAMP)
            del app
            _unload_app(spec)
            ctx.input.wake()
            gc.collect()


async def run_idle_screensaver(ctx, force=False):
    """Run the configured saver only from a launcher/submenu listing."""
    if not force and not ctx.idle_saver_allowed:
        return
    spec = APPS[SCREENSAVER_INDEX]
    ctx.input.wake()
    for attempt in range(2):
        app = None
        _release_transients()
        try:
            app = _load_app(spec)
            app.auto = True
            await app.run(ctx)
            return
        except MemoryError as exc:
            if attempt:
                await _crash(ctx, _app_label(ctx.crt, spec), exc)
                return
        except Exception as exc:  # noqa: BLE001
            await _crash(ctx, _app_label(ctx.crt, spec), exc)
            return
        finally:
            if app is not None:
                del app
            _unload_app(spec)
            ctx.input.wake()
        await uasyncio.sleep_ms(0)


async def _menu(ctx, sel):
    crt = ctx.crt
    sen = ctx.sensors
    labels = tuple(_app_label(crt, app) for app in APPS)
    descriptions = tuple(app[2] for app in APPS)
    ctx.idle_saver_allowed = True
    hud = ""
    hud_scale = 1
    hud_updated = None
    dirty = True

    while True:
        up, down, select, back = ctx.input.poll()
        idle_seconds = int(ctx.config["screensaver"].get("timeout", 60))
        if idle_seconds > 0 and ctx.input.idle_ms() >= idle_seconds * 1000:
            labels = None
            descriptions = None
            gc.collect()
            await run_idle_screensaver(ctx)
            labels = tuple(_app_label(crt, app) for app in APPS)
            descriptions = tuple(app[2] for app in APPS)
            hud_updated = None
            dirty = True
            continue
        if up:
            sel = (sel - 1) % len(APPS)
            dirty = True
        if down:
            sel = (sel + 1) % len(APPS)
            dirty = True
        if select:
            ctx.idle_saver_allowed = False
            return sel

        tick = time.ticks_ms()
        if hud_updated is None or time.ticks_diff(tick, hud_updated) >= 1000:
            now, _offset = local_time(ctx.clock_config)
            hud = "{} {}".format(
                format_clock(now, ctx.config),
                format_temperature(sen.temperature(), ctx.config),
            )
            hud_scale = crt.fit_scale(hud, crt.w - 120)
            hud_updated = tick
            dirty = True

        if dirty:
            dirty = False
            crt.begin()
            list_top = _draw_launcher_header(crt)
            start, visible, row_h = crt.menu_rows(
                labels,
                sel,
                list_top,
                crt.ui_bottom(),
                x=4,
                descriptions=descriptions,
                leading_width=_MENU_ICON_SIZE + 6,
                min_row_height=_MENU_ICON_SIZE + 4,
            )
            icon_x = 4
            for row in range(visible):
                index = start + row
                if index >= len(_MENU_ICON_PATHS):
                    break
                icon_y = list_top + row * row_h + (row_h - _MENU_ICON_SIZE) // 2
                _draw_theme_mask(
                    crt,
                    _MENU_ICON_PATHS[index],
                    icon_x,
                    icon_y,
                    _MENU_ICON_SIZE,
                    "hi" if index == sel else "fg",
                )

            crt.text_center(
                hud, crt.h - crt.text_height(hud_scale), hud_scale, "mid"
            )
            crt.button_hints(
                top_right="SEL",
                bottom_left="UP",
                bottom_right="DWN",
            )

            crt.end()
        await uasyncio.sleep(FRAME)


async def _crash(ctx, label, exc):
    """
    If an app throws, show a tidy CRT error instead of freezing the device.
    """
    crt = ctx.crt
    ctx.lamp.status("error")
    msg = str(exc)
    while True:
        up, down, select, back = ctx.input.poll()
        if any((up, down, select, back)):
            return
        crt.begin()
        crt.box(
            4,
            4,
            crt.w - 8,
            crt.h - 8,
            "alarm",
            title="FAULT",
            title_pen="alarm",
        )
        crt.text(label, 14, 20, 2, "alarm")
        crt.text(msg, 14, 44, 1, "warn", wrap=crt.w - 28)
        crt.text("press any button", 14, crt.h - 20, 1, "mid")
        crt.end()
        await uasyncio.sleep(FRAME)
