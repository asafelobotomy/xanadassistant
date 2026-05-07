#!/usr/bin/env python3

from __future__ import annotations

import json
import sys


def main() -> int:
    json.dump(
        {
            "status": "not-implemented",
            "message": "Placeholder workspace MCP server managed by xanad-assistant planning.",
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())