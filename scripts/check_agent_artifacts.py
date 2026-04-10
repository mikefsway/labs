#!/usr/bin/env python3
"""Check agent-facing artifacts for drift against source-of-truth files.

Each configured artifact declares which source files describe it. If any
source file has been modified more recently than the artifact's
`last-verified:` date, this script flags it as drift.

Run from the repo root:
    python scripts/check_agent_artifacts.py

Exit codes:
    0 — all artifacts are fresh
    1 — drift detected
    2 — script error
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Per-repo config — keep in sync with CLAUDE.md "Agent-facing artifacts" table.
ARTIFACTS: dict[str, list[str]] = {
    "app/templates/llms.txt": [
        "labs_mcp/server.py",
        "app/routers/search.py",
        "app/routers/labs.py",
        "app/services/hybrid_search.py",
    ],
    "app/templates/skill.md": [
        "labs_mcp/server.py",
        "app/services/hybrid_search.py",
        "app/services/recommendation.py",
    ],
}

LAST_VERIFIED_RE = re.compile(r"^last-verified:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


def parse_last_verified(artifact: Path) -> dt.date | None:
    try:
        text = artifact.read_text()
    except FileNotFoundError:
        return None
    m = LAST_VERIFIED_RE.search(text)
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def latest_source_mtime(patterns: list[str]) -> dt.date | None:
    latest: dt.date | None = None
    for pattern in patterns:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file():
                mtime = dt.date.fromtimestamp(path.stat().st_mtime)
                if latest is None or mtime > latest:
                    latest = mtime
    return latest


def main() -> int:
    drift_found = False
    error_found = False
    print(f"Checking agent artifacts in {REPO_ROOT}\n")
    for rel_artifact, sources in ARTIFACTS.items():
        artifact = REPO_ROOT / rel_artifact
        if not artifact.exists():
            print(f"  MISSING  {rel_artifact}")
            error_found = True
            continue
        if not sources:
            print(f"  skipped  {rel_artifact} (hand-curated)")
            continue
        last_verified = parse_last_verified(artifact)
        if last_verified is None:
            print(f"  UNDATED  {rel_artifact} — add `last-verified: YYYY-MM-DD`")
            error_found = True
            continue
        latest = latest_source_mtime(sources)
        if latest is None:
            print(f"  no-src   {rel_artifact} (no matching source files)")
            continue
        if latest > last_verified:
            days = (latest - last_verified).days
            print(
                f"  DRIFT    {rel_artifact} — verified {last_verified}, "
                f"sources newer by {days}d (latest: {latest})"
            )
            drift_found = True
        else:
            print(f"  ok       {rel_artifact} — verified {last_verified}")

    if error_found:
        print("\nScript errors — see messages above.")
        return 2
    if drift_found:
        print(
            "\nDrift detected. Review the source files, update the artifact, "
            "and bump `last-verified:` to today."
        )
        return 1
    print("\nAll artifacts fresh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
