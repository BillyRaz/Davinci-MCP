"""Command-line access to offline LUT generation, validation, and inspection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from resolve.errors import ResolveError

from .generator import generate_artifacts
from .model import GradeProfile
from .validator import validate_lut


def _emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="davinci-grade")
    parser.add_argument("--json", action="store_true")
    subcommands = parser.add_subparsers(dest="group", required=True)
    lut = subcommands.add_parser("lut")
    commands = lut.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("profile", type=Path)
    generate.add_argument("--output", type=Path, default=Path.cwd())
    generate.add_argument("--dry-run", action="store_true")
    for name in ("validate", "inspect"):
        command = commands.add_parser(name)
        command.add_argument("cube", type=Path)
        command.add_argument("--metadata", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "generate":
            profile = GradeProfile.model_validate_json(args.profile.read_text())
            if args.dry_run:
                result = {
                    "dry_run": True,
                    "profile": profile.name,
                    "filename": f"{profile.filename_stem}.cube",
                    "rows": profile.cube_size**3,
                }
            else:
                result = generate_artifacts(
                    profile, args.output, source_profile_path=str(args.profile.resolve())
                )
        else:
            result = validate_lut(args.cube, args.metadata).to_dict()
            if not result["valid"]:
                _emit(result, args.json)
                return 2
        _emit(result, args.json)
        return 0
    except (OSError, ValueError, ValidationError, ResolveError) as exc:
        _emit({"error": str(exc)}, args.json)
        return 2
