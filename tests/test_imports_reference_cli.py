import json
from pathlib import Path
import subprocess

from openpyxl import Workbook
import pytest

from clipforge_skills import audio, importers, media
from clipforge_skills.cli import main
from clipforge_skills.core import Fault, load_json, write_json


def test_workbook_preserves_fields_and_missing_media(tmp_path):
    path = tmp_path / "source.xlsx"
    w = Workbook()
    s = w.active
    s.append(["素材索引"])
    s.append(["编号", "文件名", "存储路径", "备注"])
    s.append(["1", "missing.mp4", "missing-directory", "Example, not a confirmed fact"])
    w.save(path)
    out = importers.import_docs(tmp_path / "data", [path])
    assert out["worksheets"] == 1
    source = load_json(out["sources"][0]["artifact"])
    assert source["index_rows"][0]["media_status"] == "not_resolved"
    assert source["facts_status"] == "pending"
    with pytest.raises(Fault): importers.import_docs(tmp_path, [tmp_path / "no.xls"])


@pytest.mark.parametrize("envelope", [True, False])
def test_legacy_real_shapes(tmp_path, media_dir, envelope):
    path = tmp_path / "index.json"
    rows = [{"编号": "legacy1", "存储路径": "first.mp4", "行为": "test signal", "start_time": .5, "end_time": 2},
            {"编号": "legacy2", "存储路径": "absent.mp4"}, {"编号": "legacy3"}]
    path.write_text(json.dumps({"schema_version": 1, "rows": rows} if envelope else rows))
    out = importers.import_hub(tmp_path / "data", path, media_dir)
    assert out["mapped"] == 1 and out["missing"] == 2
    from clipforge_skills.library import Library
    assert Library(tmp_path / "data").records()[0]["annotations"][0]["source"] == "legacy"
    write_json(path, {"schema_version": 2, "rows": []})
    with pytest.raises(Fault): importers.import_hub(tmp_path / "data", path, media_dir)


def test_reference_produces_timestamped_frames_and_repairs_cache(tmp_path, media_dir):
    first = media.reference(media_dir / "first.mp4", tmp_path, 3)
    assert len(first["frames"]) == 3
    assert media.reference(media_dir / "first.mp4", tmp_path, 3)["cache_hit"]
    frame = Path(first["artifact"]).parent / first["frames"][0]["file"]
    frame.write_bytes(b"corrupt")
    assert not media.reference(media_dir / "first.mp4", tmp_path, 3)["cache_hit"]
    assert load_json(first["artifact"])["popularity"] is None
    with pytest.raises(Fault): media.reference(media_dir / "first.mp4", tmp_path, 99)
    with pytest.raises(Fault): media.reference(media_dir / "narration.wav", tmp_path)
    with pytest.raises(Fault): media.probe(tmp_path / "absent.mp4")


def test_cli_json_and_real_paths(tmp_path, media_dir, capsys):
    data = tmp_path / "data"
    assert main(["--data", str(data), "ingest", str(media_dir)]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["new"] == 3
    assert main(["--data", str(data), "search"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["candidates"] == []
    assert main(["--data", str(data), "validate", str(tmp_path / "missing.json")]) == 2
    assert not json.loads(capsys.readouterr().out)["ok"]
    assert main(["invalid-command"]) == 2
    assert json.loads(capsys.readouterr().out)["error_code"] == "usage"
    assert len(list((data / "logs").glob("*.json"))) == 3
    assert main(["--data", str(data), "doctor"]) == 0
    doctor_result = json.loads(capsys.readouterr().out)['result']
    from clipforge_skills.media import engine_root
    from clipforge_skills.core import ENGINE_REVISION
    engine = engine_root()
    expected_ready = ((engine / 'REVISION').is_file() and
                      (engine / 'REVISION').read_text(encoding='utf-8').strip() == ENGINE_REVISION and
                      (engine / 'vidmake/src/feedcut_compose').is_dir())
    assert doctor_result['engine_ready'] == expected_ready
    assert main(["--data", str(data), "profiles"]) == 0
    assert len(json.loads(capsys.readouterr().out)["result"]["profiles"]) == 6


def test_speech_missing_or_empty(tmp_path, monkeypatch):
    text = tmp_path / "text.txt"
    text.write_text("")
    with pytest.raises(Fault): audio.speech(tmp_path, text)
    text.write_text("Test voice")
    monkeypatch.setattr(audio.shutil, "which", lambda _: None)
    with pytest.raises(Fault): audio.speech(tmp_path, text)


def test_host_paths_share_identical_skill_and_cli():
    root = Path(__file__).resolve().parents[1]
    for skill in (root / "skills").iterdir():
        if not skill.is_dir():
            continue
        for host in (".agents", ".claude"):
            linked = root / host / "skills" / skill.name
            assert (linked / 'SKILL.md').read_bytes() == (skill / 'SKILL.md').read_bytes()
            assert (linked / 'scripts/run.py').read_bytes() == (root / 'tools/dev/skill_entry.py').read_bytes()


def test_workbook_retains_image_bytes_and_dates(tmp_path):
    from datetime import datetime
    from zipfile import ZipFile
    from openpyxl import Workbook
    from clipforge_skills.core import load_json
    path = tmp_path / 'pictures.xlsx'
    wb = Workbook()
    wb.active['A1'] = datetime(2026, 1, 1)
    wb.save(path)
    wb.close()
    image_bytes = b'reference-only image evidence'
    with ZipFile(path, 'a') as archive:
        archive.writestr('xl/media/image1.png', image_bytes)
    result = importers.import_docs(tmp_path / 'data', [path])
    assert result['images'] == 1
    source = load_json(result['sources'][0]['artifact'])
    assert Path(source['images'][0]['file']).read_bytes() == image_bytes
    assert source['images'][0]['purpose'] == 'reference_only'
    assert source['sheets'][0]['cells'][0]['value'].startswith('2026-01-01')


def test_system_speech_actual_cache_and_corruption(tmp_path):
    import shutil
    from clipforge_skills import audio
    from clipforge_skills.core import load_json, run
    if not shutil.which('say') or 'Tingting ' not in run(['say', '-v', '?']):
        pytest.skip('Offline macOS Tingting voice not installed')
    source = tmp_path / 'speech.txt'
    source.write_text('这是技术测试。', encoding='utf-8')
    with pytest.raises(Fault) as exc:
        audio.speech(tmp_path, source, 'MissingVoiceForTest')
    assert exc.value.code == 'voice_unavailable'
    first = audio.speech(tmp_path, source)
    assert first['duration'] > 0
    assert load_json(first['artifact'])['alignment'] == 'not_computed'
    assert audio.speech(tmp_path, source)['cache_hit'] is True
    Path(first['audio']).write_bytes(b'broken cache')
    assert audio.speech(tmp_path, source)['cache_hit'] is False
