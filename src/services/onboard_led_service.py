# ======================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service for controlling the LED lights on the Pico W.
# ======================================================================

import uasyncio  # type: ignore
from machine import Pin  # type: ignore


class OnboardLedService:
    def __init__(self):
        self.led_pin = Pin("LED", Pin.OUT)

    # Flash the LED light at a given interval
    async def flash(self, interval=3.0):
        while True:
            self.led_pin.toggle()  # Toggle on/off
            await uasyncio.sleep(interval)


# Testing
if __name__ == "__main__":

    async def main():
        onboard_led = OnboardLedService()
        uasyncio.create_task(onboard_led.flash())

        while True:
            await uasyncio.sleep(1)

    uasyncio.run(main())
