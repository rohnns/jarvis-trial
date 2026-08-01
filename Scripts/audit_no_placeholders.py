from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"venv", "__pycache__", ".git"}
EXTENSIONS = {".py", ".md", ".toml", ".json", ".bat"}
TERMS = [
    "place" + "holder",
    "TO" + "DO",
    "Not" + "Implemented" + "Error",
    "return " + "''",
    "fa" + "ke implementations",
    "mo" + "ck services",
    "PySide6 un" + "available",
    "\." + "\." + "\.",
]
PATTERN = re.compile("|".join(TERMS), re.IGNORECASE)


def main() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in EXTENSIONS or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    if hits:
        raise SystemExit("\n".join(hits))
    print("SOURCE_AUDIT_CLEAN")


if __name__ == "__main__":
    main()
