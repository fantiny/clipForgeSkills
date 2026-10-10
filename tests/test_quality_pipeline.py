"""Final encoded evidence, revision and cache behavior for the v2 extension."""
from copy import deepcopy
from pathlib import Path
import subprocess

from clipforge_skills.core import load_json
from clipforge_skills.render import render


def test_v2_final_mix_qa_and_overlay_only_revision(library, plan):
    # Fractional-second boundaries must survive source FPS conversion.
    plan['clips'][0]['end'] = 79 / 30
    plan['clips'][1]['end'] = 41 / 30
    plan.update(schema_version=2, overlays=[{
        'id': 'proof', 'start': .5, 'end': 2, 'text': 'DETAIL', 'fact_ids': [],
        'kind': 'card', 'font_size': 22, 'color': '#FFFFFF',
        'box': {'x': .1, 'y': .2, 'width': .8, 'height': .2}}],
        mix={'loudness': {'integrated_lufs': -16, 'true_peak_db': -1.5}})
    plan['clips'][0]['action_window'] = {'start': .2, 'end': 1.8, 'evidence': 'Technical timing fixture only'}
    first = render(library.root, plan, 'final')
    folder = Path(first['video']).parent
    qa = load_json(folder / 'qa.json')
    assert qa['loudness']['status'] == 'passed'
    assert qa['loudness']['listening_review'] == 'pending'
    assert 'DETAIL' not in (folder / 'captions.srt').read_text(encoding='utf-8')
    assert render(library.root, plan, 'final')['cache_hit']
    changed = deepcopy(plan)
    changed['overlays'][0]['color'] = '#FFCC44'
    second = render(library.root, changed, 'final')
    assert second['revision'] != first['revision']
    assert second['cache'] == {'clips_rendered': 0, 'clips_reused': 2}
    assert load_json(Path(second['video']).parent / 'plan.json')['clips'] == plan['clips']
    before, after = [], []
    for time, target in [(78 / 30, before), (79 / 30, after)]:
        target.extend(subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(time), '-i', first['video'],
                                              '-frames:v', '1', '-vf', 'crop=20:20:0:0,scale=1:1',
                                              '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-']))
    assert len(before) == len(after) == 3
    assert sum(abs(a-b) for a, b in zip(before, after)) > 200
