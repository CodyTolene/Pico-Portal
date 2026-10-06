# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================


def format_clock(date_tuple, config, seconds=False):
    """Format a local-time tuple using the configured 12/24-hour clock."""
    hour = date_tuple[3]
    minute = date_tuple[4]
    second = date_tuple[5]
    if config["regional"].get("hour_format", 24) == 12:
        suffix = "AM" if hour < 12 else "PM"
        hour = hour % 12 or 12
        if seconds:
            return "{}:{:02d}:{:02d} {}".format(hour, minute, second, suffix)
        return "{}:{:02d} {}".format(hour, minute, suffix)
    if seconds:
        return "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
    return "{:02d}:{:02d}".format(hour, minute)


def temperature_value(celsius, config):
    """Convert a Celsius sensor value to the selected display unit."""
    if config["regional"].get("temperature_unit", "C") == "F":
        return float(celsius) * 9.0 / 5.0 + 32.0
    return float(celsius)


def temperature_unit(config):
    return (
        "F" if config["regional"].get("temperature_unit", "C") == "F" else "C"
    )


def format_temperature(celsius, config, decimals=0):
    value = temperature_value(celsius, config)
    if decimals:
        return "{:.1f}{}".format(value, temperature_unit(config))
    return "{:.0f}{}".format(value, temperature_unit(config))


def format_distance_feet(feet, config):
    """Format an estimated range using metric or imperial distance units."""
    if feet is None:
        return (
            "-- m"
            if config["regional"].get("unit_system") == "metric"
            else "-- ft"
        )
    if config["regional"].get("unit_system") == "metric":
        meters = feet * 0.3048
        if meters < 1.0:
            return "~{:.1f} m".format(meters)
        if meters < 100.0:
            return "~{} m".format(int(meters + 0.5))
        return "300+ m"
    if feet < 1.0:
        return "<1 ft"
    if feet < 10.0:
        return "~{:.1f} ft".format(feet)
    if feet < 999.0:
        return "~{} ft".format(int(feet + 0.5))
    return "999+ ft"
