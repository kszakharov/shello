#!/usr/bin/env python3

import re
import sys
from pathlib import Path


VERSION = sys.argv[1]

CHANGELOG = Path("CHANGELOG.md")
RELEASE_NOTES = Path("RELEASE_NOTES.md")
VERSION_BLOCK_RE = re.compile(
    r"^##\s+\[(?P<version>[^\]]+)\]"            # version in brackets
    r"(?:\s+-\s+(?P<date>\d{4}-\d{2}-\d{2}))?"  # optional date after " - "
    r"(?P<body>.*?)(?=^##\s+\[|\Z)",            # everything until next version
    re.MULTILINE | re.DOTALL,
)


def get_versions():
    text = CHANGELOG.read_text()
    versions = {}

    for match in VERSION_BLOCK_RE.finditer(text):
        version = match.group("version")
        body = match.group("body").strip()
        date = match.group("date")
        versions[version] = {"date": date, "body": body}

    return versions


def main():
    versions = get_versions()
    RELEASE_NOTES.write_text(versions[VERSION]["body"] + "\n")


if __name__ == "__main__":
    main()
