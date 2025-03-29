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
from services.menu_service import MenuService

# Ensure packages can be imported
sys.path.append("../modules")
sys.path.append("../services")


class ButtonService:
    def __init__(self, menu: MenuService, messages: MessagesService):
        # Dependencies
        self.messages = messages
        self.menu = menu

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

            await uasyncio.sleep(0.05)

    async def handle_button_a(self):
        if self.button_a.read():
            await self.menu.select()
            await self.menu.toggle()

    async def handle_button_b(self):
        if self.button_b.read():
            await self.menu.toggle()

    async def handle_button_x(self):
        if self.button_x.read():
            if self.menu.is_active():
                await self.menu.scroll_down()
            else:
                await self.scroll_continuously(self.messages.scroll_down)

    async def handle_button_y(self):
        if self.button_y.read():
            if self.menu.is_active():
                await self.menu.scroll_up()
            else:
                await self.scroll_continuously(self.messages.scroll_up)

    async def scroll_continuously(self, scroll_function):
        # Continue scrolling as long as the button is pressed
        while True:
            scroll_function()
            await uasyncio.sleep(0.2)  # Adjust the scrolling speed
            if not self.button_a.read() and not self.button_x.read():
                break


# Testing
if __name__ == "__main__":
    from services.options_service import OptionsService

    async def wait_for_button(button, label="button"):
        while not button.read():
            await uasyncio.sleep(0.05)
        while button.read():
            await uasyncio.sleep(0.05)
        return

    async def main():
        options = OptionsService()
        messages = MessagesService(options)
        menu = MenuService(messages)
        button_service = ButtonService(menu, messages)

        # Start the button service
        uasyncio.create_task(button_service.run())

        await messages.display("Pico Portal Button Test", color=messages.GREEN)
        await messages.display("Press Button B to toggle the menu")

        await wait_for_button(button_service.button_b, "B")
        await uasyncio.sleep(0.2)
        await messages.display("Menu opened. Press X to scroll down")

        await wait_for_button(button_service.button_x, "X")
        await messages.display("Scrolled down. Press Y to scroll up")

        await wait_for_button(button_service.button_y, "Y")
        await messages.display("Scrolled up. Press A to select")

        await wait_for_button(button_service.button_a, "A")
        await messages.display("Selection triggered. Press B to close menu")

        await wait_for_button(button_service.button_b, "B")
        await messages.display(
            "Menu closed. Button test complete!", color=messages.GREEN
        )

        await messages.display(
            "You may now try buttons freely. Press any button to see it logged."
        )

        prev_states = {
            "A": False,
            "B": False,
            "X": False,
            "Y": False,
        }

        while True:
            a = button_service.button_a.read()
            b = button_service.button_b.read()
            x = button_service.button_x.read()
            y = button_service.button_y.read()

            # Show any button press
            if a and not prev_states["A"]:
                await messages.display("Button A pressed")
            if b and not prev_states["B"]:
                await messages.display("Button B pressed")
            if x and not prev_states["X"]:
                await messages.display("Button X pressed")
            if y and not prev_states["Y"]:
                await messages.display("Button Y pressed")

            # Update states
            prev_states["A"] = a
            prev_states["B"] = b
            prev_states["X"] = x
            prev_states["Y"] = y

            await uasyncio.sleep(0.05)

    uasyncio.run(main())
