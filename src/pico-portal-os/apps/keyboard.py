# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import uasyncio  # type: ignore

_KEYS = (
    "<DONE>",
    "<SPACE>",
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "-",
    "_",
    ".",
    "!",
    "@",
    "#",
    "$",
    "%",
    "&",
    "+",
    "=",
    "?",
    "<CLEAR>",
)


async def edit_text(
    ctx, title, initial="", secret=False, max_length=63, keys=None
):
    """Edit text with four controls; return None when cancelled from empty."""
    value = initial
    key = 0
    choices = keys or _KEYS
    while True:
        up, down, select, back = ctx.input.poll()
        if up:
            key = (key - 1) % len(choices)
        if down:
            key = (key + 1) % len(choices)
        if back:
            if value:
                value = value[:-1]
            else:
                return None
        if select:
            choice = choices[key]
            if choice == "<DONE>":
                return value
            if choice == "<CLEAR>":
                value = ""
            elif len(value) < max_length:
                value += " " if choice == "<SPACE>" else choice

        _draw(ctx.crt, title, value, choices[key], secret)
        await uasyncio.sleep_ms(45)


def _draw(crt, title, value, choice, secret):
    crt.begin()
    top = crt.ui_title(title)

    shown = "*" * len(value) if secret else value
    value_scale = crt.preferred_scale()
    max_chars = max(4, (crt.w - 28) // max(1, crt.measure("M", value_scale)))
    shown = shown[-max_chars:]
    field_h = crt.text_height(value_scale) + 12
    crt.box(8, top, crt.w - 16, field_h, "dim")
    field_y = top + 6
    crt.text(shown, 14, field_y, value_scale, "fg")
    crt.cursor(
        14 + crt.measure(shown, value_scale),
        field_y,
        value_scale,
        "hi",
        crt.blink(),
    )

    y = top + field_h + 5
    prompt_scale = crt.fit_scale("CHOOSE CHARACTER", crt.w - 20)
    crt.text_center("CHOOSE CHARACTER", y, prompt_scale, "dim")
    choice_scale = crt.fit_scale(choice, crt.w - 50)
    choice_y = y + crt.text_height(prompt_scale) + 4
    choice_h = crt.text_height(choice_scale) + 8
    width = min(crt.w - 30, max(76, crt.measure(choice, choice_scale) + 20))
    x = (crt.w - width) // 2
    crt.use("mid")
    crt.g.rectangle(x, choice_y, width, choice_h)
    crt.text_center(choice, choice_y + 4, choice_scale, "bg")

    help_text = "DEL removes; DEL on empty cancels"
    help_y = choice_y + choice_h + 5
    help_scale = crt.fit_scale(help_text, crt.w - 20)
    if help_y + crt.text_height(help_scale) < crt.ui_bottom():
        crt.text_center(help_text, help_y, help_scale, "dim")
    crt.button_hints(
        top_left="DEL",
        top_right="ADD",
        bottom_left="PREV",
        bottom_right="NEXT",
    )
    crt.end()
