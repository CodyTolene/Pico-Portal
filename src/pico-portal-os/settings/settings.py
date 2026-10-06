# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from ..apps import App
from ..apps.submenu import run_submenu

_SETTINGS = (
    (
        "CLOCK",
        "Clock Settings",
        "settings.clocksettings",
        "ClockSettings",
        "Time and timezone",
        "/pico-portal-os/images/clock.bin",
    ),
    (
        "DISPLAY",
        "Display Settings",
        "settings.options",
        "Options",
        "Theme, light, size, and idle",
        "/pico-portal-os/images/display.bin",
    ),
    (
        "REGIONAL",
        "Regional Settings",
        "settings.regional",
        "RegionalSettings",
        "Clock, temperature, and units",
        "/pico-portal-os/images/globe.bin",
    ),
    (
        "WIFI",
        "WiFi Settings",
        "settings.wifi_settings",
        "WifiSettings",
        "Connect or disconnect",
        "/pico-portal-os/images/wifi.bin",
    ),
)


class Settings(App):

    async def run(self, ctx):
        await run_submenu(ctx, "SETTINGS", _SETTINGS)
