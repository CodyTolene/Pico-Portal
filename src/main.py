# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: The main entry point for the Pico Portal device. This script
#  will start the services for the device and keep the main loop running.
# =============================================================================

import uasyncio  # type: ignore
import sys
import time

# Local packages
from services.button_service import ButtonService
from services.messages_service import MessagesService
from services.onboard_led_service import OnboardLedService
from services.options_service import OptionsService
from services.pico_display_led_service import PicoDisplayLedService
from services.portal_service import PortalService

# Ensure packages can be imported
sys.path.append("/modules")
sys.path.append("/services")

# Version
VERSION = "1.0.0"


async def main():
    # Dependencies
    onboard_led = OnboardLedService()
    options = OptionsService()
    pico_display_led = PicoDisplayLedService(options)
    messages = MessagesService(options)
    buttons = ButtonService(messages)
    portal = PortalService(options, messages, pico_display_led)

    # Display the current version of the software on screen
    await messages.display(f"Starting Pico Portal v{VERSION}")

    # Make sure the display LED is off initially
    await pico_display_led.set_color("OFF")

    # Flash the onboard LED on and off every 3 seconds, indefinitely
    # Useful for when no screen is connected to the Pico Portal
    uasyncio.create_task(onboard_led.flash())

    # Start Pico Portal services
    uasyncio.create_task(portal.run())

    # Handle the buttons and trigger actions based on button presses
    uasyncio.create_task(buttons.run())

    # Keep the application running indefinitely while the power is on
    while True:
        await uasyncio.sleep(1)


if __name__ == "__main__":
    time.sleep(1)
    uasyncio.run(main())
