#!/usr/bin/env python3
"""Strip credentials and sensitive keys from an n8n workflow export.

Usage:
    python scripts/sanitize_n8n_export.py path/to/export.json [-o sanitized.json]
If no input path is provided, STDIN is used. Output defaults to STDOUT.
"""
import argparse
import json
import sys
from typing import Any

SENSITIVE_KEYS = {"credentials", "apiKey", "apikey", "token", "accessToken", "refreshToken", "password", "secret"}


def sanitize(data: Any) -> Any:
    """Recursively remove sensitive keys from dictionaries and lists."""
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if key in SENSITIVE_KEYS:
                continue
            cleaned[key] = sanitize(value)
        return cleaned
    if isinstance(data, list):
        return [sanitize(item) for item in data]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="Path to n8n export JSON. Reads STDIN if omitted.")
    parser.add_argument("-o", "--output", help="Path to write sanitized JSON. Writes STDOUT if omitted.")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    else:
        raw = json.load(sys.stdin)

    sanitized = sanitize(raw)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(sanitized, fh, indent=2)
            fh.write("\n")
    else:
        json.dump(sanitized, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
