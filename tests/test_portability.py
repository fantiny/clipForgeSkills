"""Native OS tests, also usable by the engine-independent Windows CI job."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from clipforge_skills.core import Fault, locked, run, safe_id

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('value', ['CON', 'nul', 'AUX', 'prn', 'COM1', 'LPT9'])
def test_windows_reserved_ids_rejected_on_all_hosts(value):
    with pytest.raises(Fault):
        safe_id(value)


def test_utf8_child_protocol_even_with_legacy_parent_environment(monkeypatch):
    monkeypatch.setenv('PYTHONIOENCODING', 'ascii')
    assert run([sys.executable, '-c', "print('中文素材')"]).strip() == '中文素材'


def test_non_utf8_tool_output_is_explicit_fault():
    with pytest.raises(Fault) as exc:
        run([sys.executable, '-c', "import sys; sys.stdout.buffer.write(b'\\xff')"])
    assert exc.value.code == 'tool_encoding'


def test_lock_process_contention_and_abrupt_exit(tmp_path):
    script = ('import sys; from clipforge_skills.core import locked; '
              'ctx=locked(sys.argv[1]); ctx.__enter__(); print("locked",flush=True); sys.stdin.read()')
    proc = subprocess.Popen([sys.executable, '-c', script, str(tmp_path)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8')
    try:
        assert proc.stdout.readline().strip() == 'locked'
        with pytest.raises(Fault) as exc:
            with locked(tmp_path):
                pass
        assert exc.value.code == 'busy'
    finally:
        proc.kill()
        proc.communicate(timeout=10)
    with locked(tmp_path):
        pass


def test_portable_launcher_from_unrelated_chinese_directory(tmp_path):
    work = tmp_path / '中文 素材'
    work.mkdir()
    env = {**os.environ, 'PYTHONIOENCODING': 'ascii'}
    result = subprocess.run([sys.executable, ROOT / 'skills/clipforge/scripts/run.py', 'profiles'],
                            cwd=work, env=env, capture_output=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)['result']['profiles']) == 6


def test_launcher_reports_missing_environment(tmp_path):
    import shutil
    target = tmp_path / 'tools/clipforge.py'
    target.parent.mkdir()
    shutil.copyfile(ROOT / 'tools/clipforge.py', target)
    result = subprocess.run([sys.executable, target, 'profiles'], capture_output=True, encoding='utf-8')
    assert result.returncode == 1
    assert json.loads(result.stdout)['error_code'] == 'environment_missing'
