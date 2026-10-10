#!/usr/bin/env python3
"""Repeatable local gates; no claims about human acceptance or host model execution."""
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]


def check_skills():
    for skill in (ROOT / 'skills').iterdir():
        if not skill.is_dir():
            continue
        body = (skill / 'SKILL.md').read_text(encoding='utf-8')
        header = yaml.safe_load(body.split('---', 2)[1])
        if header.get('name') != skill.name or not header.get('description'):
            raise SystemExit(f'Invalid skill metadata: {skill}')
        if not (skill / 'scripts/run.py').is_file():
            raise SystemExit(f'Broken launcher: {skill}')
        for host in ('.agents', '.claude'):
            installed = ROOT / host / 'skills' / skill.name
            if (installed / 'SKILL.md').read_bytes() != (skill / 'SKILL.md').read_bytes():
                raise SystemExit(f'Broken host installation: {host}/{skill.name}')
            if (installed / 'scripts/run.py').read_bytes() != (skill / 'scripts/run.py').read_bytes():
                raise SystemExit(f'Stale host launcher: {host}/{skill.name}')


def main():
    subprocess.run([sys.executable, '-m', 'ruff', 'check', 'src', '--select', 'F,C90',
                    '--config', 'lint.mccabe.max-complexity=10'], cwd=ROOT, check=True)
    for source in (ROOT / 'src').rglob('*.py'):
        if len(source.read_text(encoding='utf-8').splitlines()) > 500:
            raise SystemExit(f'File exceeds 500 lines: {source}')
    check_skills()
    subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q', '--basetemp=tmp/pytest',
                    '-W', 'error::ResourceWarning', '--cov=clipforge_skills',
                    '--cov-fail-under=70', '--cov-report=term-missing',
                    '--cov-report=json:tmp/coverage.json'], cwd=ROOT, check=True)
    coverage = json.loads((ROOT / 'tmp/coverage.json').read_text(encoding='utf-8'))
    core = {'contracts.py', 'library.py', 'render.py', 'delivery.py', 'captions.py',
            'media.py', 'importers.py', 'evidence.py', 'creative.py',
            'presentation.py', 'mixing.py', 'timing.py'}
    for name, record in coverage['files'].items():
        if Path(name).name in core and record['summary']['percent_covered'] < 90:
            raise SystemExit(f'Core module below 90% coverage: {name}')
    print('Local gates passed; real-media acceptance and both host sessions remain separate.')


if __name__ == '__main__':
    main()
