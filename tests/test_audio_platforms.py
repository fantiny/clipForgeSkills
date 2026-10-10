import json
import platform
from pathlib import Path

import pytest

from clipforge_skills import audio
from clipforge_skills.core import Fault


def test_windows_selects_installed_chinese_voice(monkeypatch):
    monkeypatch.setattr(audio, 'SYSTEM', 'Windows', raising=False)
    monkeypatch.setattr(audio.shutil, 'which', lambda _: 'powershell.exe')
    monkeypatch.setattr(audio, 'run', lambda *a, **k: json.dumps({'voices': [
        {'name': 'English', 'culture': 'en-US'}, {'name': 'Chinese', 'culture': 'zh-CN'}]}))
    assert audio.select_voice(None, '中文旁白') == ('windows_system_speech', 'Chinese')
    assert audio.select_voice('English', 'English narration') == ('windows_system_speech', 'English')
    with pytest.raises(Fault) as exc:
        audio.select_voice('Missing', '中文')
    assert exc.value.code == 'voice_unavailable'


def test_windows_does_not_silently_read_chinese_with_english_voice(monkeypatch):
    monkeypatch.setattr(audio, 'SYSTEM', 'Windows', raising=False)
    monkeypatch.setattr(audio.shutil, 'which', lambda _: 'powershell.exe')
    monkeypatch.setattr(audio, 'run', lambda *a, **k: '{"voices":[{"name":"English","culture":"en-US"}]}')
    with pytest.raises(Fault):
        audio.select_voice(None, '中文旁白')


def test_windows_power_shell_missing_is_explicit(monkeypatch):
    monkeypatch.setattr(audio, 'SYSTEM', 'Windows', raising=False)
    monkeypatch.setattr(audio.shutil, 'which', lambda _: None)
    with pytest.raises(Fault) as exc:
        audio.select_voice(None, '中文')
    assert exc.value.code == 'tts_unavailable'


@pytest.mark.skipif(platform.system() != 'Windows', reason='Native Windows System.Speech test')
def test_native_windows_speech_and_cache(tmp_path):
    text = tmp_path / '旁白.txt'
    text.write_text('This is a technical speech test.', encoding='utf-8')
    result = audio.speech(tmp_path, text)
    manifest = json.loads(Path(result['artifact']).read_text(encoding='utf-8'))
    assert manifest['provider'] == 'windows_system_speech'
    assert manifest['duration'] > 0
    assert audio.speech(tmp_path, text)['cache_hit']
