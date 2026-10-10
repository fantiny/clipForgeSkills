#!/usr/bin/env python3
"""Render explicit child-directory plans; never generate copy, audio or approvals."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from clipforge_skills.core import HOME, process_env, write_json


def invoke(plan, command, extra=()):
    result = subprocess.run(
        [sys.executable, '-X', 'utf8', str(HOME / 'tools/clipforge.py'), command,
         str(plan.resolve()), *extra], cwd=HOME, env=process_env(),
        capture_output=True, encoding='utf-8', timeout=2400, check=False)
    (plan.parent / f'{command}-result.json').write_text(result.stdout, encoding='utf-8')
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'{plan.parent.name}: {command} did not return JSON') from exc
    if result.returncode or not response.get('ok'):
        raise RuntimeError(f'{plan.parent.name}: {response}')
    return response


def render_directory(directory):
    directory = Path(directory)
    plans = sorted(directory.glob('*/plan.json')) if directory.is_dir() else []
    if not 1 <= len(plans) <= 24:
        raise ValueError('Expected a directory containing 1–24 child plan.json files')
    results = []
    # This is the current attempt, not a ledger of successes from a previous run.
    write_json(directory / 'render-progress.json', results)
    for plan in plans:
        invoke(plan, 'validate')
    for plan in plans:
        response = invoke(plan, 'render', ['--mode', 'final'])
        work = Path(response['result']['video']).parent
        for name in ['output.mp4', 'captions.srt', 'captions.ass', 'cover.jpg', 'qa.json', 'manifest.json']:
            shutil.copy2(work / name, plan.parent / name)
        if (work / 'loudness-analysis.json').exists():
            shutil.copy2(work / 'loudness-analysis.json', plan.parent / 'loudness-analysis.json')
        results.append({'scene': plan.parent.name, **response['result']})
        write_json(directory / 'render-progress.json', results)
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        render_directory(args.directory)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
