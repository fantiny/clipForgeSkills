"""Speech-driven shot lengths cannot overrun bounded source ranges."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('review_batch', Path(__file__).parents[1] / 'tools/production/build_review_batch.py')
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def test_allocation_bounds_and_exact_frame_total():
    ranges = [{'asset_id': 'a', 'start': .1, 'end': 1.1}, {'asset_id': 'b', 'start': 1, 'end': 5}]
    result = batch.allocate(ranges, 120)
    assert sum(round((x['end'] - x['start']) * 30) for x in result) == 120
    assert all(x['end'] <= y['end'] for x, y in zip(result, ranges))


@pytest.mark.parametrize('ranges,frames', [([], 30), ([{'start': 0, 'end': .4}], 20),
                                           ([{'start': 0, 'end': 1}], 31), ([{'start': 0, 'end': 1}], 10)])
def test_allocation_requires_real_coverage(ranges, frames):
    with pytest.raises(ValueError):
        batch.allocate(ranges, frames)


def test_recorded_voice_uses_real_audio_and_requires_rights(tmp_path, media_dir, monkeypatch):
    def no_tts(*args):
        raise AssertionError('Recorded audio must not request system speech')
    monkeypatch.setattr(batch, 'cli', no_tts)
    beat = {'audio_file': str(media_dir / 'narration.wav'), 'narration': '用户提供配音'}
    with pytest.raises(ValueError):
        batch.prepare_voice(beat, tmp_path, 0, media_dir)
    beat['audio_rights'] = {'status': 'confirmed', 'scopes': ['internal_review'], 'evidence': 'user licensed this recording'}
    voice = batch.prepare_voice(beat, tmp_path, 0, media_dir)
    assert voice['provider'] == 'provided_audio'
    assert abs(voice['duration'] - 4) < .1
    assert voice['metadata']['source_kind'] == 'captured'


def test_v2_batch_retimes_cues_without_cutting_action():
    beat = {'intent': 'show reveal', 'caption': 'Details', 'lead_in': .1, 'tail': .2,
            'shots': [{'asset_id': 'a', 'start': 0, 'end': 4,
                       'action_window': {'start': .2, 'end': 2, 'evidence': 'reviewed'}}],
            'cues': [{'start': .2, 'end': 1.9, 'text': 'Details', 'fact_ids': []}],
            'overlays': [{'start': .3, 'end': 2}]}
    result = batch.compile_beat(beat, 2.3, 30, 2)
    assert result['shots'][0]['end'] >= 2
    assert result['subtitles'][0]['start'] == pytest.approx(1.3)
    assert result['overlays'][0]['start'] == pytest.approx(1.3)
    assert result['voice_start'] == pytest.approx(1.1)
    assert result['frames'] == 78


@pytest.mark.parametrize('change', [{'lead_in': -1}, {'tail': float('nan')},
                                    {'cues': [{'start': 0, 'end': 4, 'text': 'too long'}]}])
def test_v2_batch_rejects_invalid_timing(change):
    beat = {'intent': 'test', 'caption': 'test',
            'shots': [{'asset_id': 'a', 'start': 0, 'end': 4,
                       'action_window': {'start': 0, 'end': 1, 'evidence': 'test'}}], **change}
    with pytest.raises(ValueError):
        batch.compile_beat(beat, 2, 0, 2)
