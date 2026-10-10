#!/usr/bin/env python3
"""Process boundary for the pinned existing vidmake compose stage."""
import contextlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def frame_limited_runner(original, frames):
    """Constrain the pinned engine's one-slot video encode, never its probes."""
    def execute(command, **kwargs):
        if command[0] == 'ffmpeg' and '-c:v' in command and '-r' in command:
            command = [*command[:-1], '-frames:v', str(frames), command[-1]]
        return original(command, **kwargs)
    return execute


def portable_concat(clips, dest):
    """Keep drive letters, Unicode and quotes out of FFmpeg's concat grammar."""
    dest = Path(dest).resolve()
    pending = dest.with_name(dest.stem + '.pending' + dest.suffix)
    with tempfile.TemporaryDirectory(prefix='concat-', dir=dest.parent) as scratch:
        scratch = Path(scratch)
        names = []
        for i, clip in enumerate(clips):
            clip = Path(clip).resolve()
            if clip.parent == dest.parent and re.fullmatch(r'[A-Za-z0-9_.-]+', clip.name):
                names.append('../' + clip.name)
            else:
                name = f'part-{i:04d}.mp4'
                shutil.copyfile(clip, scratch / name)
                names.append(name)
        (scratch / 'inputs.txt').write_text(''.join(f"file '{name}'\n" for name in names), encoding='utf-8')
        command = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'inputs.txt']
        try:
            result = subprocess.run([*command, '-c', 'copy', str(pending)], cwd=scratch,
                                    capture_output=True, encoding='utf-8', timeout=1800)
            if result.returncode:
                subprocess.run([*command, '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                                '-c:a', 'aac', '-ar', '44100', '-ac', '2', str(pending)],
                               cwd=scratch, capture_output=True, encoding='utf-8', timeout=1800, check=True)
            os.replace(pending, dest)
        finally:
            pending.unlink(missing_ok=True)


def main():
    engine, config_file, run_id = sys.argv[1:]
    sys.path.insert(0, str(Path(engine) / 'vidmake/src'))
    cfg = json.loads(Path(config_file).read_text(encoding='utf-8'))
    scratch = Path(cfg['runs_root']) / 'scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(scratch)
    with contextlib.redirect_stdout(sys.stderr):
        import feedcut_compose
        feedcut_compose._concat = portable_concat
        if cfg.get('clipforge_frame_limit'):
            feedcut_compose.run_subprocess = frame_limited_runner(
                feedcut_compose.run_subprocess, cfg['clipforge_frame_limit'])
        result = feedcut_compose.compose_stage(run_id=run_id, cfg=cfg, allow_missing_media=False,
                                               synthesize_missing=False)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('ok') and result.get('status') not in ('skipped', 'no_media') else 1


if __name__ == '__main__':
    raise SystemExit(main())
