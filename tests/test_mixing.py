import math
import struct
import subprocess

import pytest

from clipforge_skills.core import Fault, run
from clipforge_skills.mixing import audio_graph, check_loudness, measure_audio, measure_mix


def amplitude(path, start, duration=.25, frequency=220):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(path),
                                   '-t', str(duration), '-ac', '1', '-ar', '48000', '-f', 'f32le', '-'])
    samples = struct.unpack('<' + 'f' * (len(raw) // 4), raw)
    sin = sum(x * math.sin(2 * math.pi * frequency * i / 48000) for i, x in enumerate(samples))
    cos = sum(x * math.cos(2 * math.pi * frequency * i / 48000) for i, x in enumerate(samples))
    return 2 * math.hypot(sin, cos) / len(samples)


def mix(tmp_path, *, duplicate=False, duck=True, fade=False, normalize=False, no_voice=False):
    music = {'start': 0, 'duration': 4, 'gain_db': 0, 'role': 'music'}
    voice = {'start': 1, 'duration': 2, 'gain_db': 0, 'role': 'narration'}
    if fade:
        music.update(fade_in=.5, fade_out=.5)
    tracks = [music] + ([] if no_voice else [voice])
    inputs = ['-f', 'lavfi', '-i', 'sine=frequency=220:duration=4']
    if not no_voice:
        inputs += ['-f', 'lavfi', '-i', 'sine=frequency=880:duration=2']
    if duplicate:
        tracks.append(dict(voice))
        inputs += ['-f', 'lavfi', '-i', 'sine=frequency=880:duration=2']
    config = {'ducking': {'reduction_db': -12, 'attack': .1, 'release': .2}} if duck else {}
    if normalize:
        config['loudness'] = {'integrated_lufs': -16, 'true_peak_db': -1.5}
    # audio_graph indexes start at 1 because the renderer's first input is video.
    args = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=s=128x128:d=4', *inputs,
            '-filter_complex', audio_graph(tracks, 4, config), '-map', '[audio]']
    dest = tmp_path / ('result.m4a' if normalize else 'result.wav')
    run([*args, '-c:a', 'aac' if normalize else 'pcm_s16le', str(dest)])
    return dest


def test_music_ducks_once_and_recovers_without_attenuating_voice(tmp_path):
    single = mix(tmp_path)
    normal = amplitude(single, .5)
    ducked = amplitude(single, 1.5)
    assert 11 < 20 * math.log10(normal / ducked) < 13
    assert amplitude(single, 3.5) == pytest.approx(normal, rel=.05)
    voice_amplitude = amplitude(single, 1.5, frequency=880)
    other = tmp_path / 'overlap'
    other.mkdir()
    duplicate = mix(other, duplicate=True)
    assert amplitude(duplicate, 1.5) == pytest.approx(ducked, rel=.05)
    assert amplitude(duplicate, 1.5, frequency=880) == pytest.approx(2 * voice_amplitude, rel=.05)


def test_fades_and_missing_narration(tmp_path):
    result = mix(tmp_path, fade=True, no_voice=True)
    middle = amplitude(result, 2)
    assert amplitude(result, .01, .1) < middle * .3
    assert amplitude(result, 3.9, .08) < middle * .3
    assert amplitude(result, 1.5) == pytest.approx(middle, rel=.05)


def test_actual_aac_loudness_and_silent_rejection(tmp_path):
    output = mix(tmp_path, normalize=True, duck=False)
    target = {'integrated_lufs': -16, 'true_peak_db': -1.5}
    assert check_loudness(output, target)['status'] == 'passed'
    with pytest.raises(Fault):
        check_loudness(output, {**target, 'integrated_lufs': -23})
    silent = tmp_path / 'silent.wav'
    run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000', '-t', '3', silent])
    assert measure_audio(silent)['integrated_lufs'] is None
    with pytest.raises(Fault):
        check_loudness(silent, target)


def test_measurement_errors(tmp_path, monkeypatch):
    with pytest.raises(Fault):
        measure_audio(tmp_path / 'absent.wav')
    def unavailable(*args, **kwargs):
        raise OSError('ffmpeg missing')
    monkeypatch.setattr(subprocess, 'run', unavailable)
    with pytest.raises(Fault):
        measure_audio(tmp_path / 'x.wav')


def test_two_pass_variable_music_and_silent_analysis(tmp_path):
    target = {'integrated_lufs': -16, 'true_peak_db': -1.5}
    config = {'loudness': target}
    tracks = [{'start': 0, 'duration': 18.6, 'gain_db': 0, 'role': 'music', 'fade_out': .65}]
    args = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=s=128x128:d=18.6',
            '-f', 'lavfi', '-i', "sine=frequency=220:duration=18.6,volume='if(lt(t,3),0.2,1)':eval=frame"]
    measured = measure_mix(args, tracks, 18.6, config, tmp_path)
    output = tmp_path / 'two-pass.m4a'
    run([*args, '-filter_complex', audio_graph(tracks, 18.6, config, measured),
         '-map', '[audio]', '-c:a', 'aac', '-b:a', '192k', output])
    assert abs(measure_audio(output)['integrated_lufs'] + 16) < .5
    assert check_loudness(output, target)['status'] == 'passed'
    for invalid in [{}, {**measured, 'input_i': '-inf'}]:
        with pytest.raises(Fault):
            audio_graph(tracks, 18.6, config, invalid)
    silent_args = [*args[:-1], 'anullsrc=r=48000:d=18.6']
    silent = measure_mix(silent_args, tracks, 18.6, config, tmp_path)
    with pytest.raises(Fault):
        audio_graph(tracks, 18.6, config, silent)
