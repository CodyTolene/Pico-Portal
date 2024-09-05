# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service to handle button inputs and trigger actions based on
#  the button presses.
# =============================================================================

from pimoroni import Button  # type: ignore
import sys
import uasyncio  # type: ignore

# Local packages
from services.messages_service import MessagesService

# Ensure packages can be imported
sys.path.append("../modules")
sys.path.append("../services")


class ButtonService:
    def __init__(self, messages: MessagesService):
        # Dependencies
        self.messages = messages

        # Initialize buttons
        self.button_a = Button(12)  # Button A
        self.button_b = Button(13)  # Button B
        self.button_x = Button(14)  # Button X
        self.button_y = Button(15)  # Button Y

        # Initialize button states
        self.button_states = {
            "B": False,
            "Y": False,
        }

    async def run(self):
        while True:
            # Handle button presses
            await self.handle_button_a()
            await self.handle_button_b()
            await self.handle_button_x()
            await self.handle_button_y()

            # Sleep for a short period to debounce button presses
            await uasyncio.sleep(0.1)

    async def handle_button_a(self):
        if self.button_a.read():
            await self.scroll_continuously(self.messages.scroll_up)
        else:
            await uasyncio.sleep(0.1)

    async def handle_button_b(self):
        if self.button_b.read():
            if not self.button_states["B"]:
                self.button_states["B"] = True
                self.messages.scroll_top()
        else:
            self.button_states["B"] = False

    async def handle_button_x(self):
        if self.button_x.read():
            await self.scroll_continuously(self.messages.scroll_down)
        else:
            await uasyncio.sleep(0.1)

    async def handle_button_y(self):
        if self.button_y.read():
            if not self.button_states["Y"]:
                self.button_states["Y"] = True
                self.messages.scroll_bottom()
        else:
            self.button_states["Y"] = False

    async def scroll_continuously(self, scroll_function):
        # Continue scrolling as long as the button is pressed
        while True:
            scroll_function()
            await uasyncio.sleep(0.2)  # Adjust the scrolling speed
            if not self.button_a.read() and not self.button_x.read():
                break


# Testing
if __name__ == "__main__":
    from services.options_service import OptionsDisplayTypes, OptionsService, OptionKeys

    async def main():
        options = OptionsService()
        display_type: OptionsDisplayTypes = options.get_option(OptionKeys.DISPLAY_TYPE)

        messages = MessagesService(display_type)
        button_service = ButtonService(messages)

        # Start the button service
        uasyncio.create_task(button_service.run())

        # Simulate displaying messages
        await messages.display("Success (green) message.", color=messages.GREEN)
        await messages.display("Error (red) message!", color=messages.RED)
        await messages.display("Normal (gray) message.")
        await messages.display("Normal (gray) message, no timestamp.", timestamp=False)

        # Test an extra long string that has no spaces
        await messages.display(
            "ThisIsALongStringThatShouldBeWrappedIntoMultipleLinesBecauseItDoesNotHaveSpaces",
            log=False,
        )

        # Simulate messages displaying until scrollbar appears
        for i in range(20):
            await messages.display(f"Message {i + 1}: Lorem ipsum dolor sit amet")

        # Start the scroll test
        await messages.display("Scroll test starting...", log=False)
        await uasyncio.sleep(1)

        # Keep the event loop running indefinitely to continue processing
        # button inputs
        while True:
            await uasyncio.sleep(1)

    uasyncio.run(main())
