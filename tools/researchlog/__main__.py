"""Canonical entry point.

Run as `python3 tools/researchlog <command>` or `python3 -m researchlog <command>`.

Copy the whole `tools/` directory when moving this into another repository —
`researchlog` needs its sibling `templates/` and `schemas/` directories.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_PARENT = Path(__file__).resolve().parent.parent
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

from researchlog.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
