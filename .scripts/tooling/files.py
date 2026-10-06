# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

from pathlib import Path, PurePosixPath
import re
import shutil


def files_under(directory):
    output = []
    for path in sorted(Path(directory).iterdir()):
        if path.name in ("__pycache__", ".DS_Store"):
            continue
        if path.is_dir():
            output.extend(files_under(path))
        elif path.suffix != ".pyc":
            output.append(path)
    return output


def ensure_clean_output(project_root, output_root):
    output_root = Path(output_root)
    expected = Path(project_root).resolve() / "dist"
    if output_root.resolve() != expected or output_root.is_symlink():
        raise ValueError(
            f"Refusing to clean unexpected output path: {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    for path in output_root.iterdir():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def upload_path(relative):
    """Use .mpy for imported modules; keep root boot files as source."""
    path = PurePosixPath(relative)
    if path.suffix.lower() == ".py" and path.parent != PurePosixPath("."):
        path = path.with_suffix(".mpy")
    return path.as_posix()


def validate_output(output_root, expected_paths=None):
    output_root = Path(output_root)
    if any(
        path.name == "__pycache__" or path.suffix == ".pyc"
        for path in output_root.rglob("*")
    ):
        raise ValueError("Build output contains Python cache files.")
    files = files_under(output_root)
    if expected_paths is not None:
        expected = set(expected_paths)
        actual = {path.relative_to(output_root).as_posix() for path in files}
        if actual != expected:
            missing = ",".join(sorted(expected - actual)) or "none"
            unexpected = ",".join(sorted(actual - expected)) or "none"
            raise ValueError(
                f"Build output mismatch; missing={missing}; "
                f"unexpected={unexpected}"
            )
    patterns = (
        ("Windows absolute path", r"[A-Za-z]:[\\/](?![\\/])[\x20-\x7e]{2,}"),
        ("user home path", r"/(?:Users|home)/[\x20-\x7e]{2,}"),
    )
    for path in files:
        content = path.read_bytes().decode("latin1")
        for label, pattern in patterns:
            match = re.search(pattern, content)
            if match:
                relative = path.relative_to(output_root).as_posix()
                raise ValueError(
                    f"Build output {relative} contains a {label}: "
                    f"{match.group()[:120]}"
                )
