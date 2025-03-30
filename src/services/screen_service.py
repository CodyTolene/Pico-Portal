# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service to handle screen display and brightness settings.
# =============================================================================

import sys
import uasyncio  # type: ignore
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, DISPLAY_PICO_DISPLAY_2  # type: ignore

# Local packages
from services.options_service import OptionsDisplayTypes, OptionKeys, OptionsService

# Ensure packages can be imported
sys.path.append("../modules")
sys.path.append("../services")


class ScreenService:
    def __init__(self, options: OptionsService):
        self.display_type: OptionsDisplayTypes = options.get_option(OptionKeys.DISPLAY_TYPE)
        self.enable_dark_mode: bool = options.get_option(OptionKeys.ENABLE_DARK_MODE)
        self.screen_brightness: float = options.get_option(OptionKeys.SCREEN_BRIGHTNESS)

        if self.display_type == OptionsDisplayTypes.DISPLAY_PICO_DISPLAY:
            self.graphics = PicoGraphics(display=DISPLAY_PICO_DISPLAY)
        elif self.display_type == OptionsDisplayTypes.DISPLAY_PICO_DISPLAY_2:
            self.graphics = PicoGraphics(display=DISPLAY_PICO_DISPLAY_2, rotate=270)
        else:
            raise ValueError("Invalid display type")

        # Colors
        self.BLACK = self.graphics.create_pen(0, 0, 0)
        self.GRAY = self.graphics.create_pen(150, 150, 150)
        self.GREEN = self.graphics.create_pen(0, 200, 0)
        self.RED = self.graphics.create_pen(255, 0, 0)
        self.WHITE = self.graphics.create_pen(255, 255, 255)

        self._set_backlight()

    def _set_backlight(self):
        self.graphics.set_backlight(self.screen_brightness)

# Testing
if __name__ == "__main__":

    async def main():
        options = OptionsService()
        backlight_service = BacklightService(options)

        backlight_service.set_backlight()

        await uasyncio.sleep(1)

    uasyncio.run(main())
