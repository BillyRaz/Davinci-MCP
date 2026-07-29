#!/usr/bin/env python3
"""Print discovered platform paths or create the user configuration file."""

from __future__ import annotations

import argparse
import json

from resolve.config import create_default_config
from resolve.platforms import detect_platform


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create-config", action="store_true")
    parser.add_argument("--value", choices=("output", "config", "modules", "library"))
    args = parser.parse_args()
    paths = detect_platform()
    if args.create_config:
        print(create_default_config(paths))
        return 0
    values = {
        "system": paths.info.system,
        "architecture": paths.info.architecture,
        "output": str(paths.output_directory),
        "config": str(paths.configuration_file),
        "modules": str(paths.resolve.modules_directory or ""),
        "library": str(paths.resolve.native_library or ""),
        "executable": str(paths.resolve.executable or ""),
        "venv_python": str(paths.virtual_environment_python),
    }
    print(values[args.value] if args.value else json.dumps(values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
