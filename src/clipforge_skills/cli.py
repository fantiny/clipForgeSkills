"""One JSON response per command; durable structured diagnostics per trace."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
import time
import uuid

from . import audio, contracts, creative, delivery, evidence, importers, media, render
from .core import HOME, Fault, load_json, locked, now, write_json
from .library import Library


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Fault("usage", message)


def parser():
    p = Parser(prog="clipforge")
    p.add_argument("--data", type=Path, default=Path(os.environ.get("CLIPFORGE_DATA", HOME / ".clipforge")))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    x = sub.add_parser("ingest")
    x.add_argument("directory", type=Path)
    x.add_argument("--metadata", type=Path)
    x = sub.add_parser("search")
    x.add_argument("query", nargs="?", default="")
    x.add_argument("--sku")
    x.add_argument("--channel")
    x.add_argument("--limit", type=int, default=5)
    x.add_argument("--include-unconfirmed", action="store_true")
    x = sub.add_parser("annotate")
    x.add_argument("asset_id")
    x.add_argument("input", type=Path)
    x = sub.add_parser("import-docs")
    x.add_argument("paths", type=Path, nargs="+")
    x = sub.add_parser("import-hub")
    x.add_argument("index", type=Path)
    x.add_argument("--media-root", type=Path, required=True)
    x = sub.add_parser("reference")
    x.add_argument("video", type=Path)
    x.add_argument("--frames", type=int, default=8)
    x = sub.add_parser("evidence")
    x.add_argument("video", type=Path)
    x.add_argument("--start", type=float, required=True)
    x.add_argument("--end", type=float, required=True)
    density = x.add_mutually_exclusive_group()
    density.add_argument("--fps", type=float, default=4)
    density.add_argument("--every-frame", action="store_true")
    x.add_argument("--size", type=int, default=640)
    x = sub.add_parser("creative-save")
    x.add_argument("input", type=Path)
    x.add_argument("--expected")
    x = sub.add_parser("creative-context")
    x.add_argument("content_id")
    x.add_argument("--beat", action="append")
    x.add_argument("--max-chars", type=int, default=12000)
    x.add_argument("--revision")
    for cmd in ("facts", "coverage", "validate"):
        sub.add_parser(cmd).add_argument("input", type=Path)
    x = sub.add_parser("render")
    x.add_argument("input", type=Path)
    x.add_argument("--mode", choices=["preview", "final"], default="preview")
    x = sub.add_parser("revise")
    x.add_argument("input", type=Path)
    x.add_argument("patch", type=Path)
    x.add_argument("output", type=Path)
    x = sub.add_parser("review")
    x.add_argument("revision")
    x.add_argument("input", type=Path)
    sub.add_parser("deliver").add_argument("revision")
    sub.add_parser("status").add_argument("revision", nargs="?")
    x = sub.add_parser("speech")
    x.add_argument("input", type=Path)
    x.add_argument("--voice")
    sub.add_parser("profiles")
    return p


def dispatch(a):
    root = a.data.resolve()
    cmd = a.command
    if cmd == "doctor":
        return media.doctor()
    if cmd == "profiles":
        return {"profiles": [load_json(x) for x in sorted((HOME / "profiles").glob("*.json"))]}
    lib = Library(root)
    handlers = {
        "ingest": lambda: lib.ingest(a.directory, load_json(a.metadata) if a.metadata else None),
        "search": lambda: lib.search(a.query, a.sku, a.channel, a.limit, a.include_unconfirmed),
        "annotate": lambda: lib.annotate(a.asset_id, load_json(a.input)),
        "import-docs": lambda: importers.import_docs(root, a.paths),
        "import-hub": lambda: importers.import_hub(root, a.index, a.media_root),
        "reference": lambda: media.reference(a.video, root / "references", a.frames),
        "evidence": lambda: evidence.extract(a.video, root / "evidence", a.start, a.end,
                                             fps=a.fps, size=a.size, every_frame=a.every_frame),
        "creative-save": lambda: creative.save(root, a.input, expected=a.expected),
        "creative-context": lambda: creative.context(root, a.content_id, beats=a.beat,
                                                     max_chars=a.max_chars, revision=a.revision),
        "facts": lambda: contracts.import_facts(root, load_json(a.input)),
        "coverage": lambda: lib.coverage(load_json(a.input)),
        "validate": lambda: _validate_command(root, a.input),
        "render": lambda: render.render(root, load_json(a.input), a.mode),
        "revise": lambda: _revise_command(root, a),
        "review": lambda: delivery.review(root, a.revision, load_json(a.input)),
        "deliver": lambda: delivery.deliver(root, a.revision),
        "status": lambda: delivery.status(root, a.revision),
        "speech": lambda: audio.speech(root, a.input, a.voice),
    }
    if cmd not in handlers:
        raise Fault("usage", cmd)
    return handlers[cmd]()


def _validate_command(root, path):
    result = contracts.validate(root, load_json(path))
    return {"valid": True, "duration": result["duration"], "signature": result["signature"]}


def _revise_command(root, args):
    if args.output.exists():
        raise Fault("output_exists", "Choose a new revision filename")
    patch = load_json(args.patch)
    result = contracts.revise(load_json(args.input), patch)
    contracts.validate(root, result)
    write_json(args.output, result)
    return {"plan": str(args.output.resolve()), "patch": patch}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    trace = uuid.uuid4().hex
    started = time.monotonic()
    args = None
    try:
        args = parser().parse_args(argv)
        lock = nullcontext() if args.command in ("doctor", "profiles") else locked(args.data)
        with lock:
            result = dispatch(args)
        reply, code = {"ok": True, "result": result}, 0
    except Fault as exc:
        reply = {"ok": False, "error_code": exc.code, "message": str(exc),
                 "retryable": exc.retryable, "details": exc.details}
        code = 2 if exc.code in ("usage", "invalid_json", "invalid_plan") else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        reply, code = {"ok": False, "error_code": "invalid_input", "message": str(exc), "retryable": False}, 2
    except Exception as exc:
        reply, code = {"ok": False, "error_code": "internal_error", "message": str(exc), "retryable": False}, 1
    reply["trace_id"] = trace
    if args:
        event = {"trace_id": trace, "at": now(), "stage": args.command, "ok": reply["ok"],
                 "duration_s": round(time.monotonic() - started, 4), "error_code": reply.get("error_code"),
                 "input_fields": sorted(vars(args)), "external_api_cost": 0, "host_tokens": None}
        try:
            write_json(args.data / "logs" / f"{trace}.json", event)
        except OSError:
            print(json.dumps({"trace_id": trace, "warning": "log_write_failed"}), file=sys.stderr)
    print(json.dumps(reply, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
