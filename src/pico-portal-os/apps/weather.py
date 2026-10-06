# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import gc
import uasyncio  # type: ignore

from . import App
from .keyboard import edit_text
from ..crt import CELL
from ..storage import save_config

_DIGITS = (
    "<DONE>",
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
    "<CLEAR>",
)
_WEATHER = {
    0: "CLEAR",
    1: "MOSTLY CLEAR",
    2: "PART CLOUD",
    3: "OVERCAST",
    45: "FOG",
    48: "RIME FOG",
    51: "DRIZZLE",
    53: "DRIZZLE",
    55: "DRIZZLE",
    61: "RAIN",
    63: "RAIN",
    65: "HEAVY RAIN",
    71: "SNOW",
    73: "SNOW",
    75: "HEAVY SNOW",
    80: "SHOWERS",
    81: "SHOWERS",
    82: "HEAVY SHOWERS",
    95: "THUNDER",
}
_TIMEZONES = {
    "UTC": "GMT",
    "Eastern": "America%2FNew_York",
    "Central": "America%2FChicago",
    "Mountain": "America%2FDenver",
    "Pacific": "America%2FLos_Angeles",
    "Alaska": "America%2FAnchorage",
    "Hawaii": "Pacific%2FHonolulu",
}


class Weather(App):

    async def run(self, ctx):
        data = None
        error = ""
        if ctx.weather_config.get("zip_code") and ctx.wifi.is_connected():
            data, error = self._load(ctx)
        while True:
            up, _down, select, back = ctx.input.poll()
            if back:
                return
            if up:
                changed = await self._set_zip(ctx)
                if changed and ctx.wifi.is_connected():
                    data, error = self._load(ctx)
            if select:
                if not ctx.weather_config.get("zip_code"):
                    await self._set_zip(ctx)
                if ctx.wifi.is_connected():
                    data, error = self._load(ctx)
                else:
                    error = "CONNECT WIFI FIRST"
            self._draw(ctx, data, error)
            await uasyncio.sleep_ms(80)

    async def _set_zip(self, ctx):
        value = await edit_text(
            ctx,
            "ZIP CODE",
            str(ctx.weather_config.get("zip_code", "")),
            max_length=10,
            keys=_DIGITS,
        )
        if not value:
            return False
        ctx.weather_config["zip_code"] = value
        ctx.weather_config["latitude"] = None
        ctx.weather_config["longitude"] = None
        ctx.weather_config["location"] = ""
        save_config(ctx.config)
        gc.collect()
        return True

    def _load(self, ctx):
        try:
            latitude = ctx.weather_config.get("latitude")
            longitude = ctx.weather_config.get("longitude")
            if latitude is None or longitude is None:
                query = "http://api.zippopotam.us/us/{}".format(
                    ctx.weather_config["zip_code"]
                )
                result = ctx.wifi.http_json(query)
                matches = result.get("places", ())
                if not matches:
                    return None, "ZIP NOT FOUND"
                place = matches[0]
                latitude = place["latitude"]
                longitude = place["longitude"]
                ctx.weather_config["latitude"] = latitude
                ctx.weather_config["longitude"] = longitude
                ctx.weather_config["location"] = place.get(
                    "place name", ctx.weather_config["zip_code"]
                )
                save_config(ctx.config)
                del result
                gc.collect()
            zone = _TIMEZONES.get(
                ctx.clock_config.get("timezone_name", "Central"),
                "America%2FChicago",
            )
            temp_unit = (
                "fahrenheit"
                if ctx.config["regional"].get("temperature_unit", "C") == "F"
                else "celsius"
            )
            wind_unit = (
                "kmh"
                if ctx.config["regional"].get("unit_system") == "metric"
                else "mph"
            )
            url = (
                "http://api.open-meteo.com/v1/forecast?latitude={}&longitude={}"
                "&current=temperature_2m,apparent_temperature,"
                "relative_humidity_2m,weather_code,wind_speed_10m"
                "&daily=temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
                "&temperature_unit={}&wind_speed_unit={}"
                "&timezone={}&forecast_days=3"
            ).format(latitude, longitude, temp_unit, wind_unit, zone)
            return ctx.wifi.http_json(url), ""
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)[:28]

    def _draw(self, ctx, data, error):
        crt = ctx.crt
        crt.begin()
        crt.text_center(
            "WEATHER // " + str(ctx.weather_config.get("zip_code") or "NO ZIP"),
            3,
            1,
            "hi",
        )
        if data:
            current = data.get("current", {})
            code = int(current.get("weather_code", -1))
            temp = current.get("temperature_2m", 0)
            temp_label = ctx.config["regional"].get("temperature_unit", "C")
            wind_label = (
                "km/h"
                if ctx.config["regional"].get("unit_system") == "metric"
                else "mph"
            )
            crt.text("{:.0f}{}".format(temp, temp_label), 8, 20, 4, "fg")
            self._icon(crt, code, crt.w - 48, 37)
            crt.text(
                _WEATHER.get(code, "CODE {}".format(code)), 10, 58, 1, "hi"
            )
            if crt.h > 160:
                metrics = "FEELS {:.0f}{}  HUM {}%  WIND {:.0f}{}".format(
                    current.get("apparent_temperature", 0),
                    temp_label,
                    current.get("relative_humidity_2m", 0),
                    current.get("wind_speed_10m", 0),
                    wind_label,
                )
            else:
                metrics = "FL{:.0f}{} H{} W{:.0f}{}".format(
                    current.get("apparent_temperature", 0),
                    temp_label,
                    current.get("relative_humidity_2m", 0),
                    current.get("wind_speed_10m", 0),
                    wind_label,
                )
            crt.text(crt.clip_text(metrics, crt.w - 20, 1), 10, 72, 1, "mid")
            self._daily(crt, data.get("daily", {}), 90, temp_label)
            if crt.h > 160:
                crt.text_center(
                    str(ctx.weather_config.get("location", "")),
                    crt.h - 26,
                    1,
                    "dim",
                )
        else:
            crt.text_center(
                error or "SET ZIP THEN LOAD",
                crt.h // 2 - 8,
                2,
                "warn" if error else "mid",
            )
            crt.text_center("WiFi required", crt.h // 2 + 18, 1, "dim")
        crt.button_hints(top_left="BACK", top_right="LOAD", bottom_left="ZIP")
        crt.end()

    def _daily(self, crt, daily, top, temp_label):
        dates = daily.get("time", ())
        highs = daily.get("temperature_2m_max", ())
        lows = daily.get("temperature_2m_min", ())
        rain = daily.get("precipitation_probability_max", ())
        for index in range(min(3, len(dates), len(highs), len(lows))):
            y = top + index * (CELL + 6)
            if y > crt.h - 2 * CELL:
                break
            crt.text(str(dates[index])[5:], 10, y, 1, "dim")
            crt.text(
                "{:>3.0f}/{:<3.0f}{}".format(
                    highs[index], lows[index], temp_label
                ),
                72,
                y,
                1,
                "fg",
            )
            chance = rain[index] if index < len(rain) else 0
            crt.text_right("{}% RAIN".format(chance), crt.w - 10, y, 1, "mid")

    def _icon(self, crt, code, cx, cy):
        if code == 0:
            crt.use("hi")
            crt.g.circle(cx, cy, 10)
            for offset in (-18, 18):
                crt.g.line(cx + offset, cy, cx + offset // 2, cy)
                crt.g.line(cx, cy + offset, cx, cy + offset // 2)
        else:
            crt.use("mid")
            crt.g.circle(cx - 8, cy, 9)
            crt.g.circle(cx + 3, cy - 4, 12)
            crt.g.rectangle(cx - 16, cy, 32, 10)
            if code >= 51:
                crt.use("fg")
                for x in (-10, 0, 10):
                    crt.g.line(cx + x, cy + 14, cx + x - 4, cy + 21)
