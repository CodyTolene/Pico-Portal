# =============================================================================
#  Project: Pico Portal
#  License: CC-BY-NC-4.0
# =============================================================================

import argparse
import sys

sys.dont_write_bytecode = True

from tooling.pipeline import run_build  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Build optimized Pico Portal OS files in dist/."
    )
    parser.parse_args()
    try:
        run_build()
    except (OSError, ValueError, RuntimeError, SyntaxError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
