#!/usr/bin/env python3
"""Isolated source probes; never imports the upstream app or touches real drafts."""
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tmp/research-excerpts/jianying-editor-skill'
OUT = ROOT / 'tmp/harness-research/jianying'
COMMIT = '32c56928ded4f9e2c2b80e099dc7abb793d2c30b'
FILES = {}


def definitions(relative, names, env):
    """Load only explicitly reviewed definitions, with dependencies supplied by caller."""
    path = SOURCE / relative
    raw = path.read_bytes()
    FILES[relative] = hashlib.sha256(raw).hexdigest()
    tree = ast.parse(raw, filename=relative)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
             and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise RuntimeError('Expected upstream definitions have changed')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), relative, 'exec'), env)
    return env


def staging_probe(root):
    env = definitions('scripts/core/media_ops.py', ['MediaOpsMixin'],
                      {'hashlib': hashlib, 'os': os, 'shutil': shutil, 'Union': __import__('typing').Union})
    obj = env['MediaOpsMixin']()
    obj.draft_dir = str(root / 'draft')
    source = root / 'source.bin'
    source.write_bytes(b'AAAA')
    first = Path(obj._stage_local_asset(str(source)))
    source.write_bytes(b'BBBB')
    second = Path(obj._stage_local_asset(str(source)))
    result = {'same_path': first == second, 'source_hex': source.read_bytes().hex(),
              'staged_hex': second.read_bytes().hex()}
    assert result['same_path'] and result['source_hex'] != result['staged_hex']
    return result


def recovery_probe(root):
    calls = []

    class FakeDraftFolder:
        def __init__(self, path): pass
        def has_draft(self, name): return True
        def load_template(self, name): raise ValueError('injected incompatible draft')
        def create_draft(self, name, width, height, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace()

    project = root / 'existing'
    project.mkdir()
    for name in ('draft_info.json', 'draft_meta_info.json'):
        (project / name).write_text('{}')
    env = definitions('scripts/core/project_base.py', ['JyProjectBase'],
                      {'os': os, 're': re, 'shutil': shutil,
                       'draft': SimpleNamespace(DraftFolder=FakeDraftFolder)})
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        env['JyProjectBase']('existing', drafts_root=str(root), overwrite=False)
    assert calls == [{'allow_replace': True}]
    return {'overwrite_requested': False, 'mock_create_calls': calls,
            'log': log.getvalue(), 'real_draft_deleted': False}


def matching_probe(root):
    env = definitions('examples/video_transcribe_and_match.py', ['ai_match_subtitles'],
                      {'os': os, 'List': List, 'Dict': Dict,
                       'CHAT_SCRIPT': str(root / 'absent-chat.py')})
    result = env['ai_match_subtitles'](
        [{'index': 1, 'text': '包装封口'}, {'index': 2, 'text': '保质日期'}, {'index': 3, 'text': '配料'}],
        [{'filename': 'unrelated-a.mp4'}, {'filename': 'unrelated-b.mp4'}])
    assert [r['id'] for r in result] == [0, 1, 0]
    return {'missing_model_fallback': result, 'visual_evidence_supplied': False}


def geometry_probe(root):
    path = SOURCE / 'scripts/utils/media_normalizer.py'
    names = [n.name for n in ast.parse(path.read_bytes()).body if isinstance(n, ast.FunctionDef)]
    env = definitions(str(path.relative_to(SOURCE)), names,
                      {'os': os, 'json': json, 'subprocess': subprocess, 'Optional': Optional})
    source = root / 'portrait.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'color=red:s=1080x1920:r=30:d=0.1', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(source)], check=True, timeout=30)
    output = env['normalize_video_for_jianying'](str(source))
    before, after = env['_probe_video'](str(source)), env['_probe_video'](output)
    assert (after['width'], after['height']) == (1920, 1080)
    return {'input': before, 'normalized': after,
            'note': 'Actual FFmpeg synthetic media; no Jianying app acceptance'}


def main():
    head = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    if head != COMMIT:
        raise SystemExit('Source checkout must match reviewed commit')
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='probe-', dir=OUT) as temp:
        root = Path(temp)
        results = {'staging': staging_probe(root), 'recovery': recovery_probe(root),
                   'matching': matching_probe(root), 'geometry': geometry_probe(root)}
    report = {'commit': head, 'source_sha256': FILES, 'probes': results,
              'scope': '4 isolated probes, not upstream full tests or editor acceptance'}
    (OUT / 'probes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
