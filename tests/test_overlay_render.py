import subprocess

import pytest

from clipforge_skills.captions import write_captions
from clipforge_skills.core import run
from clipforge_skills.render import final_pass


@pytest.mark.parametrize('kind', ['emphasis', 'card', 'cta'])
def test_real_encoded_overlay_window_and_separate_srt(tmp_path, plan, library, kind):
    plan.update(schema_version=2, subtitles=[], audio=[], overlays=[
        {'id': 'detail', 'start': .5, 'end': 2, 'kind': kind, 'text': 'DETAIL', 'fact_ids': [],
         'box': {'x': .1, 'y': .2, 'width': .8, 'height': .2}, 'font_size': 24,
         'color': '#FFCC44', 'fade_in': .1, 'fade_out': .2}])
    run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=320x480:r=30:d=4',
         '-c:v', 'libx264', tmp_path / 'base.mp4'])
    write_captions(plan, tmp_path, plan['canvas'])
    final_pass(library, plan, tmp_path, 4)
    def lit_pixels(t):
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(tmp_path / 'output.mp4'),
                                       '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
        return sum(max(raw[i:i+3]) > 100 for i in range(0, len(raw), 3))
    assert lit_pixels(.1) == 0
    assert lit_pixels(1) > 100
    assert lit_pixels(2.5) == 0
    assert (tmp_path / 'captions.srt').read_text() == ''
