#!/usr/bin/env python3
"""Sync the uAssets yt-rpnt exception block in brave-unbreak.txt.

Source resolution order:
  1. --src CLI argument (path or URL)
  2. UPSTREAM_FILE environment variable
  3. Sibling fork clone (local testing): ../uAssets/filters/quick-fixes.txt
  4. GitHub raw URL (CI fallback): griffinallen/uAssets @ test-sync

For production, change FORK_URL to the uBlockOrigin/uAssets master branch.
"""
import argparse
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "brave-unbreak.txt"
LOCAL_UPSTREAM = REPO_ROOT.parent / "uAssets" / "filters" / "quick-fixes.txt"
FORK_URL = (
    "https://raw.githubusercontent.com/griffinallen/uAssets/test-sync"
    "/filters/quick-fixes.txt"
)

BEGIN = "! BEGIN uAssets/yt-rpnt AUTO-SYNC"
END = "! END uAssets/yt-rpnt AUTO-SYNC"

# Tolerates the historical "AUTO=SYNC" typo in the END marker
BLOCK_RE = re.compile(
    r"^! BEGIN uAssets/yt-rpnt AUTO[-=]SYNC[ \t\r]*$.*?^! END uAssets/yt-rpnt AUTO[-=]SYNC[ \t\r]*$",
    re.S | re.M,
)

# Matches ONLY the rule(s) that start with this prefix in quick-fixes.txt
PREFIX = "www.youtube.com##+js(rpnt, script"


def load_upstream(src: str) -> list:
    if src.startswith("http://") or src.startswith("https://"):
        with urllib.request.urlopen(src, timeout=30) as r:
            return r.read().decode("utf-8").splitlines()
    return Path(src).read_text(encoding="utf-8").splitlines()


def to_exception(rule: str) -> str:
    # Only the first "##" is the separator; the scriptlet body stays byte-identical
    return rule.replace("##", "#@#", 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Regenerate the yt-rpnt exception block.")
    ap.add_argument("--src", default=None, help="path or URL of upstream quick-fixes.txt")
    ap.add_argument("--dry-run", action="store_true", help="report but do not write")
    args = ap.parse_args()

    src = args.src or os.environ.get("UPSTREAM_FILE")
    if not src:
        src = str(LOCAL_UPSTREAM) if LOCAL_UPSTREAM.is_file() else FORK_URL
    print(f"Source: {src}")

    try:
        upstream = load_upstream(src)
    except Exception as e:
        sys.exit(f"ERROR: reading upstream failed: {e}")

    matches = [line.strip() for line in upstream if line.strip().startswith(PREFIX)]

    # Never wipe the block if upstream renamed/removed the rule: fail loudly instead
    if not matches:
        sys.exit(f"ERROR: no upstream rule starting with {PREFIX!r}; leaving file unchanged")
    if len(matches) > 1:
        print(f"WARNING: {len(matches)} upstream rules match; excepting all of them")

    exceptions = [to_exception(m) for m in dict.fromkeys(matches)]  # dedupe, keep order

    # newline="" disables newline translation so existing line endings survive
    with TARGET.open(encoding="utf-8", newline="") as f:
        text = f.read()

    if not BLOCK_RE.search(text):
        sys.exit("ERROR: BEGIN/END markers not found in brave-unbreak.txt")

    eol = "\r\n" if "\r\n" in text else "\n"
    block = eol.join([BEGIN, *exceptions, END])

    # Replacer function keeps re.sub from interpreting backslashes / "$1" in the rule
    new_text = BLOCK_RE.sub(lambda _: block, text, count=1)

    if new_text == text:
        print("No change")
        return
    if args.dry_run:
        print("Would update brave-unbreak.txt (dry run)")
        return
    with TARGET.open("w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    print(f"Updated {TARGET.name} ({len(exceptions)} exception(s))")


if __name__ == "__main__":
    main()