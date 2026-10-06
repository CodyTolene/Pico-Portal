# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import time

_MASK_15 = 0x7FFF
_MASK_30 = 0x3FFFFFFF
_state = (time.ticks_ms() ^ 0x5A17) & _MASK_15


def _step():
    global _state
    _state = (_state * 109 + 1021) & _MASK_15
    return _state


def _next():
    return (_step() << 15) | _step()


def getrandbits(bits):
    bits = max(1, min(30, bits))
    mask = _MASK_30 if bits == 30 else (1 << bits) - 1
    return _next() & mask


def random():
    return _next() / 1073741824.0


def uniform(low, high):
    return low + (high - low) * random()
