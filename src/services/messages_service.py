# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service for displaying messages on the Pico Portal screen,
#  with support for timestamps, colors, and scrolling. Messages are also logged
#  to a log.txt file and output to the console.
# =============================================================================

import sys
import uasyncio  # type: ignore
import utime  # type: ignore
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY, DISPLAY_PICO_DISPLAY_2  # type: ignore

# Local packages
from services.options_service import OptionsDisplayTypes, OptionKeys, OptionsService

# Ensure packages can be imported
sys.path.append("../modules")
sys.path.append("../services")


class MessagesService:
    def __init__(self, options: OptionsService):
        display_type: OptionsDisplayTypes = options.get_option(OptionKeys.DISPLAY_TYPE)
        self.enable_timestamps: bool = options.get_option(OptionKeys.ENABLE_TIMESTAMPS)

        # Initialize the display based on the display_type
        if display_type == OptionsDisplayTypes.DISPLAY_PICO_DISPLAY:
            self.graphics = PicoGraphics(display=DISPLAY_PICO_DISPLAY)
            self.rotation = 0  # No rotation needed for DISPLAY_PICO_DISPLAY
        elif display_type == OptionsDisplayTypes.DISPLAY_PICO_DISPLAY_2:
            self.graphics = PicoGraphics(display=DISPLAY_PICO_DISPLAY_2, rotate=270)
            self.rotation = 270  # Rotate DISPLAY_PICO_DISPLAY_2 to match orientation
        else:
            raise ValueError("Invalid display type")

        # Initialize drawing properties
        self.BLACK = self.graphics.create_pen(0, 0, 0)
        self.GRAY = self.graphics.create_pen(150, 150, 150)
        self.GREEN = self.graphics.create_pen(0, 200, 0)
        self.RED = self.graphics.create_pen(255, 0, 0)
        self.WHITE = self.graphics.create_pen(255, 255, 255)
        self.line_height = 13
        self.margin = 10

        # Define max_lines for the selected display
        self.max_lines = (
            self.graphics.get_bounds()[1] - self.margin * 2
        ) // self.line_height

        self.messages = []
        self.scroll_position = 0

        # Use system font that supports lowercase and better character
        # distinction
        self.graphics.set_font("bitmap8")

    def calculate_total_lines(self):
        total_lines = 0
        for msg, _ in self.messages:  # Process only the message text, not the color
            wrapped_lines = self.calculate_wrapped_lines(msg)
            total_lines += wrapped_lines
        return total_lines

    def calculate_wrapped_lines(self, message):
        # Calculate the number of lines a message would take after wrapping
        max_width = self.graphics.get_bounds()[0] - self.margin * 2
        wrapped_lines = 1
        current_line_length = 0

        for word in message.split():
            word_length = self.graphics.measure_text(word, scale=1)
            if current_line_length + word_length <= max_width:
                current_line_length += word_length + self.graphics.measure_text(
                    " ", scale=1
                )
            else:
                wrapped_lines += 1
                current_line_length = word_length + self.graphics.measure_text(
                    " ", scale=1
                )

        return wrapped_lines

    async def display(self, message, log=True, color=None):
        if self.enable_timestamps:
            # Prepend the current date and time to the message in the format
            # "2024-09-02 18:58:08"
            current_time = utime.localtime()
            formatted_time = "{:04}-{:02}-{:02} {:02}:{:02}:{:02}".format(
                current_time[0],
                current_time[1],
                current_time[2],
                current_time[3],
                current_time[4],
                current_time[5],
            )
            # Display timestamp and message on separate lines for the screen
            display_message = f"[{formatted_time}]\n{message}"
            # Log timestamp and message on the same line for log.txt
            log_message = f"[{formatted_time}] {message}"
        else:
            display_message = message
            log_message = message

        # Set the color, default to GRAY if not provided
        if color is None:
            color = self.GRAY

        # Add the display message and its color to the list of messages
        self.messages.append((f"> {display_message}", color))

        # Calculate the total number of lines in all messages
        total_lines = self.calculate_total_lines()

        # If total lines exceed the maximum, adjust the scroll position
        if total_lines > self.max_lines:
            self.scroll_position = total_lines - self.max_lines

        # Update the display
        self.update_display(total_lines)

        if log:
            print(log_message)
            self.log_to_file(log_message)

        await uasyncio.sleep(1)

    def update_display(self, total_lines):
        # Clear the display
        self.graphics.set_pen(self.WHITE)
        self.graphics.clear()

        y = self.margin
        current_line = 0

        for msg, color in self.messages:
            wrapped_lines = self.calculate_wrapped_lines(msg)
            if current_line + wrapped_lines > self.scroll_position:
                if msg.startswith("["):
                    # Extract timestamp and rest of the message
                    timestamp, rest = msg.split("\n", 1)
                    self.graphics.set_pen(self.BLACK)
                    self.graphics.text(
                        timestamp,
                        self.margin,
                        y,
                        wordwrap=self.graphics.get_bounds()[0] - self.margin * 2,
                        scale=1,
                    )
                    y += self.line_height  # Move to next line after timestamp
                    msg = rest  # Remaining message text

                self.graphics.set_pen(color)
                # Split message into lines manually for better handling
                lines = self.split_message_into_lines(msg)
                for line in lines:
                    if current_line >= self.scroll_position:
                        self.graphics.text(
                            line,
                            self.margin,
                            y,
                            wordwrap=self.graphics.get_bounds()[0] - self.margin * 2,
                            scale=1,
                        )
                        y += self.line_height
                    current_line += 1

            current_line += wrapped_lines

        self.draw_scroll_bar(total_lines)
        self.graphics.update()

    def split_message_into_lines(self, message):
        max_width = self.graphics.get_bounds()[0] - self.margin * 2
        lines = []
        current_line = ""

        # Process the message character by character
        for char in message:
            if self.graphics.measure_text(current_line + char, scale=1) <= max_width:
                current_line += char
            else:
                lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

        return lines

    def draw_scroll_bar(self, total_lines):
        # Calculate the height and position of the scroll bar
        display_height = self.graphics.get_bounds()[1]
        if total_lines <= self.max_lines:
            return  # No need to draw a scroll bar if content fits within the screen

        scroll_bar_height = max(int(display_height * (self.max_lines / total_lines)), 5)
        scrollable_area_height = display_height - scroll_bar_height
        scroll_ratio = self.scroll_position / (total_lines - self.max_lines)
        scroll_bar_position = int(scrollable_area_height * scroll_ratio)

        # Draw the scroll bar
        self.graphics.set_pen(self.BLACK)
        self.graphics.rectangle(
            self.graphics.get_bounds()[0] - 5, scroll_bar_position, 5, scroll_bar_height
        )

    # Scroll up by one line
    def scroll_up(self):
        if self.scroll_position > 0:
            self.scroll_position -= 1
            self.update_display(self.calculate_total_lines())

    # Scroll down by one line
    def scroll_down(self):
        total_lines = self.calculate_total_lines()
        if self.scroll_position < total_lines - self.max_lines:
            self.scroll_position += 1
            self.update_display(total_lines)

    # Scroll to the top of the messages
    def scroll_top(self):
        self.scroll_position = 0
        self.update_display(self.calculate_total_lines())

    # Scroll to the bottom of the messages
    def scroll_bottom(self):
        total_lines = self.calculate_total_lines()
        if total_lines > self.max_lines:
            self.scroll_position = total_lines - self.max_lines
            self.update_display(total_lines)

    # Append a message to the log.txt file on a single line
    def log_to_file(self, message):
        try:
            with open("log.txt", "a") as log_file:
                log_file.write(message + "\n")
        except Exception as e:
            print(f"Failed to log message: {e}")


# Testing
if __name__ == "__main__":

    async def main():
        options = OptionsService()
        display_type: OptionsDisplayTypes = options.get_option(OptionKeys.DISPLAY_TYPE)

        messages = MessagesService(display_type)
        GREEN = messages.GREEN
        RED = messages.RED

        # Simulate displaying messages with different colors
        await messages.display("Success (green) message.", color=GREEN)
        await messages.display("Error (red) message!", color=RED)
        await messages.display("Normal (gray) message.")

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

        # Scroll up x25
        for i in range(25):
            messages.scroll_up()

        await uasyncio.sleep(2)

        # Scroll down x20
        for i in range(20):
            messages.scroll_down()

        await uasyncio.sleep(1)

        # Scroll to top
        messages.scroll_top()
        await uasyncio.sleep(1)

        # Scroll to bottom
        messages.scroll_bottom()

    uasyncio.run(main())
