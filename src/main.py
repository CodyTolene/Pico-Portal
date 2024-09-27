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
from services.options_service import OptionsService
from services.portal_service import PortalService
from services.led_service import LedService

# Ensure packages can be imported
sys.path.append("/modules")
sys.path.append("/services")

# Version
VERSION = "1.0.0"


async def main():
    # Dependencies
    led = LedService()
    options = OptionsService()
    messages = MessagesService(options)
    buttons = ButtonService(messages)
    portal = PortalService(options, messages)

    # Display the current version of the software
    await messages.display(f"Starting Pico Portal v{VERSION}")

    # Run
    uasyncio.create_task(led.flash())
    uasyncio.create_task(portal.run())
    uasyncio.create_task(buttons.run())

    # Keep the main loop running
    while True:
        await uasyncio.sleep(1)


if __name__ == "__main__":
    time.sleep(1)
    uasyncio.run(main())
