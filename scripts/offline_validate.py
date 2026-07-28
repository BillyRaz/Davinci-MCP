#!/usr/bin/env python3
"""Run validation checks that do not import or connect to Resolve."""

from __future__ import annotations

import json

from tools.context import Services


def main() -> int:
    report = Services.build().validation.run_full(live=False)
    print(json.dumps({"summary": report["summary"], "paths": report["paths"]}, indent=2))
    return 1 if report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

