#!/usr/bin/env python3
"""Shared source for ordinary skill launchers; no symlinks or shell needed."""
import json
from pathlib import Path
import runpy


def main():
    skill = Path(__file__).resolve().parents[1]
    manifest = skill / '.clipforge-install.json'
    if manifest.is_file():
        roots = [Path(json.loads(manifest.read_text(encoding='utf-8'))['package_root'])]
    else:
        roots = list(skill.parents)
    for root in roots:
        launcher = root / 'tools/clipforge.py'
        if launcher.is_file() and (root / 'pyproject.toml').is_file():
            runpy.run_path(str(launcher), run_name='__main__')
            return
    raise SystemExit('ClipForge tool package not found; reinstall this skill from the complete checkout.')


if __name__ == '__main__':
    main()
