# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================
#  Pinout (Pimoroni Pico Display Pack / Pack 2.0):
#    Buttons ...... A=GP12  B=GP13  X=GP14  Y=GP15
#    RGB LED ...... R=GP6   G=GP7   B=GP8
#    Onboard LED .. Pin("LED")  (via the Pico W wireless chip)
#    Screen ....... SPI, driven by PicoGraphics (ST7789)
#    Core temp .... ADC channel 4 (internal, no GPIO)
# =============================================================================

import gc
import os
import sys
import time

from .storage import _level

from machine import ADC, I2C, PWM, Pin, freq  # type: ignore
from pimoroni import RGBLED  # type: ignore
from picographics import (  # type: ignore
    PicoGraphics,
    DISPLAY_PICO_DISPLAY,
    DISPLAY_PICO_DISPLAY_2,
)

try:
    from picographics import PEN_P8  # type: ignore
except ImportError:  # older firmware
    PEN_P8 = None

DISPLAY_TYPES = ("DISPLAY_PICO_DISPLAY", "DISPLAY_PICO_DISPLAY_2")


def reset():
    """Soft-reboot the board. Used after the display type changes."""
    import machine  # type: ignore

    machine.reset()


def button_held(gp):
    """True if the button on GPIO `gp` is physically held down right now.

    Button.read() is edge-triggered (True once per press); this reads the
    live active-low pin level instead, which is what you want at boot time
    (e.g. hold the bottom-left control while powering on to re-pick the screen).
    """
    try:
        return Pin(gp, Pin.IN, Pin.PULL_UP).value() == 0
    except Exception:  # noqa: BLE001
        return False


class Screen:
    """The Pimoroni Display Pack. Owns the PicoGraphics buffer and bounds."""

    def __init__(self, config, display_type=None):
        resolved = display_type or config["display"].get("type", "auto")

        if resolved == "DISPLAY_PICO_DISPLAY_2":
            if PEN_P8 is None:
                self.buffer = bytearray(320 * 240 * 2)
                self.graphics = PicoGraphics(
                    display=DISPLAY_PICO_DISPLAY_2,
                    rotate=270,
                    buffer=self.buffer,
                )
            else:
                self.buffer = bytearray(320 * 240)
                try:
                    self.graphics = PicoGraphics(
                        display=DISPLAY_PICO_DISPLAY_2,
                        rotate=270,
                        pen_type=PEN_P8,
                        buffer=self.buffer,
                    )
                except (TypeError, ValueError):
                    self.buffer = None
                    gc.collect()
                    self.buffer = bytearray(320 * 240 * 2)
                    self.graphics = PicoGraphics(
                        display=DISPLAY_PICO_DISPLAY_2,
                        rotate=270,
                        buffer=self.buffer,
                    )
        else:
            self.buffer = bytearray(240 * 135 * 2)
            self.graphics = PicoGraphics(
                display=DISPLAY_PICO_DISPLAY, buffer=self.buffer
            )

        self.width, self.height = self.graphics.get_bounds()
        self.base_brightness = _level(config["display"].get("brightness"), 0.9)
        self.graphics.set_backlight(self.base_brightness)
        self.graphics.set_font("bitmap8")

    def backlight(self, level):
        self.graphics.set_backlight(level)

    def set_brightness(self, level):
        self.base_brightness = _level(level, self.base_brightness)
        self.backlight(self.base_brightness)


class Lamp:
    """The RGB status LED on the Display Pack."""

    _STATUS_COLORS = {
        "idle": (0, 70, 30),
        "success": (0, 255, 90),
        "warning": (255, 150, 0),
        "error": (255, 0, 0),
        "info": (0, 120, 255),
    }

    def __init__(self, config):
        self.led = RGBLED(6, 7, 8)
        self.brightness = _level(config["led"].get("brightness"), 0.05)
        self._current = (0, 0, 0)
        self.set((0, 0, 0))

    def set(self, rgb):
        """
        Set the LED to an (r, g, b) tuple, scaled by configured brightness.
        """
        self._current = rgb
        r, g, b = rgb
        self.led.set_rgb(
            int(r * self.brightness),
            int(g * self.brightness),
            int(b * self.brightness),
        )

    def off(self):
        self.set((0, 0, 0))

    def status(self, kind):
        """Show a steady semantic state while respecting LED brightness."""
        self.set(self._STATUS_COLORS.get(kind, self._STATUS_COLORS["info"]))

    async def feedback(self, kind, restore=True):
        """Pulse a recognizable success/warning/error pattern."""
        from uasyncio import sleep_ms  # type: ignore

        previous = self._current
        color = self._STATUS_COLORS.get(kind, self._STATUS_COLORS["info"])
        if kind == "error":
            pulses, on_ms = 3, 85
        elif kind == "warning":
            pulses, on_ms = 2, 150
        elif kind == "success":
            pulses, on_ms = 2, 105
        else:
            pulses, on_ms = 1, 130
        for pulse in range(pulses):
            self.set(color)
            await sleep_ms(on_ms)
            if pulse + 1 < pulses:
                self.off()
                await sleep_ms(65)
        if restore:
            self.set(previous)

    def set_brightness(self, level):
        self.brightness = _level(level, self.brightness)
        self.set(self._current)


class Heartbeat:
    """The onboard LED. A slow blink so you know the board is alive."""

    def __init__(self):
        self.pin = Pin("LED", Pin.OUT)

    def on(self):
        self.pin.on()

    def off(self):
        self.pin.off()


class Button:
    """One front-panel button with IRQ-latched, pimoroni-style auto-repeat.

    pimoroni.Button.read() only notices a press if the pin happens to be
    sampled while the button is physically held, so a quick tap vanishes
    whenever a frame takes longer to draw than the tap lasted. Here a pin IRQ
    latches every debounced press the moment it happens; read() then reports
    each latched press exactly once and keeps the familiar repeat-while-held
    behavior (repeat_time, 3x faster after hold_time), so callers are
    unchanged.
    """

    _DEBOUNCE_MS = 30
    _PENDING_CAP = 2

    def __init__(self, gp, repeat_time=200, hold_time=1000):
        self.repeat_time = repeat_time
        self.hold_time = hold_time
        self.pin = Pin(gp, Pin.IN, Pin.PULL_UP)
        self._presses = 0
        self._taken = 0
        self._down = False
        self._down_ms = 0
        self._repeat_ms = 0
        self._edge_ms = time.ticks_ms()
        self.pin.irq(self._on_edge, Pin.IRQ_FALLING | Pin.IRQ_RISING)

    def _on_edge(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._edge_ms) >= self._DEBOUNCE_MS:
            if pin.value() == 0:
                if not self._down:
                    self._down = True
                    self._down_ms = now
                    self._repeat_ms = now
                    if (self._presses - self._taken) & 0xFF < self._PENDING_CAP:
                        self._presses = (self._presses + 1) & 0xFF
            elif self._down:
                self._down = False
        self._edge_ms = now

    def read(self):
        """True once per latched press, then repeating while held."""
        now = time.ticks_ms()
        if self._taken != self._presses:
            self._taken = (self._taken + 1) & 0xFF
            self._repeat_ms = now
            return True
        if time.ticks_diff(now, self._edge_ms) < self._DEBOUNCE_MS:
            return False
        held = self.pin.value() == 0
        if not self._down:
            if held:
                self._down = True
                self._down_ms = now
                self._repeat_ms = now
                return True
            return False
        if not held:
            self._down = False
            return False
        rate = self.repeat_time
        if (
            self.hold_time
            and time.ticks_diff(now, self._down_ms) > self.hold_time
        ):
            rate //= 3
        if rate and time.ticks_diff(now, self._repeat_ms) >= rate:
            self._repeat_ms = now
            return True
        return False

    def flush(self):
        """Forget queued presses and restart repeat pacing.

        Called at app/menu transitions so a tap made while nothing was
        polling (an app import, the crash screen) is not replayed later.
        """
        self._taken = self._presses
        self._repeat_ms = time.ticks_ms()


class Buttons:
    """The four front-panel buttons. read() is True on a fresh press."""

    def __init__(self):
        self.a = Button(12)
        self.b = Button(13)
        self.x = Button(14)
        self.y = Button(15)

    def flush(self):
        """Drop presses queued while no app was polling (transitions)."""
        self.a.flush()
        self.b.flush()
        self.x.flush()
        self.y.flush()


class Sensors:
    """Real telemetry read straight off the RP2040 and the flash filesystem.

    All of this is genuine device data - no faking. The core temperature comes
    from the RP2040's internal sensor on ADC channel 4; RAM figures come from
    the garbage collector; flash from the filesystem stat.
    """

    # RP2040 datasheet calibration for the on-die temperature diode.
    _V_REF = 3.3
    _T_SLOPE = 0.001721  # volts per degree C
    _T_27 = 0.706  # diode voltage at 27 C
    _INA_ADDRESSES = (0x40, 0x41, 0x42, 0x43)
    _INA_CALIBRATION = 0x1000
    _INA_CONFIG = 0x3EEF  # 32 V range, 32-sample ADCs, continuous mode

    def __init__(self, display_type="DISPLAY_PICO_DISPLAY_2", screen=None):
        self._temp_adc = ADC(4)  # internal temperature channel
        self._boot_ms = time.ticks_ms()
        self._display_type = display_type
        self._screen = screen
        self._vsys_adc = None
        self._battery_i2c = None
        self._backlight_pwm = None
        self._ina_address = None
        self._ina_ready = False
        self._battery_cache = None
        self._battery_cache_ms = 0

    def temperature(self):
        """RP2040 core temperature in degrees Celsius (float)."""
        raw = self._temp_adc.read_u16()
        volts = raw * self._V_REF / 65535.0
        return 27.0 - (volts - self._T_27) / self._T_SLOPE

    def cpu_mhz(self):
        """Current CPU clock in MHz."""
        return freq() // 1_000_000

    def firmware(self):
        """MicroPython release this build is based on, e.g. "1.25.0".

        Worth showing: the RP2 multicast/IGMP fixes the mDNS/SSDP sniffer relies
        on landed in 1.24.1 and 1.25.0, so an older base explains a silent scan.
        """
        try:
            return os.uname().release
        except Exception:  # noqa: BLE001
            return "unknown"

    def memory(self):
        """(used_bytes, total_bytes) of SRAM as seen by the allocator."""
        gc.collect()
        free = gc.mem_free()
        used = gc.mem_alloc()
        return used, used + free

    def flash(self):
        """(used_bytes, total_bytes) of the onboard flash filesystem."""
        s = os.statvfs("/")
        block = s[0]
        total = block * s[2]
        free = block * s[3]
        return total - free, total

    def filesystem(self):
        """Return flash block stats plus a recursive file/directory count."""
        stats = os.statvfs("/")
        block_size = stats[0]
        total = block_size * stats[2]
        free = block_size * stats[3]
        files, directories, largest, largest_name = self._count_files("/")
        return {
            "used": total - free,
            "free": free,
            "total": total,
            "block_size": block_size,
            "files": files,
            "directories": directories,
            "largest": largest,
            "largest_name": largest_name,
        }

    def _count_files(self, path):
        files = 0
        directories = 0
        largest = 0
        largest_name = ""
        try:
            entries = os.ilistdir(path)
            for entry in entries:
                name = entry[0]
                kind = entry[1]
                child = path.rstrip("/") + "/" + name
                if kind & 0x4000:
                    directories += 1
                    sub = self._count_files(child)
                    files += sub[0]
                    directories += sub[1]
                    if sub[2] > largest:
                        largest, largest_name = sub[2], sub[3]
                else:
                    files += 1
                    try:
                        size = os.stat(child)[6]
                    except OSError:
                        size = 0
                    if size > largest:
                        largest, largest_name = size, child
        except OSError:
            pass
        return files, directories, largest, largest_name

    def uptime_ms(self):
        """Milliseconds since Sensors was created (device boot)."""
        return time.ticks_diff(time.ticks_ms(), self._boot_ms)

    def _usb_present(self):
        """Read VBUS state on Pico W, with the original Pico as a fallback."""
        try:
            return bool(Pin("WL_GPIO2", Pin.IN).value())
        except Exception:  # noqa: BLE001
            try:
                return bool(Pin(24, Pin.IN).value())
            except Exception:  # noqa: BLE001
                return None

    def _vsys_voltage(self, samples=16):
        """Return averaged Pico VSYS voltage, or None for an invalid reading."""
        try:
            if self._vsys_adc is None:
                self._vsys_adc = ADC(Pin(29))
            total = 0
            for _ in range(samples):
                total += self._vsys_adc.read_u16()
                time.sleep_ms(2)
            volts = total / samples * (3.0 * self._V_REF / 65535.0)
            return volts if 2.5 <= volts <= 5.6 else None
        except Exception:  # noqa: BLE001
            return None

    def _write_ina(self, register, value):
        data = bytes(((value >> 8) & 0xFF, value & 0xFF))
        self._battery_i2c.writeto_mem(self._ina_address, register, data)

    def _read_ina(self, register, signed=False):
        data = self._battery_i2c.readfrom_mem(self._ina_address, register, 2)
        value = (data[0] << 8) | data[1]
        if signed and value & 0x8000:
            value -= 65536
        return value

    def _ensure_ina(self):
        """Initialize the Pico-UPS-B INA219 on GP20/GP21 when present."""
        if self._backlight_pwm is not None:
            deinit = getattr(self._backlight_pwm, "deinit", None)
            if deinit is not None:
                try:
                    deinit()
                except Exception:  # noqa: BLE001
                    pass
            self._backlight_pwm = None
        self._battery_i2c = I2C(
            0,
            sda=Pin(20),
            scl=Pin(21),
            freq=400_000,
        )
        if self._ina_address is None:
            devices = self._battery_i2c.scan()
            for address in self._INA_ADDRESSES:
                if address in devices:
                    self._ina_address = address
                    break
        if self._ina_address is None:
            return False
        if not self._ina_ready:
            self._write_ina(0x05, self._INA_CALIBRATION)
            self._write_ina(0x00, self._INA_CONFIG)
            time.sleep_ms(70)
            self._ina_ready = True
        return True

    def _close_ina(self):
        """
        Release I2C0 and restore the Display Pack backlight on shared GP20.
        """
        if self._battery_i2c is not None:
            deinit = getattr(self._battery_i2c, "deinit", None)
            if deinit is not None:
                try:
                    deinit()
                except Exception:  # noqa: BLE001
                    pass
            self._battery_i2c = None
        if self._screen is None:
            return
        try:
            level = self._screen.base_brightness
            self._backlight_pwm = PWM(Pin(20))
            self._backlight_pwm.freq(1000)
            self._backlight_pwm.duty_u16(int(level * 65535))
        except Exception:  # noqa: BLE001
            try:
                self._screen.backlight(self._screen.base_brightness)
            except Exception:  # noqa: BLE001
                pass

    def _ups_battery(self):
        usb = self._usb_present()
        result = {
            "profile": "PICO_UPS_B",
            "capacity_mah": 600,
            "usb": usb,
            "voltage": None,
            "vsys": None,
            "current_ma": None,
            "power_mw": None,
            "monitor_address": None,
        }
        try:
            if not self._ensure_ina():
                return result
            bus_raw = self._read_ina(0x02)
            current_raw = self._read_ina(0x04, signed=True)
            power_raw = self._read_ina(0x03)
            voltage = (bus_raw >> 3) * 0.004
            if 2.5 <= voltage <= 5.6:
                result["voltage"] = voltage
            result["current_ma"] = current_raw
            result["power_mw"] = power_raw * 20
            result["monitor_address"] = self._ina_address
        except Exception:  # noqa: BLE001
            self._ina_address = None
            self._ina_ready = False
        finally:
            self._close_ina()
        return result

    def _shim_battery(self):
        usb = self._usb_present()
        vsys = self._vsys_voltage()
        voltage = (
            vsys if usb is False and vsys is not None and vsys < 4.5 else None
        )
        return {
            "profile": "LIPO_SHIM",
            "capacity_mah": 1600,
            "usb": usb,
            "voltage": voltage,
            "vsys": vsys,
            "current_ma": None,
            "power_mw": None,
            "monitor_address": None,
        }

    def battery(self, force=False):
        """Return battery telemetry matched to the selected display build."""
        now = time.ticks_ms()
        if not force and self._battery_cache is not None:
            age = time.ticks_diff(now, self._battery_cache_ms)
            if 0 <= age < 10000:
                return self._battery_cache
        if self._display_type == "DISPLAY_PICO_DISPLAY":
            reading = self._ups_battery()
        else:
            reading = self._shim_battery()
        previous = self._battery_cache
        if previous is not None and previous["profile"] == reading["profile"]:
            for key in (
                "voltage",
                "vsys",
                "current_ma",
                "power_mw",
                "monitor_address",
            ):
                if reading[key] is None:
                    reading[key] = previous[key]
        self._battery_cache = reading
        self._battery_cache_ms = now
        return reading

    def power(self):
        """Return System Monitor's power summary: (USB, supply volts)."""
        battery = self.battery()
        volts = battery["voltage"]
        if volts is None:
            volts = battery["vsys"]
        return battery["usb"], volts


def _hexmac(raw):
    """Format 6 raw bytes as AA:BB:CC:DD:EE:FF."""
    return ":".join("{:02X}".format(b) for b in raw)


def _ad_sections(payload):
    """Yield (ad_type, value) for each AD structure in an advertising payload.

    Values stay memoryview slices of the caller's buffer, so nothing is copied
    until a decoder actually wants the bytes.
    """
    index = 0
    total = len(payload)
    while index + 1 < total:
        length = payload[index]
        if length == 0:
            break
        end = index + 1 + length
        if end > total:
            break
        start = index + 2
        yield payload[index + 1], payload[start:end]
        index = end


def _decode_ble_name(payload):
    """Pull the local name out of a BLE advertising payload (AD structures)."""
    name = ""
    for adtype, value in _ad_sections(payload):
        if adtype in (0x08, 0x09):
            try:
                name = bytes(value).decode()
            except Exception:  # noqa: BLE001
                name = ""
    return name


def _u16le(data, index):
    return data[index] | data[index + 1] << 8


def _i16le(data, index):
    value = data[index] | data[index + 1] << 8
    return value - 65536 if value & 0x8000 else value


def _i16be(data, index):
    value = data[index] << 8 | data[index + 1]
    return value - 65536 if value & 0x8000 else value


_SENSOR_TEMP_MIN = -40.0
_SENSOR_TEMP_MAX = 85.0

_BTHOME_SIZES = {
    0x00: 1,
    0x01: 1,
    0x02: 2,
    0x03: 2,
    0x04: 3,
    0x05: 3,
    0x06: 2,
    0x0C: 2,
    0x2E: 1,
    0x2F: 1,
    0x3D: 2,
    0x3E: 2,
    0x45: 2,
    0x51: 2,
}


def _sane_reading(temp, humidity):
    """True when a decode produced at least one value in a believable range."""
    if temp is not None and not _SENSOR_TEMP_MIN <= temp <= _SENSOR_TEMP_MAX:
        return False
    if humidity is not None and not 0.0 <= humidity <= 100.0:
        return False
    return temp is not None or humidity is not None


def _decode_bthome(value):
    """Decode unencrypted BTHome v2 service data (UUID 0xFCD2)."""
    if len(value) < 3 or value[0] & 0x01:
        return None
    temp = humidity = battery = millivolts = None
    index = 1
    total = len(value)
    while index < total:
        object_id = value[index]
        size = _BTHOME_SIZES.get(object_id)
        if size is None or index + 1 + size > total:
            break
        index += 1
        if object_id == 0x01:
            battery = value[index]
        elif object_id == 0x02:
            temp = _i16le(value, index) / 100.0
        elif object_id == 0x45:
            temp = _i16le(value, index) / 10.0
        elif object_id == 0x03:
            humidity = _u16le(value, index) / 100.0
        elif object_id == 0x2E:
            humidity = float(value[index])
        elif object_id == 0x0C:
            millivolts = _u16le(value, index)
        index += size
    if not _sane_reading(temp, humidity):
        return None
    return "BTHOME", temp, humidity, battery, millivolts


def _decode_atc(value):
    """Decode ATC1441 / pvvx custom service data (UUID 0x181A)."""
    if len(value) == 13:  # MAC, 0.1C big-endian, RH%, batt%, batt mV
        temp = _i16be(value, 6) / 10.0
        humidity = float(value[8])
        battery = value[9]
        millivolts = value[10] << 8 | value[11]
        kind = "ATC"
    elif len(value) == 15:  # pvvx custom: hundredths, little-endian
        temp = _i16le(value, 6) / 100.0
        humidity = _u16le(value, 8) / 100.0
        millivolts = _u16le(value, 10)
        battery = value[12]
        kind = "PVVX"
    else:
        return None
    if not _sane_reading(temp, humidity):
        return None
    return kind, temp, humidity, battery, millivolts


def _decode_mibeacon(value):
    """Decode an unencrypted Xiaomi MiBeacon frame (UUID 0xFE95)."""
    if len(value) < 6:
        return None
    control = _u16le(value, 0)
    if control & 0x0008:
        return None
    if not control & 0x0040:
        return None
    index = 5
    if control & 0x0010:
        index += 6  # MAC
    if control & 0x0020:
        index += 1
    if index + 3 > len(value):
        return None
    object_id = _u16le(value, index)
    size = value[index + 2]
    index += 3
    if index + size > len(value):
        return None
    temp = humidity = battery = None
    if object_id == 0x1004 and size >= 2:
        temp = _i16le(value, index) / 10.0
    elif object_id == 0x1006 and size >= 2:
        humidity = _u16le(value, index) / 10.0
    elif object_id == 0x100D and size >= 4:
        temp = _i16le(value, index) / 10.0
        humidity = _u16le(value, index + 2) / 10.0
    elif object_id in (0x1002, 0x100A) and size >= 1:
        return "MIJIA", None, None, value[index], None
    else:
        return None
    if not _sane_reading(temp, humidity):
        return None
    return "MIJIA", temp, humidity, battery, None


def _decode_govee(value):
    """Decode Govee manufacturer data (company 0xEC88)."""
    if len(value) < 6 or value[0] != 0x88 or value[1] != 0xEC:
        return None
    body = value[2:]
    # H5072/H5075 pack temperature and humidity into one 24-bit counter.
    packed = body[1] << 16 | body[2] << 8 | body[3]
    negative = bool(packed & 0x800000)
    packed &= 0x7FFFFF
    temp = packed / 10000.0
    humidity = (packed % 1000) / 10.0
    if negative:
        temp = -temp
    if _sane_reading(temp, humidity):
        return "GOVEE", temp, humidity, body[4] if len(body) > 4 else None, None
    # H5074 sends signed little-endian hundredths in the same company frame.
    if len(body) >= 5:
        temp = _i16le(body, 1) / 100.0
        humidity = _u16le(body, 3) / 100.0
        if _sane_reading(temp, humidity):
            return (
                "GOVEE",
                temp,
                humidity,
                body[5] if len(body) > 5 else None,
                None,
            )
    return None


def _decode_ble_sensor(payload):
    """Decode an environmental reading a BLE sensor broadcasts to everyone.

    Returns (kind, temp_c, humidity, battery_pct, battery_mv) with None for any
    field the broadcast omits, or None when the payload is not a sensor format
    this build understands. Nothing is transmitted and no encrypted payload is
    attacked - these are the plaintext advertisements the sensors already shout
    at every radio in the room.
    """
    for adtype, value in _ad_sections(payload):
        if adtype == 0x16 and len(value) >= 2:
            uuid = _u16le(value, 0)
            body = value[2:]
            if uuid == 0xFCD2:
                reading = _decode_bthome(body)
            elif uuid == 0x181A:
                reading = _decode_atc(body)
            elif uuid == 0xFE95:
                reading = _decode_mibeacon(body)
            else:
                continue
        elif adtype == 0xFF:
            reading = _decode_govee(value)
        else:
            continue
        if reading is not None:
            return reading
    return None


class WiFi:
    """Wi-Fi station/AP wrapper used by scanners and user-approved networking.

    Recon apps only scan. WiFi Settings may join a user-selected network and
    Pico Portal may create a local AP; both actions are explicit in the UI.
    """

    _CAP = 48

    def __init__(self):
        self._wlan = None
        self._ap = None
        self.keep_connected = False

    def _ensure(self):
        if self._wlan is None:
            import network  # type: ignore

            self._wlan = network.WLAN(network.STA_IF)
        if not self._wlan.active():
            self._wlan.active(True)

    def scan(self):
        """
        Return APs as (ssid, bssid, channel, rssi, secured), strongest first.
        """
        self._ensure()
        out = []
        for net in self._wlan.scan():
            ssid = net[0]
            try:
                ssid = ssid.decode()
            except Exception:  # noqa: BLE001
                ssid = str(ssid)
            out.append((ssid, _hexmac(net[1]), net[2], net[3], net[4] != 0))
        out.sort(key=lambda r: r[3], reverse=True)
        while len(out) > self._CAP:
            out.pop()
        return out

    def connect(self, ssid, password=""):
        """Begin a station connection; callers poll is_connected()."""
        self._ensure()
        if self._wlan.isconnected():
            self._wlan.disconnect()
        if password:
            self._wlan.connect(ssid, password)
        else:
            self._wlan.connect(ssid)
        self.keep_connected = True

    def reconnect(self, ssid, password=""):
        """Rebuild the station interface and retry saved credentials."""
        self.disconnect()
        time.sleep_ms(100)
        self.connect(ssid, password)

    def is_connected(self):
        return bool(self._wlan is not None and self._wlan.isconnected())

    def connection_info(self):
        if not self.is_connected():
            return None
        return self._wlan.ifconfig()

    def disconnect(self):
        """
        Stop station mode even when its link state is already disconnected.
        """
        self.keep_connected = False
        wlan = self._wlan
        self._wlan = None
        if wlan is not None:
            try:
                wlan.disconnect()
            except Exception:  # noqa: BLE001
                pass
            try:
                wlan.active(False)
            except Exception:  # noqa: BLE001
                pass
        del wlan
        gc.collect()

    def sync_time(self):
        """Set the RTC from NTP after a user-approved station connection."""
        if not self.is_connected():
            return False
        import ntptime  # type: ignore

        try:
            ntptime.settime()
            return True
        finally:
            sys.modules.pop("ntptime", None)
            del ntptime
            gc.collect()

    def _pin_ipv4(self, url):
        """Resolve a plain-HTTP host to IPv4, returning (url, host_header).

        Dual-stack firmware can resolve a name to its IPv6 address first, and
        the station link has no IPv6 route, so the request dies with
        EHOSTUNREACH. Requesting the IPv4 address directly and carrying the
        original name in the Host header keeps plain-HTTP fetches routable.
        HTTPS is left untouched - TLS needs the hostname for SNI.
        """
        if not url.startswith("http://"):
            return url, None
        rest = url[7:]
        slash = rest.find("/")
        host = rest if slash < 0 else rest[:slash]
        path = "" if slash < 0 else rest[slash:]
        if not host or ":" in host or host.replace(".", "").isdigit():
            return url, None
        try:
            import socket

            infos = socket.getaddrinfo(host, 80, socket.AF_INET)
            address = infos[0][-1][0]
        except Exception:  # noqa: BLE001
            return url, None
        return "http://" + address + path, host

    def http_json(self, url):
        """Fetch one small JSON response and close it promptly to recover RAM.

        Plain HTTP only: a TLS session does not fit in the heap beside the
        framebuffer.
        """
        if not self.is_connected():
            raise OSError("WiFi is not connected")
        if url.startswith("https://"):
            raise OSError("HTTPS unsupported on this device")
        gc.collect()
        import urequests  # type: ignore

        request_url, host_header = self._pin_ipv4(url)
        headers = {"Host": host_header} if host_header else {}
        response = None
        try:
            response = urequests.get(request_url, headers=headers)
            if getattr(response, "status_code", 200) != 200:
                raise OSError("HTTP {}".format(response.status_code))
            result = response.json()
        finally:
            if response is not None:
                response.close()
            del response
            sys.modules.pop("urequests", None)
            gc.collect()
        return result

    def start_ap(self, ssid, password=""):
        """Start a local access point and return its interface tuple."""
        import network  # type: ignore

        self.disconnect()
        self._ap = network.WLAN(network.AP_IF)
        self._ap.active(False)
        if password:
            self._ap.config(essid=ssid, password=password)
        else:
            try:
                self._ap.config(essid=ssid, security=0)
            except Exception:  # noqa: BLE001
                self._ap.config(essid=ssid, authmode=0)
        self._ap.active(True)
        for _ in range(20):
            if self._ap.active():
                break
            time.sleep_ms(50)
        return self._ap.ifconfig()

    def stop_ap(self):
        if self._ap is not None:
            try:
                self._ap.active(False)
            except Exception:  # noqa: BLE001
                pass
            self._ap = None

    def off(self):
        if self._wlan is not None:
            if self.keep_connected and self._wlan.isconnected():
                return
            try:
                self._wlan.active(False)
            except Exception:  # noqa: BLE001
                pass
            self._wlan = None


class BLE:
    """Passive Bluetooth-LE scanner: list nearby advertisers (name/MAC/RSSI).

    Observer role only - it listens for advertising packets, the same thing a
    phone's Bluetooth screen does. Not every MicroPython build ships Bluetooth,
    so start() returns False when scanning is unavailable.
    """

    _IRQ_SCAN_RESULT = 5
    _CAP = 48  # keep small for RAM
    _SENSOR_CAP = 12
    _SENSOR_EVICT_MS = 300000

    def __init__(self):
        self._ble = None
        self.devices = {}  # mac -> [name, rssi]
        self.sensor_mode = False
        self._readings = (
            {}
        )  # mac -> [name, rssi, seen, kind, temp, rh, batt, mv]

    def start(self, sensors=False):
        """Begin an observer-role scan; `sensors` decodes readings instead.

        Sensor mode is exclusive: it skips the general device table so the small
        heap only holds decoded environmental values.
        """
        try:
            import bluetooth
        except ImportError:
            return False
        try:
            self.devices = {}
            self._readings = {}
            self.sensor_mode = bool(sensors)
            self._ble = bluetooth.BLE()
            self._ble.active(True)
            self._ble.irq(self._irq)
            # scan forever
            self._ble.gap_scan(0, 30000, 30000, True)
            return True
        except Exception:  # noqa: BLE001
            self.stop()
            return False

    def _irq(self, event, data):
        if event != self._IRQ_SCAN_RESULT:
            return
        _addr_type, addr, _adv_type, rssi, adv = data
        now = time.ticks_ms()
        if self.sensor_mode:
            self._note_reading(_hexmac(addr), rssi, adv, now)
            return
        mac = _hexmac(addr)
        entry = self.devices.get(mac)
        if entry is None:
            if len(self.devices) < self._CAP:
                name = _decode_ble_name(adv)
                self.devices[mac] = [name, rssi, now]  # name, rssi, last-seen
        else:
            entry[1] = rssi
            entry[2] = now
            if not entry[0]:
                name = _decode_ble_name(adv)
                if name:
                    entry[0] = name

    def _evict(self, now):
        """Free the slot of a long-silent sensor so a new one can be tracked.

        Without this, carrying the device into a different room would leave the
        table full of sensors that are no longer in range.
        """
        stalest = None
        stalest_age = self._SENSOR_EVICT_MS
        for mac, entry in self._readings.items():
            age = time.ticks_diff(now, entry[2])
            if age > stalest_age:
                stalest = mac
                stalest_age = age
        if stalest is None:
            return False
        del self._readings[stalest]
        return True

    def _note_reading(self, mac, rssi, adv, now):
        """Merge one decoded advertisement into the passive sensor table.

        The advertisement buffer is only valid for the length of this callback,
        so decoding has to happen here rather than being deferred to the app.
        """
        reading = _decode_ble_sensor(adv)
        if reading is None:
            return
        entry = self._readings.get(mac)
        if entry is None:
            if len(self._readings) >= self._SENSOR_CAP and not self._evict(now):
                return
            entry = [
                _decode_ble_name(adv),
                rssi,
                now,
                reading[0],
                None,
                None,
                None,
                None,
            ]
            self._readings[mac] = entry
        else:
            entry[1] = rssi
            entry[2] = now
            entry[3] = reading[0]
            if not entry[0]:
                name = _decode_ble_name(adv)
                if name:
                    entry[0] = name
        for field in range(4):
            value = reading[field + 1]
            if value is not None:
                entry[field + 4] = value

    def readings(self):
        """
        Return sensors as (mac, name, rssi, kind, temp_c, rh, batt, mv, age_ms).

        Strongest signal first. Like results(), the scan IRQ can add an entry
        mid-read, so a concurrent change just yields an empty frame.
        """
        now = time.ticks_ms()
        try:
            items = [
                (
                    mac,
                    entry[0],
                    entry[1],
                    entry[3],
                    entry[4],
                    entry[5],
                    entry[6],
                    entry[7],
                    time.ticks_diff(now, entry[2]),
                )
                for mac, entry in self._readings.items()
            ]
        except RuntimeError:
            return []
        items.sort(key=lambda row: row[2], reverse=True)
        return items

    def results(self):
        """Return devices as (mac, name, rssi), strongest first.

        The scan IRQ can add a device mid-read, so guard against the dict
        changing under us and just try again next frame if it does.
        """
        try:
            items = [(mac, v[0], v[1]) for mac, v in self.devices.items()]
        except RuntimeError:
            return []
        items.sort(key=lambda t: t[2], reverse=True)
        return items

    def track(self, mac):
        """For a tracked device, return (rssi, age_ms) or None if never seen."""
        entry = self.devices.get(mac)
        if entry is None:
            return None
        return entry[1], time.ticks_diff(time.ticks_ms(), entry[2])

    def stop(self):
        if self._ble is not None:
            try:
                self._ble.gap_scan(None)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._ble.irq(None)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._ble.active(False)
            except Exception:  # noqa: BLE001
                pass
            self._ble = None
        self.devices = {}
        self._readings = {}
        self.sensor_mode = False
        sys.modules.pop("bluetooth", None)
