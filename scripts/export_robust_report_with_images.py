#!/usr/bin/env python3

from __future__ import annotations

import subprocess
from pathlib import Path


def _find_anchor(start: Path, anchor: str) -> Path:
    """Walk up from `start` looking for a directory containing a sibling named
    `anchor`. Returns the path to the anchor itself."""
    for parent in [start.resolve(), *start.resolve().parents]:
        candidate = parent / anchor
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not locate '{anchor}' walking up from {start}"
    )


# `updated-rtest-main` is a sibling of this project under "0-Shen Research/".
# Walk up until we find it instead of hardcoding a username/path.
MAIN_FOLDER = _find_anchor(Path(__file__).parent, "updated-rtest-main")
REPORTS = MAIN_FOLDER / "My-robust-Test-Results" / "reports"
SOURCE = REPORTS / "robust_27_31_nist_summary_report_20260412.md"
INLINE_MD = REPORTS / "robust_27_31_nist_summary_report_20260412_inline_images.md"
HTML = REPORTS / "robust_27_31_nist_summary_report_20260412_inline_images.html"

def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    INLINE_MD.write_text(text, encoding="utf-8")

    subprocess.run(
        [
            "pandoc",
            str(INLINE_MD),
            "-s",
            "-o",
            str(HTML),
        ],
        check=True,
    )

    print(INLINE_MD)
    print(HTML)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
