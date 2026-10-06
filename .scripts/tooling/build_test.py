# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tooling.files import (  # noqa: E402
    ensure_clean_output,
    files_under,
    validate_output,
)
from tooling.pipeline import run_build  # noqa: E402
from tooling.tools import cross_compile  # noqa: E402


class DeviceBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pico-portal-build-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, relative, content=b""):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            content.encode() if isinstance(content, str) else content
        )
        return path

    def test_discovery_skips_caches_and_cleanup_stays_in_dist(self):
        self.write("src/main.py")
        self.write("src/pico-portal-os/__init__.py")
        self.write("src/__pycache__/main.pyc")
        self.write("src/loose.pyc")
        self.write("src/.DS_Store")
        source = self.root / "src"
        discovered = [
            p.relative_to(source).as_posix() for p in files_under(source)
        ]
        self.assertEqual(discovered, ["main.py", "pico-portal-os/__init__.py"])
        with self.assertRaisesRegex(ValueError, "unexpected output path"):
            ensure_clean_output(self.root, source)
        self.write("dist/stale.py")
        ensure_clean_output(self.root, self.root / "dist")
        self.assertEqual(files_under(self.root / "dist"), [])
        self.assertEqual(len(files_under(source)), 2)

    def test_output_requires_expected_files_and_rejects_caches(self):
        expected = {"main.py", "pico-portal-os/tool.mpy"}
        self.write("main.py")
        self.write("pico-portal-os/tool.mpy")
        validate_output(self.root, expected)
        with self.assertRaisesRegex(ValueError, "output mismatch"):
            validate_output(self.root, {"main.py", "pico-portal-os/tool.py"})
        self.write("loose.pyc")
        with self.assertRaisesRegex(ValueError, "Python cache"):
            validate_output(self.root, expected)

    def test_output_rejects_absolute_host_paths(self):
        for content, label in (
            (
                b'source = "C:\\Users\\Code\\source.py"\n',
                "Windows absolute path",
            ),
            (b"/home/developer/source.py", "user home path"),
        ):
            with self.subTest(label=label):
                self.write("main.py", content)
                with self.assertRaisesRegex(ValueError, label):
                    validate_output(self.root)

    def test_build_preserves_assets_json_values_and_source_tree(self):
        unchanged = {
            "main.py": b'app = __import__("pico-portal-os")\r\n',
            "pico-portal-os/__init__.py": b'"""Package docs."""\n',
            "pico-portal-os/tool.py": (
                b"# Keep this comment.\n"
                b"def descriptive_name(parameter_name):\n"
                b'    """Keep this docstring."""\n'
                b"    local_name = parameter_name\n"
                b"    return local_name\n"
            ),
            "pico-portal-os/images/icon.bin": b"\x00\x01\xff",
            "templates/login/page.html": b"<!-- keep -->\r\n<p>  text </p>  ",
            "templates/success/done.htm": b"<pre>   done\n</pre>",
            "pico-portal-os/data.json": b'{"$schema":"keep","value":1}\n',
        }
        for path, content in unchanged.items():
            self.write("src/" + path, content)
        config = {
            "icon": "/pico-portal-os/images/icon.bin",
            "module": "pico-portal-os.tool",
            "title": "é",
        }
        editor_config = {"$schema": "../.schemas/config.schema.json", **config}
        config_path = self.write(
            "src/config.json", json.dumps(editor_config, indent=2)
        )
        self.write(".schemas/config.schema.json", '{"type":"object"}')
        self.write("dist/stale.txt")

        def fake_compile(source, destination, compiler):
            relative = source.relative_to(self.root / "dist").as_posix()
            self.assertEqual(source.read_bytes(), unchanged[relative])
            destination.write_bytes(b"fixture bytecode")

        compiler = {"command": ["compiler"], "version": "fixture"}
        with (
            patch("tooling.pipeline.find_mpy_cross", return_value=compiler),
            patch("tooling.assets.cross_compile", side_effect=fake_compile),
            redirect_stdout(io.StringIO()),
        ):
            run_build(project_root=self.root)
        output = self.root / "dist"
        self.assertEqual(
            {p.relative_to(output).as_posix() for p in files_under(output)},
            set(unchanged)
            - {"pico-portal-os/__init__.py", "pico-portal-os/tool.py"}
            | {
                "config.json",
                "pico-portal-os/__init__.mpy",
                "pico-portal-os/tool.mpy",
            },
        )
        for path, content in unchanged.items():
            self.assertEqual((self.root / "src" / path).read_bytes(), content)
            if path in (
                "pico-portal-os/__init__.py",
                "pico-portal-os/tool.py",
            ):
                compiled = (output / path).with_suffix(".mpy")
                self.assertEqual(compiled.read_bytes(), b"fixture bytecode")
                self.assertFalse((output / path).exists())
            else:
                self.assertEqual((output / path).read_bytes(), content)
        built_config = (output / "config.json").read_bytes()
        self.assertEqual(json.loads(built_config), config)
        self.assertEqual(json.loads(config_path.read_bytes()), editor_config)
        self.assertEqual(built_config.count(b"\n"), 1)
        self.assertFalse((self.root / "build").exists())

    def test_bytecode_preserves_module_paths_and_root_boot_source(self):
        sources = {
            "main.py": b"value = 1\n",
            "boot.py": b"value = 2\n",
            "pico-portal-os/__init__.py": b'"""Package docs."""\n',
            "pico-portal-os/tool.py": b"def original_name():\n    return 3\n",
        }
        for path, content in sources.items():
            self.write("src/" + path, content)

        def fake_compile(source, destination, compiler):
            relative = source.relative_to(self.root / "dist").as_posix()
            self.assertEqual(source.read_bytes(), sources[relative])
            destination.write_bytes(b"fixture bytecode")

        compiler = {"command": ["compiler"], "version": "fixture"}
        with (
            patch("tooling.pipeline.find_mpy_cross", return_value=compiler),
            patch("tooling.assets.cross_compile", side_effect=fake_compile),
            redirect_stdout(io.StringIO()),
        ):
            run_build(project_root=self.root)
        output = self.root / "dist"
        self.assertEqual(
            {p.relative_to(output).as_posix() for p in files_under(output)},
            {
                "main.py",
                "boot.py",
                "pico-portal-os/__init__.mpy",
                "pico-portal-os/tool.mpy",
            },
        )
        for path in ("main.py", "boot.py"):
            self.assertEqual((output / path).read_bytes(), sources[path])

    def test_invalid_python_preserves_previous_upload_tree(self):
        self.write("src/main.py", "def broken(:\n")
        previous = self.write("dist/previous.txt", b"keep")
        with self.assertRaises(SyntaxError):
            run_build(project_root=self.root)
        self.assertEqual(previous.read_bytes(), b"keep")

    def test_missing_compiler_preserves_previous_upload_tree(self):
        self.write("src/main.py", "value = 1\n")
        previous = self.write("dist/previous.txt", b"keep")
        with patch(
            "tooling.pipeline.find_mpy_cross",
            side_effect=RuntimeError("missing compiler"),
        ):
            with self.assertRaisesRegex(RuntimeError, "missing compiler"):
                run_build(project_root=self.root)
        self.assertEqual(previous.read_bytes(), b"keep")

    def test_cross_compiler_receives_local_names_only(self):
        source = self.write("dist/package/tool.py", "value = 1\n")
        compiler = {"command": ["compiler", "--prefix"]}
        with patch("tooling.tools.run_compiler") as run:
            run.return_value.returncode = 0
            cross_compile(source, source.with_suffix(".mpy"), compiler)
            run.assert_called_once_with(
                ["compiler", "--prefix", "-O3", "-o", "tool.mpy", "tool.py"],
                cwd=source.parent,
            )


if __name__ == "__main__":
    unittest.main()
