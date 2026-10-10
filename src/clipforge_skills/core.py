"""Bounded JSON, atomic files, structured errors and single-writer locking."""
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

if os.name == 'nt':
    import msvcrt
else:
    import fcntl

HOME = Path(os.environ.get("CLIPFORGE_HOME", Path(__file__).resolve().parents[2]))
ENGINE_REVISION = "77a7e73e1f898581d325f3070b574ea0894d8a76"


class Fault(Exception):
    def __init__(self, code, message, *, retryable=False, details=None):
        super().__init__(message)
        self.code, self.retryable, self.details = code, retryable, details


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False).encode()).hexdigest()


def load_json(path):
    path = Path(path)
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("JSON exceeds 8 MiB")
        data = json.loads(path.read_text(encoding="utf-8"),
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        return data
    except (OSError, ValueError) as exc:
        raise Fault("invalid_json", f"{path}: {exc}") from exc


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return path


@contextmanager
def locked(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a+b") as stream:
        try:
            _file_lock(stream, True)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            raise Fault("busy", "busy: another process is writing this library", retryable=True) from exc
        try:
            yield
        finally:
            _file_lock(stream, False)


def _file_lock(stream, acquire):
    if os.name == 'nt':
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB if acquire else fcntl.LOCK_UN)


def process_env():
    return {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}


def decode_output(value):
    # Decode on the calling thread: Windows subprocess text reader threads can
    # lose UnicodeDecodeError instead of propagating it from communicate().
    return value.decode('utf-8') if isinstance(value, bytes) else value


def run(args, *, cwd=None, timeout=120):
    try:
        result = subprocess.run([str(x) for x in args], cwd=cwd, timeout=timeout,
                                capture_output=True, env=process_env())
        stdout, stderr = decode_output(result.stdout), decode_output(result.stderr)
    except UnicodeError as exc:
        raise Fault('tool_encoding', f'{args[0]} returned non-UTF-8 output') from exc
    except FileNotFoundError as exc:
        raise Fault("tool_missing", str(args[0])) from exc
    except subprocess.TimeoutExpired as exc:
        raise Fault("tool_timeout", f"{args[0]} timed out", retryable=True) from exc
    if result.returncode:
        raise Fault("tool_failed", f"{args[0]} exited {result.returncode}",
                    details=stderr[-4000:])
    return stdout


def parse_time(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("timezone is required")
        return dt
    except (ValueError, TypeError, AttributeError) as exc:
        raise Fault("invalid_date", f"Invalid timestamp: {value}") from exc


def expired(value):
    return bool(value) and parse_time(value) <= datetime.now(timezone.utc)


def safe_id(value):
    import re
    import ntpath
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,100}", value) or ntpath.isreserved(value):
        raise Fault("invalid_id", "IDs must be 1-101 ASCII letters, digits, _ or -")
    return value
