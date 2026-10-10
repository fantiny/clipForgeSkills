#!/usr/bin/env python3
"""Compare sparse navigation and local evidence on a synthetic two-frame flash."""
from pathlib import Path
import json
import subprocess

from clipforge_skills.core import run, write_json
from clipforge_skills.evidence import extract
from clipforge_skills.media import reference


def brightness(path):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vf',
                             'scale=1:1,format=gray', '-frames:v', '1', '-f',
                             'rawvideo', '-'], capture_output=True, check=True)
    if len(result.stdout) != 1:
        raise RuntimeError('Expected one measured grayscale pixel')
    return result.stdout[0]


def main():
    root = Path(__file__).resolve().parents[2] / 'tmp/evidence-demo'
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'synthetic-flash.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
         'color=black:s=160x160:r=30:d=3', '-vf',
         "drawbox=color=white:t=fill:enable='between(n,31,32)'",
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', source])
    sparse = reference(source, root / 'sparse', count=8)
    dense = extract(source, root / 'dense', 1, 1.2, every_frame=True, size=160)
    report = json.loads(Path(dense['artifact']).read_text(encoding='utf-8'))
    sparse_values = [brightness(Path(sparse['artifact']).parent / f['file'])
                     for f in sparse['frames']]
    dense_values = [brightness(Path(dense['artifact']).parent / f['file'])
                    for f in report['frames']]
    if max(sparse_values) > 20 or sum(v > 230 for v in dense_values) != 2:
        raise RuntimeError('Measured evidence does not match synthetic fixture')
    sheet = root / 'dense-contact-sheet.jpg'
    run(['ffmpeg', '-v', 'error', '-y', '-i',
         Path(dense['artifact']).parent / 'frame-%04d.jpg', '-vf', 'tile=6x1',
         '-frames:v', '1', sheet])
    result = {'purpose': 'technical_test', 'source': str(source),
              'sparse_frame_count': 8, 'sparse_gray_values': sparse_values,
              'dense': dense, 'dense_gray_values': dense_values,
              'dense_source_times': [f['source_time'] for f in report['frames']],
              'contact_sheet': str(sheet), 'audio': 'fixture_has_no_audio',
              'business_acceptance': 'pending_real_media'}
    write_json(root / 'result.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
