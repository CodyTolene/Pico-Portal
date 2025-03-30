# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service to display a splash image on startup.
# =============================================================================

import sys
import uasyncio  # type: ignore

# Local packages
from services.screen_service import ScreenService

sys.path.append("../modules")
sys.path.append("../services")


class SplashScreenService:
    def __init__(self, screen: ScreenService):
        self.enable_dark_mode = screen.enable_dark_mode
        self.graphics = screen.graphics
        self.width, self.height = self.graphics.get_bounds()

        self.BLACK = screen.BLACK
        self.WHITE = screen.WHITE

    async def show(self, duration=3):
        image_path = (
            "images/logo-dark.bin" if self.enable_dark_mode else "images/logo.bin"
        )

        try:
            # Load raw RGB565 image (60x60 = 7200 bytes)
            with open(image_path, "rb") as f:
                raw = f.read()

            image_width = 60
            image_height = 60

            x_offset = (self.width - image_width) // 2
            y_offset = (self.height - image_height) // 2

            if self.enable_dark_mode:
                self.graphics.set_pen(self.BLACK)
            else:
                self.graphics.set_pen(self.WHITE)

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
            if self.enable_dark_mode:
                self.graphics.set_pen(self.WHITE)
            else:
                self.graphics.set_pen(self.BLACK)

            self.graphics.text("Splash failed", 10, 10, scale=2)
            self.graphics.update()
            print(f"Failed to load splash: {e}")

        await uasyncio.sleep(duration)
