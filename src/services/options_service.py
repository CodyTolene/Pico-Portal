# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  Repository: https://github.com/CodyTolene/Pico-Portal
#  Description: A service to handle user defined options from a JSON file.
# =============================================================================

import json


class OptionsDisplayTypes:
    DISPLAY_PICO_DISPLAY = "DISPLAY_PICO_DISPLAY"
    DISPLAY_PICO_DISPLAY_2 = "DISPLAY_PICO_DISPLAY_2"


class OptionKeys:
    WIFI_SSID: str = "wifi_ssid"  # Default: "WiFi"
    WIFI_PASSWORD: str = "wifi_password"  # Default: ""
    WIFI_DOMAIN: str = "wifi_domain"  # Default: "setup.local"
    DISPLAY_TYPE: OptionsDisplayTypes = "display_type"  # Default: DISPLAY_PICO_DISPLAY
    ENABLE_TIMESTAMPS: bool = "enable_timestamps"  # Default: false
    LED_BRIGHTNESS = "led_brightness"  # Default: 0.25 (0.0 - 1.0)


class OptionsService:
    def __init__(self):
        # Properties
        self.json_file_path = "/options.json"

        # Initialization
        self.options = self.load_options()

    def load_options(self):
        try:
            with open(self.json_file_path, "r") as f:
                data = json.load(f)
                return data
        except OSError:
            self.save_options(self.default_options())
            return self.default_options()
        except ValueError:
            self.save_options(self.default_options())
            return self.default_options()

    def save_options(self, options):
        try:
            with open(self.json_file_path, "w") as f:
                json.dump(options, f)
        except OSError as e:
            print(f"Error writing to {self.json_file_path}: {e}")

    def get_option(self, key: OptionKeys, default=None):
        return self.options.get(key, default)

    def set_option(self, key: OptionKeys, value):
        self.options[key] = value
        self.save_options(self.options)

    def default_options(self):
        return {
            OptionKeys.WIFI_SSID: "WiFi",
            OptionKeys.WIFI_PASSWORD: "",
            OptionKeys.WIFI_DOMAIN: "setup.local",
            OptionKeys.DISPLAY_TYPE: OptionsDisplayTypes.DISPLAY_PICO_DISPLAY,
            OptionKeys.ENABLE_TIMESTAMPS: False,
            OptionKeys.LED_BRIGHTNESS: 0.25,
        }
