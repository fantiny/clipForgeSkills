"""Deterministic track envelopes and measured final-file loudness, all local."""
import json
import math
import re
import subprocess

from .core import Fault, decode_output, process_env


def duck_expression(narration, config):
    attack, release = config['attack'], config['release']
    ramps = []
    for track in narration:
        start, end = track['start'], track['start'] + track['duration']
        ramps.append(f"min(clip((t-({start-attack}))/({attack}),0,1),clip((({end+release})-t)/({release}),0,1))")
    envelope = ramps[0]
    for ramp in ramps[1:]:
        envelope = f'max({envelope},{ramp})'
    return f'pow(10,({config["reduction_db"]})*({envelope})/20)'


def track_filter(index, track, narration, mixing):
    chain = ['asetpts=PTS-STARTPTS', 'aresample=48000', f"volume={track['gain_db']}dB"]
    fade_in, fade_out = track.get('fade_in', 0), track.get('fade_out', 0)
    if fade_in:
        chain.append(f'afade=t=in:st=0:d={fade_in}')
    if fade_out:
        chain.append(f"afade=t=out:st={track['duration']-fade_out}:d={fade_out}")
    chain.append(f"adelay={round(track['start']*1000)}:all=1")
    if track['role'] == 'music' and narration and mixing.get('ducking'):
        expression = duck_expression(narration, mixing['ducking'])
        chain.append(f"volume='{expression}':eval=frame")
    return f'[{index}:a]' + ','.join(chain) + f'[a{index}]'


def loudness_filter(target, measurement=None):
    expression = f"loudnorm=I={target['integrated_lufs']}:TP={target['true_peak_db']}:LRA=7"
    if measurement is not None:
        fields = {'measured_I': 'input_i', 'measured_TP': 'input_tp',
                  'measured_LRA': 'input_lra', 'measured_thresh': 'input_thresh', 'offset': 'target_offset'}
        try:
            values = {option: float(measurement[key]) for option, key in fields.items()}
        except (KeyError, TypeError, ValueError) as exc:
            raise Fault('audio_measure_failed', 'Incomplete first-pass loudness analysis') from exc
        if not all(math.isfinite(value) for value in values.values()):
            raise Fault('audio_loudness_failed', 'No finite first-pass audio loudness')
        expression += ''.join(f':{key}={value}' for key, value in values.items()) + ':linear=true'
    return expression + ':print_format=json'


def audio_graph(tracks, duration, mixing, measurement=None):
    narration = [t for t in tracks if t['role'] == 'narration']
    filters = [track_filter(i, t, narration, mixing) for i, t in enumerate(tracks, 1)]
    labels = ''.join(f'[a{i}]' for i in range(1, len(tracks) + 1))
    final = f'{labels}amix=inputs={len(tracks)}:duration=longest:normalize=0,apad,atrim=duration={duration}'
    target = mixing.get('loudness')
    if target:
        final += (',aformat=channel_layouts=stereo,' + loudness_filter(target, measurement)
                  + ',aresample=48000,aformat=channel_layouts=stereo')
    return ';'.join(filters + [final + '[audio]'])


def measurement_report(args, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, env=process_env(), timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Fault('audio_measure_failed', str(exc)) from exc
    log = decode_output(result.stderr)
    matches = re.findall(r'\{\s*"input_i".*?\}', log, re.S)
    if result.returncode or not matches:
        raise Fault('audio_measure_failed', 'Final audio measurement failed', details=log[-2000:])
    return json.loads(matches[-1])


def measure_mix(args, tracks, duration, mixing, cwd):
    return measurement_report([*args, '-v', 'info', '-nostats', '-filter_complex',
                               audio_graph(tracks, duration, mixing), '-map', '[audio]',
                               '-vn', '-f', 'null', '-'], cwd)


def measure_audio(path):
    raw = measurement_report(['ffmpeg', '-hide_banner', '-nostats', '-i', str(path), '-vn',
                              '-af', 'loudnorm=print_format=json', '-f', 'null', '-'])
    fields = {'integrated_lufs': 'input_i', 'true_peak_db': 'input_tp', 'lra_lu': 'input_lra'}
    values = {name: float(raw[key]) for name, key in fields.items()}
    # Silence may yield +/-inf; it cannot satisfy a requested loudness target.
    return {name: value if math.isfinite(value) else None for name, value in values.items()}


def check_loudness(path, target):
    values = measure_audio(path)
    if any(value is None for value in values.values()):
        raise Fault('audio_loudness_failed', 'No finite final audio loudness', details=values)
    if (abs(values['integrated_lufs'] - target['integrated_lufs']) > 1
            or values['true_peak_db'] > target['true_peak_db'] + .2):
        raise Fault('audio_loudness_failed', 'Final encoded audio exceeds the agreed tolerances', details=values)
    return {'measured': values, 'target': target, 'status': 'passed', 'listening_review': 'pending'}
