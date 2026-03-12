# /usr/bin/env python3

import re
import sys
from datetime import datetime
from pathlib import Path


VERSION = sys.argv[1]

PACKAGE = "shello"
MAINTAINER = "Kostiantyn Zakharov <kszakharov@gmail.com>"
URGENCY = "medium"


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
    sections = {
        "Added": ["Support for Python 3.10 and 3.11"],
        "Changed": [
            "CI: Update `actions/checkout` to v6",
            "Rename properties `stdout_data` and `stderr_data` to `stdout` and `stderr`",
        ],
    }

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
