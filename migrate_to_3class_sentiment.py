#!/usr/bin/env python3
"""
Utility helpers for maintaining rubric_overrides.json.

Usage examples:
  python manage_overrides.py list
  python manage_overrides.py validate
  python manage_overrides.py add --entry-id 51 --label negative --keywords "exposes" "weak point"
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
OVERRIDES_PATH = BASE_DIR / "rubric_overrides.json"
CORRECTIONS_PATH = BASE_DIR.parent / "corrected_sentiments.json"


def load_overrides() -> List[Dict]:
    if not OVERRIDES_PATH.exists():
        return []
    return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))


def save_overrides(overrides: List[Dict]) -> None:
    OVERRIDES_PATH.write_text(
        json.dumps(overrides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_corrections() -> List[Dict]:
    if not CORRECTIONS_PATH.exists():
        return []
    return json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))


def sanitize_id(seed: str) -> str:
    allowed = []
    for char in seed.lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {"-", "_"}:
            allowed.append(char)
        else:
            allowed.append("_")
    cleaned = "".join(allowed).strip("_")
    return cleaned or "override"


def generate_override_id(entry_id: int, keywords: List[str], existing: List[Dict]) -> str:
    base = f"entry_{entry_id}_{sanitize_id('_'.join(keywords)[:40])}"
    candidate = base
    suffix = 1
    existing_ids = {item.get("id") for item in existing}
    while candidate in existing_ids:
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate


def cmd_list(_: argparse.Namespace) -> int:
    overrides = load_overrides()
    if not overrides:
        print("No overrides defined yet.")
        return 0

    for item in overrides:
        keywords = ", ".join(item.get("keywords", []))
        label = item.get("label")
        override_id = item.get("id", "<missing id>")
        note = item.get("note", "")
        print(f"- {override_id:35s} [{label}] :: {keywords}")
        if note:
            print(f"    note: {note}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    overrides = load_overrides()
    problems = []
    seen_keywords = set()

    for item in overrides:
        key_tuple = tuple(item.get("keywords", []))
        if not item.get("id"):
            problems.append(f"Override with keywords {key_tuple} is missing an id.")
        if not item.get("note"):
            problems.append(f"Override {item.get('id')} is missing a note.")
        if key_tuple in seen_keywords:
            problems.append(f"Duplicate keyword set detected: {key_tuple}")
        seen_keywords.add(key_tuple)

    if problems:
        print("Validation failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("All overrides look good ✅")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    overrides = load_overrides()
    corrections = load_corrections()
    entry = next((c for c in corrections if c.get("id") == args.entry_id), None)
    if entry is None:
        print(f"Entry id {args.entry_id} not found in corrected_sentiments.json", file=sys.stderr)
        return 1

    keywords = [kw.lower().strip() for kw in args.keywords]
    if not keywords:
        print("At least one keyword is required.", file=sys.stderr)
        return 1

    existing_keyword_sets = {tuple(item.get("keywords", [])) for item in overrides}
    keyword_tuple = tuple(keywords)
    if keyword_tuple in existing_keyword_sets:
        print("An override with the same keyword set already exists.", file=sys.stderr)
        return 1

    label = args.label.lower()
    valid_labels = {"very_positive", "positive", "neutral", "negative", "very_negative", "maybe"}
    if label not in valid_labels:
        print(f"Label must be one of: {', '.join(sorted(valid_labels))}", file=sys.stderr)
        return 1

    note = args.note or entry.get("reason", "").strip()
    override_id = args.override_id or generate_override_id(args.entry_id, keywords, overrides)

    overrides.append(
        {
            "id": override_id,
            "keywords": keywords,
            "label": label,
            "note": note,
        }
    )
    save_overrides(overrides)

    print(f"Added override {override_id} ({label}) using keywords {keywords}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage rubric keyword overrides.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List current overrides").set_defaults(func=cmd_list)
    subparsers.add_parser("validate", help="Validate overrides file").set_defaults(
        func=cmd_validate
    )

    add_parser = subparsers.add_parser("add", help="Add a new override entry")
    add_parser.add_argument("--entry-id", type=int, required=True, help="ID from corrected_sentiments.json")
    add_parser.add_argument(
        "--keywords",
        nargs="+",
        required=True,
        help="Lowercase keyword snippets that must be present to trigger the override.",
    )
    add_parser.add_argument("--label", required=True, help="Internal label to force (e.g., positive).")
    add_parser.add_argument("--note", help="Optional note for context (defaults to the correction reason).")
    add_parser.add_argument(
        "--override-id",
        help="Custom identifier for the override (otherwise generated automatically).",
    )
    add_parser.set_defaults(func=cmd_add)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

