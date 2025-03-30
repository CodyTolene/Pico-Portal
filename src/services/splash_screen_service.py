# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service to display a splash image on startup.
# =============================================================================

import sys
import uasyncio  # type: ignore
import os

from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, DISPLAY_PICO_DISPLAY_2  # type: ignore
from services.options_service import OptionsDisplayTypes, OptionKeys, OptionsService

sys.path.append("../modules")
sys.path.append("../services")


class SplashScreenService:
    def __init__(self, options: OptionsService):
        display_type = options.get_option(OptionKeys.DISPLAY_TYPE)

        if display_type == OptionsDisplayTypes.DISPLAY_PICO_DISPLAY:
            self.graphics = PicoGraphics(display=DISPLAY_PICO_DISPLAY)
        elif display_type == OptionsDisplayTypes.DISPLAY_PICO_DISPLAY_2:
            self.graphics = PicoGraphics(display=DISPLAY_PICO_DISPLAY_2, rotate=270)
        else:
            raise ValueError("Invalid display type")

        self.width, self.height = self.graphics.get_bounds()

    async def show(self, image_path="images/logo.bin", duration=3):
        try:
            # Load raw RGB565 image (60x60 = 7200 bytes)
            with open(image_path, "rb") as f:
                raw = f.read()

            image_width = 60
            image_height = 60

            x_offset = (self.width - image_width) // 2
            y_offset = (self.height - image_height) // 2

            self.graphics.set_pen(self.graphics.create_pen(255, 255, 255))
            self.graphics.clear()

            # Draw pixels from raw binary
            for y in range(image_height):
                for x in range(image_width):
                    i = (y * image_width + x) * 2
                    if i + 1 >= len(raw):
                        continue

                    pixel = raw[i] << 8 | raw[i + 1]
                    r = ((pixel >> 11) & 0x1F) << 3
                    g = ((pixel >> 5) & 0x3F) << 2
                    b = (pixel & 0x1F) << 3

                    pen = self.graphics.create_pen(r, g, b)
                    self.graphics.set_pen(pen)
                    self.graphics.pixel(x + x_offset, y + y_offset)

            self.graphics.update()

        except Exception as e:
            self.graphics.set_pen(self.graphics.create_pen(0, 0, 0))
            self.graphics.text("Splash failed", 10, 10, scale=2)
            self.graphics.update()
            print(f"Failed to load splash: {e}")

        await uasyncio.sleep(duration)
