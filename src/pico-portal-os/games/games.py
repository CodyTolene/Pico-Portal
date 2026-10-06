# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from ..apps import App
from ..apps.submenu import run_submenu

_GAMES = (
    (
        "BREAKOUT",
        "Breakout",
        "games.breakout",
        "Breakout",
        "Brick-breaking arcade",
        "/pico-portal-os/images/breakout.bin",
    ),
    (
        "REFLEX",
        "Reflex",
        "games.reflex",
        "Reflex",
        "Reaction-time test",
        "/pico-portal-os/images/press.bin",
    ),
    (
        "SNAKE",
        "Snake",
        "games.snake",
        "Snake",
        "Eat, grow, and survive",
        "/pico-portal-os/images/snake.bin",
    ),
    (
        "TETRIS",
        "Tetris",
        "games.tetris",
        "Tetris",
        "Falling block puzzle",
        "/pico-portal-os/images/tetris.bin",
    ),
)


class Games(App):

    async def run(self, ctx):
        await run_submenu(ctx, "GAMES", _GAMES)
