# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from .apps import App
from .apps.submenu import run_submenu

_SYSTEM_TOOLS = (
    (
        "BATTERY",
        "Battery Info",
        "settings.batteryinfo",
        "BatteryInfo",
        "LiPo and power stats",
        "/pico-portal-os/images/battery.bin",
    ),
    (
        "FILESYSTEM",
        "Filesystem Info",
        "settings.filesysteminfo",
        "FilesystemInfo",
        "Flash usage and files",
        "/pico-portal-os/images/folder.bin",
    ),
    (
        "SCREEN TEST",
        "Screen Test",
        "settings.screentest",
        "ScreenTest",
        "Display and RGB test",
        "/pico-portal-os/images/test.bin",
    ),
    (
        "SYS.MON",
        "System Monitor",
        "settings.systemmonitor",
        "SystemMonitor",
        "Live Pico telemetry",
        "/pico-portal-os/images/dashboard.bin",
    ),
)


class SystemTools(App):

    async def run(self, ctx):
        await run_submenu(ctx, "SYSTEM TOOLS", _SYSTEM_TOOLS)
