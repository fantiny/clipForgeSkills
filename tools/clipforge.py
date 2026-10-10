#!/usr/bin/env python3
"""Cross-platform launcher for this checkout's locked environment."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        print(json.dumps({'ok': False, 'error_code': 'environment_missing',
                          'message': 'Run uv sync --frozen in the complete ClipForge Skills checkout'}))
        return 1
    env = {**os.environ, 'CLIPFORGE_HOME': str(root), 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    return subprocess.call([str(python), '-X', 'utf8', '-m', 'clipforge_skills.cli', *sys.argv[1:]], env=env)


if __name__ == '__main__':
    raise SystemExit(main())
