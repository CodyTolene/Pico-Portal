# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service for controlling the LED lights for the Pico Portal.
# =============================================================================

import uasyncio  # type: ignore
from machine import Pin  # type: ignore


class LedService:
    def __init__(self):
        self.led_pin = Pin("LED", Pin.OUT)

    async def flash(self, interval=3.0):
        while True:
            self.led_pin.toggle()  # Toggle on/off
            await uasyncio.sleep(interval)


# Testing
if __name__ == "__main__":

    async def main():
        led = LedService()
        uasyncio.create_task(led.flash())

        while True:
            await uasyncio.sleep(1)

    uasyncio.run(main())
