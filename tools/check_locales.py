"""Verify that every translation file is complete and consistent.

Checks, using en.json as the reference:
  * every language has exactly the same keys
  * every text keeps the same {placeholders} as the English text
  * every language listed in i18n.LANGUAGES has a file (and vice versa)

Usage:  python tools/check_locales.py        (exit code 1 on problems)
Used by the CI workflow and by build.bat.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "src" / "bandwidthguard" / "locales"
sys.path.insert(0, str(ROOT / "src"))

from bandwidthguard.i18n import LANGUAGES  # noqa: E402

PLACEHOLDER = re.compile(r"\{\w+\}")


def main() -> int:
    problems = []
    reference = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    files = {p.stem for p in LOCALES.glob("*.json")}

    if files != set(LANGUAGES):
        problems.append(f"Language list and files differ: {sorted(files ^ set(LANGUAGES))}")

    for code in sorted(files):
        data = json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))
        missing = set(reference) - set(data)
        extra = set(data) - set(reference)
        if missing:
            problems.append(f"[{code}] missing keys: {sorted(missing)}")
        if extra:
            problems.append(f"[{code}] unknown keys: {sorted(extra)}")
        for key in set(reference) & set(data):
            if sorted(PLACEHOLDER.findall(reference[key])) != sorted(PLACEHOLDER.findall(data[key])):
                problems.append(f"[{code}] placeholder mismatch in '{key}'")
            if not data[key].strip():
                problems.append(f"[{code}] empty text for '{key}'")

    if problems:
        print("Locale check FAILED:")
        for line in problems:
            print("  -", line)
        return 1
    print(f"Locale check OK: {len(files)} languages, {len(reference)} keys each.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
