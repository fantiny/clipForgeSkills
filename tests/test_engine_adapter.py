import importlib.util
from pathlib import Path
import shutil
import subprocess

from clipforge_skills.core import digest
from clipforge_skills.media import probe

spec = importlib.util.spec_from_file_location('engine_stage', Path(__file__).parents[1] / 'tools/engine/run_stage.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def test_frame_limit_at_existing_encode_boundary(tmp_path):
    dest = tmp_path / 'exact.mp4'
    runner = adapter.frame_limited_runner(lambda cmd, **kw: subprocess.run(cmd, check=True, **kw), 79)
    runner(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=32x32:r=30:d=2.7',
            '-c:v', 'libx264', '-r', '30', str(dest)])
    assert abs(probe(dest)['duration'] - 79 / 30) < 1e-6
    seen = []
    adapter.frame_limited_runner(lambda cmd: seen.append(cmd), 79)(['ffprobe', str(dest)])
    assert seen == [['ffprobe', str(dest)]]


def test_concat_unicode_quotes_and_spaces(tmp_path, media_dir):
    work = tmp_path / "中文 user's folder"
    work.mkdir()
    source = work / "镜头 '一'.mp4"
    shutil.copyfile(next(media_dir.glob('*.mp4')), source)
    before = digest(source)
    output = work / 'result.mp4'
    adapter.portable_concat([source, source], output)
    assert abs(probe(output)['duration'] - 2 * probe(source)['duration']) < .2
    assert digest(source) == before
    assert not list(work.glob('concat-*'))


def test_caption_audio_render_components_without_private_engine(tmp_path, library, plan):
    from clipforge_skills.captions import write_captions
    from clipforge_skills.render import final_pass
    from clipforge_skills.media import technical_check
    work = tmp_path / '字幕 配音'
    work.mkdir()
    sources = [library.resolve(library.get(clip['asset_id'])) for clip in plan['clips']]
    adapter.portable_concat(sources, work / 'base.mp4')
    write_captions(plan, work, plan['canvas'])
    final_pass(library, plan, work, 4)
    qa = technical_check(work / 'output.mp4', plan['canvas'], 4)
    assert qa['metadata']['has_audio']
    assert '跨镜字幕' in (work / 'captions.srt').read_text(encoding='utf-8')
