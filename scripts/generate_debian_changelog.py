#!/usr/bin/env python3

import re
import sys
from datetime import datetime
from pathlib import Path


VERSION = sys.argv[1]

PACKAGE = "shello"
MAINTAINER = "Kostiantyn Zakharov <kszakharov@gmail.com>"
URGENCY = "medium"

CHANGELOG = Path("CHANGELOG.md")
VERSION_BLOCK_RE = re.compile(
    r"^##\s+\[(?P<version>[^\]]+)\]"
    r"(?:\s+-\s+(?P<date>\d{4}-\d{2}-\d{2}))?"
    r"(?P<body>.*?)(?=^##\s+\[|\Z)",
    re.MULTILINE | re.DOTALL,
)
SECTION_RE = re.compile(r"^###\s+(?P<section>.+)$", re.MULTILINE)
ITEM_RE = re.compile(r"^\s*[-*]\s+(?P<item>.+)$", re.MULTILINE)


def get_changelog_body(version: str) -> str:
    text = CHANGELOG.read_text()
    for match in VERSION_BLOCK_RE.finditer(text):
        if match.group("version") == version:
            return match.group("body").strip()
    sys.exit(f"Version {version!r} not found in CHANGELOG.md")


def parse_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section = "Changes"
    for line in body.splitlines():
        section_match = SECTION_RE.match(line)
        item_match = ITEM_RE.match(line)
        if section_match:
            current_section = section_match.group("section")
        elif item_match:
            sections.setdefault(current_section, []).append(item_match.group("item"))
    return sections


def main():
    body = get_changelog_body(VERSION)
    sections = parse_sections(body)

    if not sections:
        sections = {"Changes": [f"Release {VERSION}"]}

    date_str = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
    lines = [f"{PACKAGE} ({VERSION}-1) unstable; urgency={URGENCY}", ""]

    for section, items in sections.items():
        lines.append(f"  * {section}:")
        for item in items:
            lines.append(f"    - {item}")
    lines.append("")
    lines.append(f" -- {MAINTAINER}  {date_str}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
