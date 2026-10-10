import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('skill_install', ROOT / 'tools/dev/install_skills.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def package(tmp_path):
    root = tmp_path / 'package'
    for name in ['clipforge', 'clipforge-audio']:
        skill = root / 'skills' / name
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('用户制作目标', encoding='utf-8')
    return root


def test_install_update_no_links_and_preserve_edits(tmp_path):
    root = package(tmp_path)
    target = tmp_path / '中文 项目'
    paths = installer.install(root, target, ['codex', 'claude'])
    assert len(paths) == 4
    assert all(not Path(p).is_symlink() for p in paths)
    changed = root / 'skills/clipforge/SKILL.md'
    changed.write_text('新目标', encoding='utf-8')
    installer.install(root, target, ['codex', 'claude'])
    assert (Path(paths[0]) / 'SKILL.md').read_text(encoding='utf-8') == '新目标'
    edited = Path(paths[-1]) / 'SKILL.md'
    edited.write_text('user edit', encoding='utf-8')
    changed.write_text('third version', encoding='utf-8')
    with pytest.raises(ValueError):
        installer.install(root, target, ['codex', 'claude'])
    assert (Path(paths[0]) / 'SKILL.md').read_text(encoding='utf-8') == '新目标'
    assert edited.read_text(encoding='utf-8') == 'user edit'


def test_legacy_git_placeholder_migration_and_other_files_protected(tmp_path):
    root = package(tmp_path)
    dest = root / '.agents/skills/clipforge'
    dest.parent.mkdir(parents=True)
    dest.write_text('../../skills/clipforge', encoding='utf-8')
    installer.install(root, root, ['codex'])
    assert dest.is_dir() and not dest.is_symlink()
    (dest / 'user-notes.txt').write_text('keep me', encoding='utf-8')
    with pytest.raises(ValueError):
        installer.install(root, root, ['codex'])
    assert (dest / 'user-notes.txt').read_text(encoding='utf-8') == 'keep me'


def test_external_copy_launcher_uses_original_locked_runtime(tmp_path):
    installer.install(ROOT, tmp_path / 'target', ['codex'])
    entry = tmp_path / 'target/.agents/skills/clipforge/scripts/run.py'
    result = subprocess.run([sys.executable, entry, 'profiles'], cwd=tmp_path,
                            capture_output=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)['result']['profiles']) == 6


def test_installer_never_calls_symlink_or_relpath(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('link or cross-drive relative path requested')
    monkeypatch.setattr(Path, 'symlink_to', forbidden)
    import os
    monkeypatch.setattr(os.path, 'relpath', forbidden)
    installer.install(package(tmp_path), tmp_path / 'other-volume', ['codex'])
