#!/usr/bin/env python3
"""Compile an explicit, reviewed shot selection using measured local speech.

No automatic scene choice, duration guesses, looping, or approval records.
Run with the project's existing .venv Python; inputs/outputs stay local.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from clipforge_skills.core import HOME, digest, process_env, write_json
from clipforge_skills.media import probe
from clipforge_skills.timing import allocate_actions


def cli(*args):
    result = subprocess.run([sys.executable, '-X', 'utf8', str(HOME / 'tools/clipforge.py'), *map(str, args)],
                            capture_output=True, encoding='utf-8', env=process_env(), timeout=1800)
    response = json.loads(result.stdout)
    if result.returncode or not response.get('ok'):
        raise RuntimeError(response)
    return response['result']


def allocate(ranges, frames):
    """Bounded source intervals; never loop or stretch to cover excess speech."""
    capacities = [math.floor((x['end'] - x['start']) * 30 + 1e-6) for x in ranges]
    if not ranges or min(capacities) < 15 or frames < len(ranges) * 15 or sum(capacities) < frames:
        raise ValueError(f'Shot coverage cannot fit {frames / 30:.2f}s; revise the beat')
    lengths = [15] * len(ranges)
    remaining = frames - sum(lengths)
    while remaining:
        for i in range(len(ranges)):
            if lengths[i] < capacities[i] and remaining:
                lengths[i] += 1
                remaining -= 1
    return [{**x, 'end': round(x['start'] + length / 30, 9)} for x, length in zip(ranges, lengths)]


def prepare_voice(beat, folder, index, base):
    target = folder / 'voice' / str(index + 1) / 'voice.wav'
    if beat.get('audio_file'):
        rights = beat.get('audio_rights', {})
        if rights.get('status') != 'confirmed' or 'internal_review' not in rights.get('scopes', []) or not rights.get('evidence'):
            raise ValueError('Provided audio requires confirmed internal_review rights and evidence')
        source = (base / beat['audio_file']).resolve()
        info = probe(source)
        if not info['has_audio']:
            raise ValueError('Provided narration must contain audio')
        # Keep the actual format; do not rename an MP3 to WAV.
        target = target.with_suffix(source.suffix.lower())
        voice = {'provider': 'provided_audio', 'duration': info['duration'], 'sha256': digest(source)}
        kind = 'captured'
    else:
        folder.mkdir(parents=True, exist_ok=True)
        text = folder / f'narration-{index + 1}.txt'
        text.write_text(beat['narration'], encoding='utf-8')
        args = ['speech', text]
        if beat.get('voice'):
            args += ['--voice', beat['voice']]
        result = cli(*args)
        source = Path(result['audio'])
        voice = json.loads(Path(result['artifact']).read_text(encoding='utf-8'))
        rights = {'status': 'confirmed', 'scopes': ['internal_review'],
                  'evidence': f"Local {voice['provider']} speech of authored internal-review copy; user requested these drafts."}
        kind = 'generated'
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return {**voice, 'file': str(target), 'metadata': {'sku': '*', 'packaging': 'not_applicable',
            'source_kind': kind, 'rights': rights}}


def compile_beat(beat, voice_duration, cursor_frames, version):
    lead, tail = (beat.get('lead_in', .12), beat.get('tail', .38)) if version == 2 else (.12, .38)
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0 <= x <= 5
               for x in (lead, tail)):
        raise ValueError('lead_in and tail require finite seconds between 0 and 5')
    frames = (math.ceil((voice_duration + .5) * 30) if version == 1
              else math.ceil((voice_duration + lead + tail) * 30 - 1e-8))
    selection = allocate_actions(beat['shots'], frames) if version == 2 else allocate(beat['shots'], frames)
    start, end = cursor_frames / 30, (cursor_frames + frames) / 30
    cues = beat.get('cues') if version == 2 else None
    if cues is not None:
        if any(not 0 <= c['start'] < c['end'] <= voice_duration for c in cues):
            raise ValueError('Cues must use the actual narration time range')
        subtitles = [{**c, 'start': start + lead + c['start'], 'end': start + lead + c['end']} for c in cues]
    else:
        subtitles = [{'start': start, 'end': end - .08, 'text': beat['caption'], 'fact_ids': []}]
    overlays = [{**o, 'start': start + o['start'], 'end': start + o['end']}
                for o in beat.get('overlays', [])] if version == 2 else []
    if any(not start <= o['start'] < o['end'] <= end for o in overlays):
        raise ValueError('Overlay extends beyond its beat')
    return {'frames': frames, 'shots': selection, 'subtitles': subtitles, 'overlays': overlays,
            'voice_start': start + lead, 'start': start, 'end': end}


def prepare(scene, out, base=None):
    version = scene.get('schema_version', 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError('Batch scene requires schema_version 1 or 2')
    folder = out / scene['scenario']
    voice_dir = folder / 'voice'
    voice_dir.mkdir(parents=True, exist_ok=True)
    voices = []
    for i, beat in enumerate(scene['beats']):
        voice = prepare_voice(beat, folder, i, base or Path.cwd())
        metadata = write_json(Path(voice['file']).parent / 'metadata.json', voice['metadata'])
        ingested = cli('ingest', voice['file'], '--metadata', metadata)
        if ingested['errors']:
            raise RuntimeError(ingested['errors'])
        voices.append(voice)
    clips, subtitles, audio, beats, overlays = [], [], [], [], []
    cursor_frames = 0
    for i, (beat, voice) in enumerate(zip(scene['beats'], voices)):
        compiled = compile_beat(beat, voice['duration'], cursor_frames, version)
        frames, start, selection = compiled['frames'], compiled['start'], compiled['shots']
        for shot in selection:
            clips.append({**shot, 'role': f'beat-{i + 1}: {beat["intent"]}', 'audio': 'mute'})
        audio.append({'asset_id': 'asset_' + voice['sha256'][:24], 'source_start': 0,
                      'start': compiled['voice_start'], 'duration': voice['duration'], 'gain_db': -2, 'role': 'narration'})
        cursor_frames += frames
        subtitles.extend(compiled['subtitles'])
        overlays.extend(compiled['overlays'])
        beats.append({**beat, 'output_start': start, 'output_end': cursor_frames / 30,
                      'voice_duration': voice['duration'], 'actual_shots': selection})
    plan = {'schema_version': version, 'content_id': scene.get('content_id', 'review-' + scene['scenario'] + '-review-v1'),
            'purpose': 'internal_review', 'brief': {'scenario': scene['scenario'], 'sku': 'pending-review',
            'audience': scene['audience'], 'channel': 'internal_review', 'cta': scene['cta']},
            'canvas': {'width': 1080, 'height': 1920, 'fps': 30}, 'clips': clips,
            'subtitles': subtitles, 'audio': audio, 'fact_ids': [],
            'style': {'font_size': 76, 'color': '#FFFFFF'},
            'title': scene['title'], 'description': scene['goal']}
    if version == 2:
        plan.update(overlays=overlays, mix=scene.get('mix', {}))
        plan['audio'].extend(scene.get('audio', []))
    write_json(folder / 'creative-notes.json', {**scene, 'beats': beats, 'status': 'internal_review',
               'audio_review': 'pending_actual_listening', 'business_approval': 'pending'})
    path = write_json(folder / 'plan.json', plan)
    validation = cli('validate', path)
    write_json(folder / 'validation.json', validation)
    print(json.dumps({'prepared': scene['scenario'], 'duration': validation['duration']}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--scenario')
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    for scene in json.loads(args.batch.read_text(encoding='utf-8'))['scenes']:
        if args.scenario and scene['scenario'] != args.scenario:
            continue
        folder = out / scene['scenario']
        if not args.render:
            prepare(scene, out, args.batch.resolve().parent)
            continue
        result = cli('render', folder / 'plan.json', '--mode', 'final')
        write_json(folder / 'render-result.json', result)
        source = Path(result['video']).parent
        for name in ('output.mp4', 'captions.srt', 'cover.jpg', 'qa.json', 'manifest.json'):
            shutil.copy2(source / name, folder / name)
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
