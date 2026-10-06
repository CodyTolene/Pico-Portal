# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import uasyncio  # type: ignore

os_info = __import__("pico-portal-os")
NAME = os_info.NAME
VERSION = os_info.VERSION
del os_info
hardware = __import__("pico-portal-os.hardware", None, None, ("Screen",))

BTN_BOTTOM_LEFT = 15  # hold at boot to re-run the display picker


async def _clock_sync_task(wifi):
    """Resync the RTC from NTP every time the station link comes up.

    The RP2040 clock resets on power loss, so the boot connection and any
    later reconnect (WiFi Settings, a dropped AP coming back) each trigger a
    fresh sync. CLOCK SETTINGS keeps its manual SYNC NOW on top of this.
    """
    was_connected = False
    while True:
        connected = wifi.is_connected()
        if connected and not was_connected:
            for _ in range(5):
                if not wifi.is_connected():
                    break
                try:
                    if wifi.sync_time():
                        break
                except Exception:  # noqa: BLE001
                    pass
                await uasyncio.sleep_ms(2000)
            connected = wifi.is_connected()
        was_connected = connected
        await uasyncio.sleep_ms(1000)


async def main():
    storage = __import__("pico-portal-os.storage", None, None, ("load_config",))
    config = storage.load_config()
    del storage

    has_display = config["display"].get("type") in hardware.DISPLAY_TYPES
    needs_pick = not has_display or hardware.button_held(BTN_BOTTOM_LEFT)
    boot_type = (
        "DISPLAY_PICO_DISPLAY" if needs_pick else config["display"]["type"]
    )

    gc.collect()

    screen = hardware.Screen(config, display_type=boot_type)
    crt_module = __import__("pico-portal-os.crt", None, None, ("CRT",))
    crt = crt_module.CRT(screen, config)
    del crt_module

    shell = __import__("pico-portal-os.shell", None, None, ("Context",))

    lamp = hardware.Lamp(config)
    heart = hardware.Heartbeat()
    buttons = hardware.Buttons()
    sensors = hardware.Sensors(boot_type, screen)
    wifi = hardware.WiFi()
    ble = hardware.BLE()

    ctx = shell.Context(
        crt,
        lamp,
        shell.Input(buttons),
        sensors,
        config,
        wifi,
        ble,
    )

    threshold = getattr(gc, "threshold", None)
    if threshold is not None:
        threshold(gc.mem_alloc() + gc.mem_free() // 4)

    print("{} v{} booting...".format(NAME, VERSION))

    uasyncio.create_task(shell.heartbeat_task(heart, config))

    if needs_pick:
        await shell.pick_display(ctx)

    await shell.splash(ctx)

    wifi_config = ctx.wifi_config
    if wifi_config.get("ssid"):
        try:
            wifi.connect(wifi_config["ssid"], wifi_config.get("password", ""))
        except Exception:  # noqa: BLE001
            wifi.keep_connected = False

    uasyncio.create_task(_clock_sync_task(wifi))

    await shell.boot(ctx)
    await shell.run(ctx)


if __name__ == "__main__":
    uasyncio.run(main())
