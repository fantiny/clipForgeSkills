"""Reuse upstream composition per clip, then render independent audio/caption tracks."""
from pathlib import Path
import json
import os
import shutil
import sys
import time

from .captions import default_font, write_captions
from .contracts import validate
from .core import ENGINE_REVISION, HOME, Fault, digest, fingerprint, load_json, now, run, write_json
from .library import Library
from .media import engine_root, technical_check, versions
from .mixing import audio_graph, check_loudness, measure_mix


def file_cache_valid(directory, manifest):
    return bool(manifest) and all((directory / name).is_file() and digest(directory / name) == sha
               for name, sha in manifest.items())


def clip_render(root, lib, clip, canvas, tool_versions, exact=False):
    engine = engine_root()
    if not (engine / "REVISION").is_file() or (engine / "REVISION").read_text(encoding='utf-8').strip() != ENGINE_REVISION:
        raise Fault("engine_not_ready", "Run tools/engine/bootstrap.py first")
    asset = lib.get(clip["asset_id"])
    source = lib.resolve(asset)
    frames = round((clip['end'] - clip['start']) * canvas['fps']) if exact else None
    key = fingerprint({"source": asset["sha256"], "start": clip["start"], "end": clip["end"], 'frames': frames,
                       "canvas": canvas, "engine": ENGINE_REVISION, "tools": tool_versions,
                       "adapter": digest(HOME / "tools/engine/run_stage.py"), "renderer": digest(Path(__file__))})
    work = Path(root) / "cache/clips" / key
    report = work / "cache.json"
    if report.exists() and file_cache_valid(work, load_json(report)["files"]):
        return work / "output.mp4", True
    work.mkdir(parents=True, exist_ok=True)
    upstream = work / "engine/runs/clip"
    slot = {"slot_id": "clip", "shot_id": clip["asset_id"], "file_path": str(source),
            "in_time": clip["start"], "out_time": clip["end"], "audio_mix": "mute", "caption_policy": "none"}
    write_json(upstream / "04_edit_plan.json", {"slots": [slot], "audio_strategy": "all_mute_bgm", "av_sync": "prefer_long_clip"})
    cfg = {"asset_hub_root": str(Path(root)), "runs_root": str(upstream.parent),
           "llm": {"enabled": False}, "tts": {"enabled": False}, "bgm": {"enabled": False},
           "creation_modes": {"delivery": {"burn_captions": False, "mix_tts": False,
                                           "aspect_normalize": True, "output_width": canvas["width"],
                                           "output_height": canvas["height"], "output_fps": canvas["fps"],
                                           "caption_conflict": {"strategy": "none"}}}}
    if exact:
        cfg['clipforge_frame_limit'] = frames
    config_path = write_json(work / "config.json", cfg)
    raw = run([sys.executable, '-X', 'utf8', HOME / "tools/engine/run_stage.py", engine, config_path, "clip"], timeout=1800)
    result = json.loads(raw)
    output = upstream / "06_render/output.mp4"
    if not result.get("ok") or result.get("status") in ("no_media", "skipped") or not output.is_file():
        raise Fault("render_failed", "Upstream did not produce a complete real media file", details=result)
    technical_check(output, canvas, clip["end"] - clip["start"])
    if exact:
        measured = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                                   '-show_entries', 'stream=nb_read_frames', '-of', 'json', output]))
        if int(measured['streams'][0]['nb_read_frames']) != frames:
            raise Fault('clip_frame_count', 'Encoded clip differs from the requested frame count')
    shutil.copy2(output, work / "output.mp4")
    write_json(report, {"files": {"output.mp4": digest(work / "output.mp4")}, "engine": ENGINE_REVISION})
    return work / "output.mp4", False


def audio_inputs(lib, plan):
    tracks = list(plan["audio"])
    cursor = 0
    for clip in plan["clips"]:
        duration = clip["end"] - clip["start"]
        asset = lib.get(clip["asset_id"])
        if clip["audio"] == "keep" and asset["technical"]["has_audio"]:
            tracks.append({"asset_id": clip["asset_id"], "start": cursor, "source_start": clip["start"],
                           "duration": duration, "gain_db": 0, "role": "original"})
        cursor += duration
    return tracks


def final_pass(lib, plan, work, duration):
    args = ["ffmpeg", "-v", "error", "-y", "-i", "base.mp4"]
    tracks = audio_inputs(lib, plan)
    for i, track in enumerate(tracks, 1):
        path = lib.resolve(lib.get(track["asset_id"]))
        args += ["-ss", str(track["source_start"]), "-t", str(track["duration"]), "-i", str(path)]
    if tracks:
        mixing = plan.get('mix', {})
        measured = measure_mix(args, tracks, duration, mixing, work) if mixing.get('loudness') else None
        if measured is not None:
            write_json(work / 'loudness-analysis.json', measured)
        args += ["-filter_complex", audio_graph(tracks, duration, mixing, measured),
                 "-map", "0:v:0", "-map", "[audio]", "-c:a", "aac", "-b:a", "192k"]
    else:
        args += ["-map", "0:v:0", "-an"]
    if plan["subtitles"] or plan.get('overlays') or plan['purpose'] == 'internal_review':
        args += ["-vf", "ass=captions.ass"]
    args += ["-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "output.pending.mp4"]
    run(args, cwd=work, timeout=1800)
    os.replace(work / "output.pending.mp4", work / "output.mp4")


def render(root, plan, mode="preview"):
    started = time.monotonic()
    root = Path(root).resolve()
    validated = validate(root, plan)
    if mode not in ("preview", "final"):
        raise Fault("invalid_mode", mode)
    canvas = dict(plan["canvas"])
    if mode == "preview" and max(canvas["width"], canvas["height"]) > 960:
        scale = 960 / max(canvas["width"], canvas["height"])
        canvas.update({k: round(canvas[k] * scale / 2) * 2 for k in ("width", "height")})
    tools = versions()
    tools['caption_font_requested'] = plan['style'].get('font_name', default_font())
    implementation = {p.name: digest(p) for p in Path(__file__).parent.glob("*.py")}
    implementation['engine_adapter'] = digest(HOME / 'tools/engine/run_stage.py')
    revision = plan["content_id"] + "-" + fingerprint({"input": validated["signature"], "mode": mode, "tools": tools, "implementation": implementation})[:12] + "-" + mode
    work = root / "runs" / revision
    manifest_path = work / "manifest.json"
    if manifest_path.exists():
        old = load_json(manifest_path)
        if old.get("state") in ("preview_rendered", "final_rendered", "reviewed", "delivered", "test_delivered") and file_cache_valid(work, old.get("files", {})):
            return {"revision": revision, "state": old["state"], "cache_hit": True, "video": str(work / "output.mp4")}
    work.mkdir(parents=True, exist_ok=True)
    manifest = {"revision": revision, "content_id": plan["content_id"], "mode": mode,
                "state": "planned", "input_signature": validated["signature"], "snapshot": validated["snapshot"],
                "canvas": canvas, "files": {}, "created_at": now(), "purpose": plan["purpose"]}
    write_json(work / "plan.json", plan)
    write_json(manifest_path, manifest)
    try:
        lib = Library(root)
        hits = 0
        parts = []
        for i, clip in enumerate(plan["clips"]):
            output, hit = clip_render(root, lib, clip, canvas, tools, exact=plan['schema_version'] == 2)
            hits += int(hit)
            name = f"part-{i:04}.mp4"
            shutil.copy2(output, work / name)
            parts.append(f"file '{name}'")
        (work / "concat.txt").write_text("\n".join(parts), encoding="utf-8")
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i", "concat.txt",
             "-c", "copy", "base.mp4"], cwd=work, timeout=600)
        write_captions(plan, work, canvas)
        final_pass(lib, plan, work, validated["duration"])
        qa = technical_check(work / "output.mp4", canvas, validated["duration"])
        if audio_inputs(lib, plan) and not qa["metadata"]["has_audio"]:
            raise Fault("qa_failed", "Expected audio stream is absent")
        if plan.get('mix', {}).get('loudness'):
            qa['loudness'] = check_loudness(work / 'output.mp4', plan['mix']['loudness'])
        run(["ffmpeg", "-v", "error", "-y", "-i", work / "output.mp4", "-frames:v", "1", work / "cover.jpg"])
        write_json(work / "qa.json", qa)
        files = ("output.mp4", "captions.srt", "cover.jpg", "qa.json", "plan.json")
        manifest.update({"state": mode + "_rendered", "files": {n: digest(work / n) for n in files},
                         "cost": {"external_api": 0, "host_tokens": None, "wall_seconds": round(time.monotonic() - started, 3)},
                         "cache": {"clips_reused": hits, "clips_rendered": len(plan["clips"]) - hits}})
        write_json(manifest_path, manifest)
        return {"revision": revision, "state": manifest["state"], "cache_hit": False,
                "video": str(work / "output.mp4"), "cache": manifest["cache"], "cost": manifest["cost"]}
    except Exception as exc:
        manifest.update({"state": "failed", "error": str(exc)})
        write_json(manifest_path, manifest)
        raise
