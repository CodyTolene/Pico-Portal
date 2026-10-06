# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from pathlib import Path

from .assets import emit_files
from .files import (
    ensure_clean_output,
    files_under,
    upload_path,
    validate_output,
)
from .tools import find_mpy_cross

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_build(project_root=PROJECT_ROOT):
    project_root = Path(project_root).resolve()
    source_root = project_root / "src"
    output_root = project_root / "dist"
    if not source_root.is_dir():
        raise ValueError(f"Source directory not found: {source_root}")
    files = files_under(source_root)
    for path in files:
        if path.suffix.lower() == ".py":
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
    compiler = find_mpy_cross()

    ensure_clean_output(project_root, output_root)
    source_bytes, output_bytes, compacted = emit_files(
        files, source_root, output_root, compiler
    )
    expected = {
        upload_path(path.relative_to(source_root).as_posix()) for path in files
    }
    validate_output(output_root, expected)

    saved = source_bytes - output_bytes
    percent = saved / source_bytes * 100 if source_bytes else 0
    print(f"Built {len(files)} files in {output_root}")
    print(f"Compacted {compacted} JSON files")
    print(f"Compiler: {compiler['version']}")
    print(
        f"Size {source_bytes:,} -> {output_bytes:,} bytes "
        f"({percent:.1f}% smaller)"
    )
    print("Device build complete; upload dist/ to the device root.")
