#!/usr/bin/env python3
"""Install managed skill copies, protecting user edits and unrelated skills."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

MARKER = '.clipforge-install.json'


def files(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file() and p.name != MARKER}


def check_destination(dest, source, root):
    if dest.is_symlink():
        if dest.resolve() == source.resolve():
            return
    elif not dest.exists():
        return
    elif dest.is_file() and dest.stat().st_size < 1024:
        # Exact old Git symlink text only, never overwrite an arbitrary file.
        try:
            if (dest.parent / dest.read_text(encoding='utf-8').strip()).resolve() == source.resolve():
                return
        except (OSError, UnicodeError):
            pass
    elif dest.is_dir() and (dest / MARKER).is_file():
        data = json.loads((dest / MARKER).read_text(encoding='utf-8'))
        if (data.get('package_root') == str(root.resolve()) and
                data.get('files') == files(dest) and not any(p.is_symlink() for p in dest.rglob('*'))):
            return
    raise ValueError(f'Refusing to replace existing or modified skill: {dest}')


def install_one(source, dest, root):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.clipforge-install-', dir=dest.parent) as scratch:
        staged = Path(scratch) / 'new'
        shutil.copytree(source, staged)
        marker = {'package_root': str(root.resolve()), 'files': files(staged)}
        (staged / MARKER).write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding='utf-8')
        check_destination(dest, source, root)
        backup = Path(scratch) / 'previous'
        if dest.exists() or dest.is_symlink():
            dest.rename(backup)
        try:
            os.replace(staged, dest)
        except OSError:
            if backup.exists() or backup.is_symlink():
                backup.rename(dest)
            raise


def install(root, target, hosts):
    pending = []
    for host in hosts:
        parent = target / {"codex": ".agents/skills", "claude": ".claude/skills"}[host]
        for source in sorted((root / "skills").iterdir()):
            if not (source / "SKILL.md").is_file():
                continue
            dest = parent / source.name
            check_destination(dest, source, root)
            pending.append((source, dest))
    for source, dest in pending:
        install_one(source, dest, root)
    return [str(dest) for _, dest in pending]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--host", choices=["codex", "claude", "both"], default="both")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    hosts = ["codex", "claude"] if a.host == "both" else [a.host]
    print(json.dumps({"installed": install(root, a.project.resolve(), hosts)}, ensure_ascii=False))
