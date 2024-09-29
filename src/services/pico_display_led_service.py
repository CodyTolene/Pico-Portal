# ==============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service for controlling the LED lights on the Pico Display(s)
# ==============================================================================

import uasyncio  # type: ignore
from pimoroni import RGBLED  # type: ignore

from services.options_service import OptionKeys, OptionsService

COLORS = {
    "RED": (255, 0, 0),
    "GREEN": (0, 255, 0),
    "BLUE": (0, 0, 255),
    "YELLOW": (255, 255, 0),
    "CYAN": (0, 255, 255),
    "MAGENTA": (255, 0, 255),
    "WHITE": (255, 255, 255),
    "OFF": (0, 0, 0),
}


class PicoDisplayLedService:
    def __init__(self, options: OptionsService):
        # Dependencies
        self.led_brightness = options.get_option(OptionKeys.LED_BRIGHTNESS)

        # Set up LED
        self.led = RGBLED(6, 7, 8)  # Pico display pins

    # Set the color of the LED
    async def set_color(self, color: str):
        if color in COLORS:
            self.current_color = COLORS[color]
            r, g, b = self.current_color
            self.led.set_rgb(r, g, b)
            await self._set_brightness(self.led_brightness)
        else:
            print(
                f"Invalid color: {color}. Available colors are: {', '.join(COLORS.keys())}"
            )

    # Set the brightness of the current color
    async def _set_brightness(self, brightness: float):
        if not 0 <= brightness <= 1:
            print("Invalid brightness value. It must be between 0.0 and 1.0")
            return

        # Adjust current color brightness
        r, g, b = self.current_color
        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)

        # Update the LED with new brightness
        self.led.set_rgb(r, g, b)


# Testing
if __name__ == "__main__":

    async def main():
        options = OptionsService()
        led = PicoDisplayLedService(options)

        await led.set_color("GREEN")

        while True:
            await uasyncio.sleep(1)

    uasyncio.run(main())
