# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from ..apps import App
from ..apps.submenu import run_submenu

_BLUETOOTH_TOOLS = (
    (
        "BT SNIFF",
        "Bluetooth Sniffer",
        "bluetooth.btsniff",
        "BtSniff",
        "Track & locate a BLE device",
        "/pico-portal-os/images/target.bin",
    ),
    (
        "SENSORS",
        "Sensor Radar",
        "bluetooth.sensorread",
        "SensorReader",
        "Decode BLE thermometers",
        "/pico-portal-os/images/radar.bin",
    ),
)


class BluetoothTools(App):

    async def run(self, ctx):
        await run_submenu(ctx, "BT TOOLS", _BLUETOOTH_TOOLS)
