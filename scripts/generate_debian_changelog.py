#!/usr/bin/env python3

import sys
from datetime import datetime


VERSION = sys.argv[1]

PACKAGE = "shello"
MAINTAINER = "Kostiantyn Zakharov <kszakharov@gmail.com>"
URGENCY = "medium"


def main():
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
