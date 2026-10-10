#!/usr/bin/env python3
"""Materialize a pinned upstream engine without altering the user's source checkout."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
REVISION = "77a7e73e1f898581d325f3070b574ea0894d8a76"
p = argparse.ArgumentParser()
p.add_argument("--source", type=Path)
a = p.parse_args()
source = a.source or ROOT / "tmp/engine-fetch"
if not a.source and not (source / ".git").exists():
    subprocess.run(["git", "clone", "--no-checkout", "https://github.com/fantiny/clipforge.git", str(source)], check=True)
resolved = subprocess.check_output(["git", "-C", str(source), "rev-parse", REVISION]).decode().strip()
if resolved != REVISION:
    raise SystemExit("Unexpected revision")
archive = subprocess.check_output(["git", "-C", str(source), "archive", REVISION, "vidmake"])
dest = ROOT / ".runtime/upstream"
dest.mkdir(parents=True, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    for member in tar.getmembers():
        if not member.isfile():
            continue
        path = dest / member.name
        content = tar.extractfile(member).read()
        if path.exists() and path.read_bytes() != content:
            raise SystemExit(f"Refusing to overwrite modified runtime file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
(dest / "REVISION").write_text(REVISION + "\n")
print(json.dumps({"engine": str(dest), "revision": REVISION, "source": str(source)}))
