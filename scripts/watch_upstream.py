#!/usr/bin/env python3
"""Poll the upstream quick-fixes.txt file and re-run the sync on any change.

Local stand-in for the scheduled GitHub Action in
.github/workflows/sync-uassets-exception.yml. Change detection is a
SHA-256 content hash, so mtime jitter and identical rewrites are ignored.

Usage:
  python3 scripts/watch_upstream.py                     # poll every 2s forever
  python3 scripts/watch_upstream.py --once              # single check, then exit
  python3 scripts/watch_upstream.py --commit            # git commit the change
  python3 scripts/watch_upstream.py --src /other/path   # watch a different file
"""
import argparse
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYNC = HERE / "sync_quickfix_exception.py"
REPO_ROOT = HERE.parent
LOCAL_UPSTREAM = HERE.parent.parent / "uAssets" / "filters" / "quick-fixes.txt"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_sync(src: Path) -> int:
    return subprocess.call([sys.executable, str(SYNC), "--src", str(src)])


def commit_change(message: str) -> None:
    status = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "brave-unbreak.txt"],
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        return  # nothing to commit (idempotent run)
    subprocess.run(["git", "-C", str(REPO_ROOT), "add", "brave-unbreak.txt"], check=True)
    subprocess.run(
        [
            "git", "-C", str(REPO_ROOT),
            "-c", "user.name=sync-bot", "-c", "user.email=sync-bot@example.com",
            "commit", "-m", message,
        ],
        check=True,
    )
    print("[watch] committed brave-unbreak.txt change")


def main() -> None:
    ap = argparse.ArgumentParser(description="Watch upstream file and re-sync on change.")
    ap.add_argument("--src", type=Path, default=None, help="upstream file to watch")
    ap.add_argument("--interval", type=float, default=2.0, help="poll interval in seconds")
    ap.add_argument("--once", action="store_true", help="run one check and exit")
    ap.add_argument("--commit", action="store_true", help="git commit brave-unbreak.txt on change")
    args = ap.parse_args()

    src = args.src or os.environ.get("UPSTREAM_FILE") or LOCAL_UPSTREAM
    src = Path(src)
    if not src.is_file():
        sys.exit(f"ERROR: upstream file not found: {src}")

    print(f"[watch] watching {src} (interval {args.interval}s)")
    last = None
    while True:
        current = digest(src)
        if current != last:
            stamp = datetime.now().strftime("%H:%M:%S")
            if last is None:
                print(f"[watch] {stamp} initial sync")
            else:
                print(f"[watch] {stamp} upstream changed (sha256 {current[:12]}...), re-syncing")
            rc = run_sync(src)
            if rc != 0:
                print(f"[watch] sync failed with exit code {rc}", file=sys.stderr)
            elif args.commit:
                commit_change(f"Sync brave-unbreak.txt with upstream quick-fixes ({current[:12]})")
            last = current
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()