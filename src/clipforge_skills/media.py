"""Local media inspection and bounded reference evidence extraction."""
import json
import math
import shutil
from pathlib import Path

from .core import ENGINE_REVISION, HOME, Fault, digest, fingerprint, load_json, run, write_json


def probe(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise Fault("missing_media", str(path))
    raw = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                          "-of", "json", path]))
    streams = raw.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float(raw.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration <= 0 or not (videos or audio):
        raise Fault("invalid_media", f"No finite playable duration: {path}")
    v = videos[0] if videos else {}
    return {"duration": duration, "width": v.get("width"), "height": v.get("height"),
            "fps": v.get("avg_frame_rate"), "has_video": bool(videos),
            "has_audio": bool(audio), "codec": v.get("codec_name")}


def versions():
    return {tool: run([tool, "-version"]).splitlines()[0] for tool in ("ffmpeg", "ffprobe")}


def engine_root():
    import os
    return Path(os.environ.get("CLIPFORGE_ENGINE_ROOT", HOME / ".runtime/upstream")).resolve()


def doctor():
    import platform
    import re
    from .captions import default_font
    root = engine_root()
    revision = (root / "REVISION").read_text(encoding='utf-8').strip() if (root / "REVISION").is_file() else None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "tools": {t: shutil.which(t) for t in ("ffmpeg", "ffprobe", "say", "codex", "claude")},
            "versions": versions(), "engine_root": str(root),
            "engine_revision": revision, "expected_revision": ENGINE_REVISION,
            "engine_ready": revision == ENGINE_REVISION and (root / "vidmake/src/feedcut_compose").is_dir(),
            "render_capabilities": {
                'ass': bool(re.search(r'\bass\s', run(['ffmpeg', '-hide_banner', '-filters']))),
                'libx264': bool(re.search(r'\blibx264\s', run(['ffmpeg', '-hide_banner', '-encoders']))),
                'caption_font_requested': default_font(), 'font_visual_check': 'pending'},
            "optional": {"asr": "not_configured", "vision": "host_evidence_review",
                         "hyperframes": "not_configured", "editor_export": "deferred"}}


def reference(path, out, count=8):
    if not 1 <= count <= 12:
        raise Fault("invalid_count", "Reference extraction accepts 1-12 frames")
    source, out = Path(path).resolve(), Path(out).resolve()
    info = probe(source)
    if not info["has_video"]:
        raise Fault("invalid_media", "Reference must contain video")
    key = fingerprint({"source": digest(source), "count": count, "tools": versions()})
    work = out / key[:24]
    report = work / "reference.json"
    if report.exists():
        cached = load_json(report)
        if all((work / f["file"]).is_file() and digest(work / f["file"]) == f["sha256"]
               for f in cached["frames"]):
            return {"artifact": str(report), "cache_hit": True, "frames": cached["frames"]}
    work.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(count):
        t = info["duration"] * (i + .5) / count
        dest = work / f"frame-{i:02d}.jpg"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.6f}", "-i", source,
             "-frames:v", "1", "-vf", "scale=640:-2", dest])
        frames.append({"time": round(t, 6), "file": dest.name, "sha256": digest(dest)})
    write_json(report, {"schema_version": 1, "source": str(source), "source_sha256": digest(source),
                        "technical": info, "frames": frames, "observations": [], "hypotheses": [],
                        "popularity": None, "note": "Sparse frames do not establish actions or popularity."})
    return {"artifact": str(report), "cache_hit": False, "frames": frames}


def technical_check(path, expected, duration):
    info = probe(path)
    run(["ffmpeg", "-v", "error", "-xerror", "-i", path, "-f", "null", "-"], timeout=600)
    errors = []
    if (info["width"], info["height"]) != (expected["width"], expected["height"]):
        errors.append("canvas_mismatch")
    if abs(info["duration"] - duration) > max(.15, 2 / expected["fps"]):
        errors.append("duration_mismatch")
    from fractions import Fraction
    if abs(float(Fraction(info["fps"])) - expected["fps"]) > .01:
        errors.append("fps_mismatch")
    if errors:
        raise Fault("qa_failed", ", ".join(errors), details=info)
    return {"decode": "passed", "metadata": info, "visual_review": "pending", "audio_review": "pending"}
