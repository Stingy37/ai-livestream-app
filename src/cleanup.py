"""Clear partial run state: old run folders, local packages, pid/tunnel files.

    python src/cleanup.py --runs-older-than 48 [--keep-current] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from config_env import REPO_ROOT, Settings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-older-than", type=float, default=48.0, help="hours; run folders older than this are deleted")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tunnel", action="store_true", help="also stop the ssh tunnel to EC2")
    a = ap.parse_args(argv)
    s = Settings.from_env()
    cutoff = time.time() - a.runs_older_than * 3600
    removed = 0
    if s.run_root.is_dir():
        for d in sorted(s.run_root.iterdir()):
            if d.is_dir() and d.stat().st_mtime < cutoff and d.name != s.run_id:
                print("remove", d)
                if not a.dry_run:
                    shutil.rmtree(d, ignore_errors=True)
                removed += 1
    for p in (REPO_ROOT / ".run" / "STOP",):
        if p.exists():
            print("remove", p)
            if not a.dry_run:
                p.unlink()
    if a.tunnel:
        subprocess.call(["bash", str(REPO_ROOT / "scripts" / "ec2_tunnel.sh"), "stop"])
    print(f"{removed} run folder(s) removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
