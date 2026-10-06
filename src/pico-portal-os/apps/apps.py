# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from . import App
from .submenu import run_submenu

_APPS = (
    (
        "BIBLE",
        "Bible Verses",
        "apps.bibleverses",
        "BibleVerses",
        "Offline readings and reflection",
        "/pico-portal-os/images/bible.bin",
    ),
    (
        "DICE",
        "Dice Roller",
        "apps.diceroller",
        "DiceRoller",
        "Dice, coin, and fortunes",
        "/pico-portal-os/images/dice.bin",
    ),
    (
        "STOPWATCH",
        "Stopwatch",
        "apps.stopwatch",
        "Stopwatch",
        "Timer and lap splits",
        "/pico-portal-os/images/stopwatch.bin",
    ),
    (
        "WEATHER",
        "Weather",
        "apps.weather",
        "Weather",
        "Forecast by ZIP code",
        "/pico-portal-os/images/weather.bin",
    ),
)


class Apps(App):

    async def run(self, ctx):
        await run_submenu(ctx, "APPS", _APPS)
