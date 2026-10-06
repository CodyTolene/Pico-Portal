# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import json
import shutil

from .files import upload_path
from .tools import cross_compile


def emit_files(files, source_root, output_root, compiler):
    source_bytes = output_bytes = compacted = 0
    for source_path in files:
        relative = source_path.relative_to(source_root).as_posix()
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_bytes += source_path.stat().st_size
        if source_path.suffix.lower() == ".json":
            parsed = json.loads(source_path.read_text(encoding="utf-8"))
            if relative == "config.json" and isinstance(parsed, dict):
                parsed.pop("$schema", None)
            result = json.dumps(
                parsed, ensure_ascii=False, separators=(",", ":")
            )
            destination.write_bytes((result + "\n").encode("utf-8"))
            compacted += 1
        else:
            shutil.copyfile(source_path, destination)
            emitted = output_root / upload_path(relative)
            if emitted != destination:
                cross_compile(destination, emitted, compiler)
                destination.unlink()
                destination = emitted
        output_bytes += destination.stat().st_size
    return source_bytes, output_bytes, compacted
