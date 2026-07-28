#!/usr/bin/env python3
"""Run offline and read-only live Resolve validation.

Resolve must already be open with a project and timeline. This script does not
export a frame, start a render, apply a grade, or alter timeline state.
"""

from __future__ import annotations

import json

from tools.context import Services


def main() -> int:
    report = Services.build().validation.run_full(live=True)
    print(json.dumps({"summary": report["summary"], "paths": report["paths"]}, indent=2))
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

