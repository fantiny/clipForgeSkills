"""Explicit batch preflight and failed-run progress must not imply delivery."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('render_directory', Path(__file__).parents[1] / 'tools/production/render_plan_directory.py')
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def plans(root, count):
    for i in range(count):
        folder = root / f'{i:02}-中文场景'
        folder.mkdir(parents=True)
        (folder / 'plan.json').write_text('{}', encoding='utf-8')


def test_missing_empty_and_excess_plans(tmp_path, monkeypatch):
    monkeypatch.setattr(batch.subprocess, 'run', lambda *a, **k: pytest.fail('No subprocess allowed'))
    for folder in [tmp_path / 'missing', tmp_path]:
        with pytest.raises(ValueError):
            batch.render_directory(folder)
    plans(tmp_path, 25)
    with pytest.raises(ValueError):
        batch.render_directory(tmp_path)


def test_preflight_failure_clears_old_progress_without_render(tmp_path, monkeypatch):
    plans(tmp_path, 2)
    (tmp_path / 'render-progress.json').write_text('[{"scene":"old"}]', encoding='utf-8')
    calls = []

    def run(args, **kwargs):
        calls.append(args[4])
        assert args[4] == 'validate'
        return SimpleNamespace(returncode=int(len(calls) == 2), stdout=json.dumps({'ok': len(calls) == 1}))

    monkeypatch.setattr(batch.subprocess, 'run', run)
    with pytest.raises(RuntimeError):
        batch.render_directory(tmp_path)
    assert calls == ['validate', 'validate']
    assert json.loads((tmp_path / 'render-progress.json').read_text()) == []


def test_render_failure_records_only_current_success_then_cache_resume(tmp_path, monkeypatch):
    root = tmp_path / '批次'; plans(root, 2)
    work = tmp_path / 'work'; work.mkdir()
    names = ['output.mp4', 'captions.srt', 'captions.ass', 'cover.jpg', 'qa.json', 'manifest.json', 'loudness-analysis.json']
    for name in names:
        (work / name).write_text('技术样例', encoding='utf-8')
    calls = []
    fail = True

    def run(args, **kwargs):
        command = args[4]; calls.append(command)
        assert kwargs['encoding'] == 'utf-8'
        assert args[:3] == [batch.sys.executable, '-X', 'utf8']
        bad = fail and command == 'render' and '01-' in args[5]
        result = {'revision': Path(args[5]).parent.name, 'video': str(work / 'output.mp4'), 'cache_hit': True}
        return SimpleNamespace(returncode=int(bad), stdout=json.dumps({'ok': not bad, 'result': result}, ensure_ascii=False))

    monkeypatch.setattr(batch.subprocess, 'run', run)
    with pytest.raises(RuntimeError):
        batch.render_directory(root)
    assert calls == ['validate', 'validate', 'render', 'render']
    assert len(json.loads((root / 'render-progress.json').read_text(encoding='utf-8'))) == 1
    fail = False
    result = batch.render_directory(root)
    assert len(result) == 2 and all(x['cache_hit'] for x in result)
    assert (root / '01-中文场景/captions.srt').read_text(encoding='utf-8') == '技术样例'
