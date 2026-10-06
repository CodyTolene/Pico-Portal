# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
#  SPDX-License-Identifier: CC-BY-NC-4.0
# =============================================================================
"""Check config schema and JSON persistence without Pico hardware."""

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from jsonschema import Draft7Validator

sys.dont_write_bytecode = True
source = Path(__file__).resolve().parents[2] / "src/pico-portal-os/storage.py"
spec = importlib.util.spec_from_file_location("portal_storage", source)
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pico-portal-config-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = (self.root / "config.json").as_posix()

    def write(self, data):
        Path(self.path).write_text(json.dumps(data), encoding="utf-8")

    def sorted_object(self, pairs):
        names = [key for key, _value in pairs]
        self.assertEqual(names, sorted(names))
        return dict(pairs)

    def test_missing_or_invalid_files_use_independent_defaults(self):
        for content in (None, "[]", "broken JSON"):
            with self.subTest(content=content):
                if content is not None:
                    Path(self.path).write_text(content, encoding="utf-8")
                first = storage.load_config(self.path)
                first["wifi"]["ssid"] = "changed"
                second = storage.load_config(self.path)
                self.assertEqual(second["wifi"]["ssid"], "")
                self.assertEqual(second["clock"]["utc_offset_hours"], -6)
                self.assertIsNone(second["weather"]["latitude"])
                self.assertEqual(storage.DEFAULT_CONFIG["wifi"]["ssid"], "")

    def test_nested_defaults_and_app_settings_survive(self):
        self.write(
            {
                "display": {"theme": "amber"},
                "regional": {"hour_format": 12, "temperature_unit": "F"},
                "wifi": {"ssid": "fixture", "future": "retained"},
                "weather": {"zip_code": "12345"},
                "clock": {"timezone_name": "UTC", "utc_offset_hours": 0},
            }
        )
        config = storage.load_config(self.path)
        self.assertEqual(config["wifi"]["password"], "")
        self.assertEqual(config["wifi"]["future"], "retained")
        self.assertEqual(config["weather"]["location"], "")
        self.assertTrue(config["clock"]["daylight_saving"])
        self.assertEqual(config["display"]["theme"], "amber")
        self.assertEqual(config["display"]["brightness"], 0.9)
        self.assertEqual(config["regional"]["hour_format"], 12)

    def test_invalid_sections_and_values_are_normalized(self):
        self.write(
            {
                "clock": None,
                "display": {
                    "brightness": 3,
                    "font_px": "bad",
                    "theme": "bad",
                },
                "led": {"brightness": 0.01, "status": "bad"},
                "regional": {
                    "hour_format": 99,
                    "temperature_unit": "f",
                    "unit_system": "METRIC",
                },
                "screensaver": {"timeout": -5},
                "wifi": [],
            }
        )
        config = storage.load_config(self.path)
        self.assertEqual(config["display"]["brightness"], 1)
        self.assertEqual(config["display"]["font_px"], 8)
        self.assertEqual(config["display"]["theme"], "green")
        self.assertEqual(config["led"]["brightness"], 0.05)
        self.assertEqual(config["led"]["status"], "heartbeat")
        self.assertEqual(config["regional"]["hour_format"], 24)
        self.assertEqual(config["regional"]["temperature_unit"], "F")
        self.assertEqual(config["regional"]["unit_system"], "metric")
        self.assertEqual(config["screensaver"]["timeout"], 0)
        self.assertEqual(config["clock"]["timezone_name"], "Central")
        self.assertEqual(config["wifi"], {"password": "", "ssid": ""})

    def test_saving_app_changes_preserves_all_other_settings(self):
        config = storage.load_config(self.path)
        config["display"]["theme"] = "amber"
        config["wifi"].update(ssid="fixture", password="fixture")
        config["weather"]["zip_code"] = "12345"
        config["clock"]["daylight_saving"] = False
        storage.save_config(config, self.path)
        restored = storage.load_config(self.path)
        self.assertEqual(restored, config)
        restored["wifi"].update(ssid="", password="")
        storage.save_config(restored, self.path)
        restored = storage.load_config(self.path)
        self.assertEqual(restored["weather"]["zip_code"], "12345")
        self.assertFalse(restored["clock"]["daylight_saving"])
        self.assertEqual(restored["display"]["theme"], "amber")

    def test_saved_properties_are_sorted_in_objects_and_arrays(self):
        config = {
            "z": {"z": 'quote: " and é', "a": None},
            "a": [True, 1, {"z": {}, "a": []}],
        }
        storage.save_config(config, self.path)
        text = Path(self.path).read_text(encoding="utf-8")
        self.assertEqual(
            json.loads(text, object_pairs_hook=self.sorted_object), config
        )
        self.assertTrue(text.endswith("\n"))

    def test_shipped_config_has_sorted_groups_and_properties(self):
        path = source.parent.parent / "config.json"
        config = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=self.sorted_object,
        )
        schema_path = path.parent / config.pop("$schema")
        self.assertTrue(schema_path.is_file())
        self.assertEqual(set(config), set(storage.DEFAULT_CONFIG))
        for key, defaults in storage.DEFAULT_CONFIG.items():
            self.assertEqual(set(config[key]), set(defaults))


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = source.parent.parent / "config.json"
        cls.config = json.loads(path.read_text(encoding="utf-8"))
        schema_path = path.parent / cls.config["$schema"]
        cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(cls.schema)
        cls.validator = Draft7Validator(cls.schema)

    def literal(self, relative, name):
        path = source.parent / relative
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                return ast.literal_eval(node.value)
        self.fail("Missing constant: " + name)

    def test_schema_covers_current_fields_and_runtime_defaults(self):
        self.validator.validate(self.config)
        self.validator.validate(storage.DEFAULT_CONFIG)
        groups = dict(self.schema["properties"])
        groups.pop("$schema")
        self.assertEqual(set(groups), set(storage.DEFAULT_CONFIG))
        for name, defaults in storage.DEFAULT_CONFIG.items():
            group = groups[name]
            self.assertTrue(group["description"])
            self.assertFalse(group["additionalProperties"])
            self.assertEqual(set(group["properties"]), set(defaults))
            for field, default in defaults.items():
                definition = group["properties"][field]
                self.assertEqual(definition["default"], default)
                self.assertTrue(definition["description"])

    def test_choices_match_runtime_catalogs_without_device_imports(self):
        properties = self.schema["properties"]
        choices = (
            ("display", "theme", self.literal("crt.py", "THEME_NAMES")),
            (
                "display",
                "type",
                ("auto",) + self.literal("hardware.py", "DISPLAY_TYPES"),
            ),
            (
                "screensaver",
                "name",
                self.literal("savers/catalog.py", "SAVER_NAMES"),
            ),
            (
                "clock",
                "timezone_name",
                [
                    name
                    for name, _offset in self.literal(
                        "settings/clocksettings.py", "_ZONES"
                    )
                ],
            ),
        )
        for group, field, values in choices:
            with self.subTest(group=group, field=field):
                enum = properties[group]["properties"][field]["enum"]
                self.assertEqual(set(enum), set(values))

    def test_partial_config_and_weather_cache_formats_are_valid(self):
        for config in (
            {},
            {"display": {"theme": "amber"}},
            {"weather": {"latitude": "41.88", "longitude": "-87.63"}},
            {"weather": {"latitude": 41.88, "longitude": -87.63}},
            {"weather": {"latitude": None, "longitude": None}},
            {"portal": {"template": "custom.HTM", "password": "12345678"}},
            {"portal": {"template": "", "password": ""}},
            {"led": {"brightness": 0}},
            {"screensaver": {"timeout": 0}},
        ):
            with self.subTest(config=config):
                self.validator.validate(config)

    def test_invalid_settings_and_unknown_fields_are_rejected(self):
        for config in (
            {"brightness": 0.9},
            {"display": {"typo": True}},
            {"display": {"brightness": 1.1}},
            {"display": {"brightness": "0.9"}},
            {"display": {"font_px": 9}},
            {"display": {"scanlines": "true"}},
            {"display": {"theme": "pink"}},
            {"display": {"type": "unknown"}},
            {"led": {"brightness": 0.01}},
            {"led": {"status": "invalid"}},
            {"clock": {"utc_offset_hours": 15}},
            {"clock": {"utc_offset_hours": 5.5}},
            {"clock": {"daylight_saving": 1}},
            {"regional": {"hour_format": 13}},
            {"regional": {"temperature_unit": "Kelvin"}},
            {"regional": {"unit_system": "unknown"}},
            {"screensaver": {"timeout": -1}},
            {"screensaver": {"name": "unknown"}},
            {"portal": {"password": "short"}},
            {"portal": {"password": "x" * 64}},
            {"portal": {"ssid": ""}},
            {"portal": {"template": "../example.html"}},
            {"portal": {"success_template": "folder\\success.html"}},
            {"portal": {"template": "file.txt"}},
            {"weather": {"latitude": 91}},
            {"weather": {"longitude": -181}},
            {"weather": {"latitude": "invalid"}},
            {"weather": {"zip_code": "abc"}},
            {"wifi": {"ssid": "x" * 33}},
            {"wifi": {"password": "x" * 64}},
            {"wifi": []},
        ):
            with self.subTest(config=config):
                self.assertFalse(self.validator.is_valid(config))

    def test_schema_metadata_is_ignored_by_runtime_load_and_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps(self.config), encoding="utf-8")
            config = storage.load_config(path.as_posix())
            self.assertNotIn("$schema", config)
            storage.save_config(config, path.as_posix())
            self.validator.validate(json.loads(path.read_bytes()))


if __name__ == "__main__":
    unittest.main()
