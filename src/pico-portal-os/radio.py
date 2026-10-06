# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from .units import format_distance_feet


def estimated_feet(rssi, reference=-45, exponent=2.3):
    """Estimate range from RSSI using a simple indoor path-loss model.

    This is deliberately presented as an estimate: antenna orientation, walls,
    transmit power, and reflections can move the result substantially.
    """
    try:
        meters = 10 ** ((reference - float(rssi)) / (10.0 * exponent))
        return max(0.3, min(999.0, meters * 3.28084))
    except (TypeError, ValueError, OverflowError):
        return None


def format_distance(distance, config):
    """Format a feet-based RF estimate using the user's unit preference."""
    return format_distance_feet(distance, config)
