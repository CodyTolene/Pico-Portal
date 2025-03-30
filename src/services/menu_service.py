# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service to handle the menu functionality for the Pico
#  Portal device. This service will allow the user to select a template from
#  the available templates and set it as the default template for the portal.
# =============================================================================

import sys
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
        self.last_render_line_count = 0
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
        if self.active:
            self.clear_rendered_lines()
            self.selected_index = 0
            await self.messages.display("Menu closed", show_timestamp=False)
        else:
            await self.render()
        self.active = not self.active

    def clear_rendered_lines(self):
        if self.last_render_line_count > 0:
            self.messages.delete_last_lines(self.last_render_line_count)
            self.last_render_line_count = 0

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

        self.clear_rendered_lines()
        self.active = False

        await self.messages.display(f"Selected: {selected['label']}")
        await selected["action"](selected["filename"])

    async def set_default_template(self, filename):
        try:
            self.options_service.set_option("template", filename)
            await self.messages.display(f"Homepage set to: {filename}")
        except Exception as e:
            await self.messages.display(f"Failed to set default: {e}")

    async def render(self):
        self.clear_rendered_lines()

        self.options = self.load_html_templates()

        line_count = 0
        line_count += await self.messages.display(
            "=== SELECT TEMPLATE ===", log=False, delay=False, show_timestamp=False
        )

        if not self.options:
            line_count += await self.messages.display(
                "No templates found.", delay=False, show_timestamp=False
            )
            self.last_render_line_count = line_count
            return

        for i, option in enumerate(self.options):
            prefix = ">" if i == self.selected_index else " "
            label = option["label"]
            color = option.get("color", self.messages.GRAY)
            line_count += await self.messages.display(
                f"{prefix} {label}",
                color=color,
                log=False,
                delay=False,
                show_timestamp=False,
            )

        self.last_render_line_count = line_count
