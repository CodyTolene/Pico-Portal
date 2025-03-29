import sys
import uasyncio  # type: ignore
import os

from services.messages_service import MessagesService
from services.options_service import OptionsService

# Ensure packages can be imported
sys.path.append("../modules")
sys.path.append("../services")


class MenuService:
    def __init__(self, messages: MessagesService, options: OptionsService):
        self.messages = messages
        self.options_service = options

        self.active = False
        self.selected_index = 0
        self.options = self.load_html_templates()

    def is_active(self):
        return self.active

    def load_html_templates(self):
        options = []
        try:
            files = os.listdir("templates")
            for filename in files:
                if filename.endswith(".html"):
                    options.append(
                        {
                            "label": filename,
                            "color": self.messages.GRAY,
                            "filename": filename,
                            "action": self.set_default_template,
                        }
                    )
        except Exception as e:
            print(f"Failed to load templates: {e}")
        return options

    async def toggle(self):
        self.active = not self.active
        if self.active:
            await self.render()
        else:
            await self.messages.display("Menu closed")

    async def scroll_up(self):
        if not self.active or not self.options:
            return
        self.selected_index = (self.selected_index - 1) % len(self.options)
        await self.render()

    async def scroll_down(self):
        if not self.active or not self.options:
            return
        self.selected_index = (self.selected_index + 1) % len(self.options)
        await self.render()

    async def select(self):
        if not self.active or not self.options:
            return
        selected = self.options[self.selected_index]
        await self.messages.display(f"Selected: {selected['label']}")
        await selected["action"](selected["filename"])

    async def set_default_template(self, filename):
        try:
            self.options_service.set_option("template", filename)
            await self.messages.display(f"Homepage set to: {filename}")
        except Exception as e:
            await self.messages.display(f"Failed to set default: {e}")

    async def render(self):
        await self.messages.display("=== SELECT TEMPLATE ===", log=False, delay=False)
        if not self.options:
            await self.messages.display("No templates found.", delay=False)
            return

        for i, option in enumerate(self.options):
            prefix = ">" if i == self.selected_index else " "
            label = option["label"]
            color = option.get("color", self.messages.GRAY)
            await self.messages.display(
                f"{prefix} {label}", color=color, log=False, delay=False
            )
