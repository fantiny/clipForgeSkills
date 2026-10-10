"""Validate boundaries before implementing local storage and media operations."""
import json
from pathlib import Path

import pytest

from clipforge_skills.core import Fault, load_json, write_json, fingerprint, locked


def test_json_rejects_nonfinite_and_nonobject(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"x": NaN}')
    with pytest.raises(Fault):
        load_json(p)
    p.write_text("[]")
    with pytest.raises(Fault):
        load_json(p)


def test_atomic_json_roundtrip(tmp_path):
    p = tmp_path / "含 空格" / "data.json"
    write_json(p, {"x": "中文"})
    assert load_json(p) == {"x": "中文"}
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})


def test_lock_rejects_concurrent_writer(tmp_path):
    with locked(tmp_path):
        with pytest.raises(Fault, match="busy"):
            with locked(tmp_path):
                pass
