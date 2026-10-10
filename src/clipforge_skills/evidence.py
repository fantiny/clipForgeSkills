"""Bounded temporal evidence with real source PTS and no inferred observations."""
from fractions import Fraction
from html import escape
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .core import Fault, decode_output, digest, fingerprint, load_json, process_env, run, write_json
from .media import probe, versions

LIMIT = 120


def _request(start, end, fps, size, every_frame):
    values = (start, end, fps)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise Fault('invalid_evidence_request', 'Times and fps must be finite numbers')
    if not 0 <= start < end or end - start > 10 or not 0 < fps <= 60:
        raise Fault('invalid_evidence_request', 'Require 0<=start<end, span<=10s, 0<fps<=60')
    if isinstance(size, bool) or not isinstance(size, int) or not 160 <= size <= 1280 or size % 2:
        raise Fault('invalid_evidence_request', 'size must be an even integer from 160 to 1280')
    return {'start': start, 'end': end, 'fps': None if every_frame else fps,
            'size': size, 'mode': 'every_frame' if every_frame else 'sampled'}


def _clock(source):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'format=start_time',
                          '-of', 'json', source]))
    origin = float(data.get('format', {}).get('start_time', 0))
    if not math.isfinite(origin):
        raise Fault('invalid_media_clock', 'Container origin must be finite')
    return {'kind': 'relative_to_container_start', 'origin_seconds': origin,
            'source_absolute_time': 'origin_seconds + source_time'}


def _scale(size):
    return f'scale={size}:{size}:force_original_aspect_ratio=decrease:force_divisible_by=2'


def _input(source, request):
    return ['-copyts', '-start_at_zero', '-ss', str(request['start']),
            '-t', str(request['end'] - request['start'] + .1), '-i', str(source)]


def _frame_log(args, work):
    try:
        result = subprocess.run(args, capture_output=True, env=process_env(), timeout=120)
        log = decode_output(result.stderr)
    except UnicodeError as exc:
        raise Fault('tool_encoding', 'Evidence tool returned non-UTF-8 output') from exc
    except FileNotFoundError as exc:
        raise Fault('tool_missing', 'ffmpeg') from exc
    except subprocess.TimeoutExpired as exc:
        raise Fault('tool_timeout', 'Evidence extraction timed out', retryable=True) from exc
    (work / 'frames.log').write_text(log, encoding='utf-8')
    if result.returncode:
        raise Fault('tool_failed', 'Evidence frame extraction failed', details=log[-4000:])
    return log


def _parse_frames(log, work, request):
    bases = re.findall(r'config in time_base:\s*(\d+/\d+)', log)
    if not bases or len(set(bases)) != 1:
        raise Fault('invalid_media_clock', 'A stable frame time base is required')
    base = Fraction(bases[0])
    pts = re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:', log)
    images = sorted(work.glob('frame-*.jpg'))
    if len(images) > LIMIT:
        raise Fault('evidence_budget_exceeded', 'Narrow the range or lower fps; more than 120 frames')
    if not images or len(pts) < len(images):
        raise Fault('no_evidence_frames', 'No frames or timestamps in the requested range')
    frames = []
    for i, path in enumerate(images):
        number, stamp = map(int, pts[i])
        time = float(stamp * base)
        if number != i or not request['start'] - 1e-6 <= time < request['end']:
            raise Fault('invalid_media_clock', 'Frame timestamp falls outside the request')
        frames.append({'file': path.name, 'pts': stamp, 'time_base': bases[0],
                       'source_time': round(time, 9), 'sha256': digest(path)})
    return frames


def _frames(source, work, request):
    start, end = request['start'], request['end']
    filters = [f'trim=start={start}:end={end}']
    if request['fps'] is not None:
        filters.append(f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{1/request['fps']})'")
    filters.extend([_scale(request['size']), 'showinfo'])
    args = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'info', '-y', *_input(source, request),
            '-map', '0:v:0', '-an', '-vf', ','.join(filters), '-fps_mode', 'passthrough',
            '-frames:v', str(LIMIT + 1), '-q:v', '2', str(work / 'frame-%04d.jpg')]
    return _parse_frames(_frame_log(args, work), work, request)


def _clip(source, work, request, info):
    start, end = request['start'], request['end']
    args = ['ffmpeg', '-v', 'error', '-nostdin', '-y', *_input(source, request), '-map', '0:v:0',
            '-vf', f'trim=start={start}:end={end},setpts=PTS-{start}/TB,{_scale(request["size"])}',
            '-fps_mode', 'vfr', '-c:v', 'libx264', '-pix_fmt', 'yuv420p']
    if info['has_audio']:
        args += ['-map', '0:a:0', '-af', f'atrim=start={start}:end={end},asetpts=PTS-{start}/TB',
                 '-c:a', 'aac', '-b:a', '128k']
    else:
        args += ['-an']
    args += ['-movflags', '+faststart', work / 'clip.mp4']
    run(args)
    clip_info = probe(work / 'clip.mp4')
    run(['ffmpeg', '-v', 'error', '-xerror', '-i', work / 'clip.mp4', '-f', 'null', '-'])
    if clip_info['has_audio'] != info['has_audio']:
        raise Fault('evidence_audio_missing', 'Source audio did not survive the requested excerpt')
    return clip_info


def _index(work, source, request, frames):
    cards = ''.join(f'<figure><a href="{f["file"]}"><img loading="lazy" src="{f["file"]}" '
                    f'alt="Source time {f["source_time"]:.6f}"></a>'
                    f'<figcaption>{f["source_time"]:.6f}s</figcaption></figure>' for f in frames)
    html = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>局部时序证据</title>
<style>body{{font:16px system-ui;background:#14212b;color:#eee;margin:24px}}video{{width:min(100%,720px);max-height:60vh}}
section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}figure{{margin:0}}img{{width:100%}}
figcaption{{padding:6px}}a{{color:#acf}}</style><h1>局部时序证据</h1><p>{escape(source.name)}</p>
<p>源区间 [{request['start']}, {request['end']}) 秒 · {request['mode']} · {len(frames)} 帧</p>
<p>下面标注的是源帧时间。片段重新编码，视听判断仍待审；不代表素材授权或内容分析结论。</p>
<video controls preload="metadata" src="clip.mp4"></video><p><a href="evidence.json">查看完整证据清单</a></p>
<section>{cards}</section></html>'''
    (work / 'index.html').write_text(html, encoding='utf-8')


def _cached(work, key):
    try:
        report = load_json(work / 'evidence.json')
        signature = report.pop('manifest_signature')
        if signature != fingerprint(report):
            return None
        files = report['files']
        valid = report['evidence_id'] == key and files and all(
            Path(name).name == name and (work / name).is_file() and digest(work / name) == sha
            for name, sha in files.items())
        return report if valid else None
    except (Fault, KeyError, OSError):
        return None


def _summary(work, report, hit):
    return {'evidence_id': report['evidence_id'], 'artifact': str(work / 'evidence.json'),
            'index': str(work / 'index.html'), 'clip': str(work / 'clip.mp4'),
            'frame_count': len(report['frames']), 'cache_hit': hit}


def extract(source, out, start, end, *, fps=4, size=640, every_frame=False):
    request = _request(start, end, fps, size, every_frame)
    source, out = Path(source).resolve(), Path(out).resolve()
    info = probe(source)
    if not info['has_video'] or end > info['duration'] + .001:
        raise Fault('invalid_evidence_media', 'Require video and a range inside its duration')
    sha, tool_versions = digest(source), versions()
    key = 'evidence_' + fingerprint({'source': sha, 'request': request, 'tools': tool_versions,
                                   'implementation': digest(Path(__file__))})[:24]
    work = out / key
    cached = _cached(work, key)
    if cached:
        return _summary(work, cached, True)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.evidence-', dir=out) as temporary:
        stage = Path(temporary)
        frames = _frames(source, stage, request)
        clip_info = _clip(source, stage, request, info)
        _index(stage, source, request, frames)
        if digest(source) != sha:
            raise Fault('source_changed', 'Source changed during extraction; retry with a stable file')
        report = {'schema_version': 1, 'evidence_id': key, 'request': request,
                  'source': {'path': str(source), 'sha256': sha, 'technical': info},
                  'clock': _clock(source), 'tools': tool_versions, 'frames': frames,
                  'clip_technical': clip_info, 'visual_review': 'pending', 'audio_review': 'pending',
                  'files': {p.name: digest(p) for p in stage.iterdir() if p.is_file()}}
        report['manifest_signature'] = fingerprint(report)
        work.mkdir(parents=True, exist_ok=True)
        (work / 'evidence.json').unlink(missing_ok=True)
        for file in stage.iterdir():
            os.replace(file, work / file.name)
        write_json(work / 'evidence.json', report)
    return _summary(work, report, False)
