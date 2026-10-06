# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import os
from pathlib import Path
import shutil
import subprocess
import sys


def run_compiler(command, cwd=None):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=(
            subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        ),
    )


def find_mpy_cross():
    candidates = []
    if os.environ.get("MPY_CROSS"):
        candidates.append([os.environ["MPY_CROSS"]])
    candidates.extend((["mpy-cross"], [sys.executable, "-m", "mpy_cross"]))
    for command in candidates:
        executable = shutil.which(command[0])
        if executable:
            command[0] = str(Path(executable).resolve())
        try:
            probe = run_compiler(command + ["--version"])
        except OSError:
            continue
        if probe.returncode == 0:
            return {
                "command": command,
                "version": (probe.stdout or probe.stderr or "unknown").strip(),
            }
    raise RuntimeError(
        "Device build requires mpy-cross, but it was not found. "
        "Install a version matching your Pimoroni MicroPython firmware "
        "(python -m pip install mpy-cross), or set MPY_CROSS to its executable."
    )


def cross_compile(source_path, destination, compiler):
    result = run_compiler(
        compiler["command"] + ["-O3", "-o", destination.name, source_path.name],
        cwd=source_path.parent,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"mpy-cross failed for {source_path.name}:\n{result.stderr}"
        )
