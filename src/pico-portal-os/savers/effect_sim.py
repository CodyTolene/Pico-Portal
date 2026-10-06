# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

from . import prng as random
from ..units import format_temperature


class Effects:
    async def _launch(self, ctx, name, show_title=True):
        self._show_title = show_title
        if name == "GAME OF LIFE":
            handler = self._life
        elif name == "NEURAL NET":
            handler = self._neural
        elif name == "SORTING":
            handler = self._sorting
        else:
            handler = self._system_dash
        await handler(ctx)

    def _leave(self, ctx):
        return any(ctx.input.poll())

    def _banner(self, crt, name, y=3):
        """
        Label the effect during menu previews only, never as an idle saver.
        """
        if self._show_title:
            crt.text_center(name, y, 1, "hi")

    async def _life(self, ctx):
        crt = ctx.crt
        cell = 6
        cols, rows = crt.w // cell, crt.h // cell
        board = bytearray(cols * rows)
        next_board = bytearray(cols * rows)
        for index in range(len(board)):
            board[index] = 1 if random.getrandbits(3) == 0 else 0
        while not self._leave(ctx):
            crt.begin()
            crt.use("fg")
            for y in range(rows):
                for x in range(cols):
                    index = y * cols + x
                    if board[index]:
                        crt.g.rectangle(
                            x * cell + 1, y * cell + 1, cell - 1, cell - 1
                        )
                    neighbors = 0
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dx or dy:
                                neighbors += board[
                                    ((y + dy) % rows) * cols + ((x + dx) % cols)
                                ]
                    next_board[index] = (
                        1
                        if neighbors == 3 or (board[index] and neighbors == 2)
                        else 0
                    )
            self._banner(crt, "GAME OF LIFE")
            crt.end()
            board, next_board = next_board, board
            await uasyncio.sleep_ms(90)

    async def _sorting(self, ctx):
        crt = ctx.crt
        count = 28
        values = [random.getrandbits(8) for _ in range(count)]
        index = 0
        while not self._leave(ctx):
            if index >= count - 1:
                values = [random.getrandbits(8) for _ in range(count)]
                index = 0
            if values[index] > values[index + 1]:
                values[index], values[index + 1] = (
                    values[index + 1],
                    values[index],
                )
            index += 1
            crt.begin()
            width = max(2, crt.w // count)
            for i, value in enumerate(values):
                height = 4 + value * (crt.h - 24) // 255
                crt.use("hi" if i == index else "mid")
                crt.g.rectangle(i * width, crt.h - height, width - 1, height)
            self._banner(crt, "SORTING")
            crt.end()
            await uasyncio.sleep_ms(25)

    async def _neural(self, ctx):
        crt = ctx.crt
        layers = (4, 7, 6, 3)
        pulse = 0
        positions = []
        for layer, count in enumerate(layers):
            x = 20 + layer * (crt.w - 40) // (len(layers) - 1)
            nodes = []
            for index in range(count):
                y = 18 + (index + 1) * (crt.h - 36) // (count + 1)
                nodes.append((x, y))
            positions.append(nodes)
        while not self._leave(ctx):
            crt.begin()
            for layer in range(len(positions) - 1):
                for a_index, start in enumerate(positions[layer]):
                    for b_index, end in enumerate(positions[layer + 1]):
                        crt.use(
                            "mid"
                            if (a_index + b_index + pulse) % 4 == 0
                            else "scan"
                        )
                        crt.g.line(start[0], start[1], end[0], end[1])
            for layer, nodes in enumerate(positions):
                for index, node in enumerate(nodes):
                    crt.use(
                        "hi" if (layer * 3 + index + pulse) % 7 == 0 else "fg"
                    )
                    crt.g.circle(node[0], node[1], 3)
            self._banner(crt, "NEURAL NET")
            crt.end()
            pulse += 1
            await uasyncio.sleep_ms(65)

    async def _system_dash(self, ctx):
        crt = ctx.crt
        history = []
        while not self._leave(ctx):
            temp = ctx.sensors.temperature()
            used, total = ctx.sensors.memory()
            flash_used, flash_total = ctx.sensors.flash()
            history.append(temp)
            while len(history) > 42:
                history.pop(0)
            crt.begin()
            self._banner(crt, "SYSTEM DASH")
            crt.text(format_temperature(temp, ctx.config, 1), 8, 22, 3, "fg")
            crt.box(
                crt.w // 2, 20, crt.w // 2 - 8, 32, "dim", title="CORE TEMP"
            )
            crt.sparkline(
                crt.w // 2 + 2, 23, crt.w // 2 - 14, 25, history, "fg", 40, 15
            )
            y = 66
            crt.text("SRAM", 8, y, 1, "mid")
            crt.bar(
                60, y, crt.w - 70, 10, used / total if total else 0, "fg", "dim"
            )
            crt.text("FLASH", 8, y + 20, 1, "mid")
            crt.bar(
                60,
                y + 20,
                crt.w - 70,
                10,
                flash_used / flash_total if flash_total else 0,
                "fg",
                "dim",
            )
            for index in range(14):
                height = 3 + (
                    (index * 17 + int(temp) * 5) % max(4, crt.h - y - 52)
                )
                crt.use("hi" if index > 10 else "dim")
                crt.g.rectangle(
                    10 + index * (crt.w - 20) // 14, crt.h - height, 4, height
                )
            crt.end()
            await uasyncio.sleep_ms(250)
