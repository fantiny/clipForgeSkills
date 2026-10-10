"""Adversarial input and stale approval checks, independent of marketing outcomes."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from clipforge_skills import contracts, delivery, media, render
from clipforge_skills.core import Fault, expired, load_json, parse_time, run, safe_id, write_json


@pytest.mark.parametrize("value", ["../x", "", "a/b", None, "x" * 102])
def test_ids_cannot_escape(value):
    with pytest.raises(Fault):
        safe_id(value)


def test_tool_missing_failed_timeout(monkeypatch):
    with pytest.raises(Fault, match="missing"):
        run(["__clipforge_missing_tool__"])
    with pytest.raises(Fault):
        run([sys.executable, '-c', 'raise SystemExit(1)'])
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("test", 1)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(Fault) as exc:
        run(["test"])
    assert exc.value.retryable


def test_dates_and_json_limit(tmp_path):
    assert expired("2000-01-01T00:00:00Z")
    assert not expired(None)
    with pytest.raises(Fault):
        parse_time("2030-01-01")
    path = tmp_path / "large.json"
    with path.open("wb") as f:
        f.truncate(8 * 1024 * 1024 + 1)
    with pytest.raises(Fault):
        load_json(path)


def fact():
    return {"id": "f1", "sku": "test", "value": "Product value", "status": "confirmed", "evidence": "label",
            "confirmed_by": "operator", "valid_until": "2099-01-01T00:00:00Z"}


def campaign():
    return {"id": "c1", "sku": "test", "status": "confirmed", "evidence": "campaign sheet", "confirmed_by": "owner",
            "price": "9.99", "currency": "CNY", "gift": "none", "stores": ["store1"], "region": "test",
            "starts_at": "2000-01-01T00:00:00Z", "expires_at": "2099-01-01T00:00:00Z", "landing": "test-only"}


def test_fact_version_change_invalidates_signature(library, plan):
    contracts.import_facts(library.root, {"facts": [fact()], "campaigns": []})
    plan["fact_ids"] = ["f1"]
    first = contracts.validate(library.root, plan)
    changed = fact()
    changed["value"] = "New value"
    contracts.import_facts(library.root, {"facts": [changed], "campaigns": []})
    assert first["signature"] != contracts.validate(library.root, plan)["signature"]
    assert len(list((library.root / "fact-history").glob("*.json"))) == 1


@pytest.mark.parametrize("change", [{"status": "pending"}, {"sku": "other"}, {"valid_until": "2000-01-01T00:00:00Z"}])
def test_bad_fact_blocks(library, plan, change):
    contracts.import_facts(library.root, {"facts": [{**fact(), **change}], "campaigns": []})
    plan["subtitles"][0]["fact_ids"] = ["f1"]
    with pytest.raises(Fault):
        contracts.validate(library.root, plan)


@pytest.mark.parametrize("change", [{"sku": "other"}, {"stores": ["elsewhere"]}, {"expires_at": "2001-01-01T00:00:00Z"}, {"starts_at": "2090-01-01T00:00:00Z"}, {"status": "pending"}])
def test_campaign_scope_blocks(library, plan, change):
    contracts.import_facts(library.root, {"facts": [], "campaigns": [{**campaign(), **change}]})
    plan["brief"].update({"scenario": "promotion", "store_id": "store1"})
    plan["campaign_id"] = "c1"
    with pytest.raises(Fault):
        contracts.validate(library.root, plan)


def test_campaign_happy_path_and_missing(library, plan):
    plan["brief"].update({"scenario": "promotion", "store_id": "store1"})
    with pytest.raises(Fault):
        contracts.validate(library.root, plan)
    plan["campaign_id"] = "c1"
    with pytest.raises(Fault):
        contracts.validate(library.root, plan)
    contracts.import_facts(library.root, {"facts": [], "campaigns": [campaign()]})
    assert contracts.validate(library.root, plan)["snapshot"]["campaign"]["id"] == "c1"


@pytest.mark.parametrize("data", [{}, {"facts": "no", "campaigns": []}, {"facts": [fact(), fact()], "campaigns": []},
                                   {"facts": [{"id": "bad", "sku": "s"}], "campaigns": []},
                                   {"facts": [], "campaigns": [{**campaign(), "stores": "wrong"}]},
                                   {"facts": [], "campaigns": [{**campaign(), "starts_at": "2099-02-01T00:00:00Z"}]}])
def test_facts_input_rejected(tmp_path, data):
    with pytest.raises(Fault):
        contracts.import_facts(tmp_path, data)


def test_timeline_bounds_and_wrong_kind(library, plan):
    p = deepcopy(plan)
    p["clips"][0]["end"] = .1
    with pytest.raises(Fault): contracts.validate(library.root, p)
    p = deepcopy(plan)
    p["clips"][0]["end"] = 2.01
    with pytest.raises(Fault): contracts.validate(library.root, p)
    p = deepcopy(plan)
    p["clips"][0]["asset_id"] = plan["audio"][0]["asset_id"]
    with pytest.raises(Fault): contracts.validate(library.root, p)
    p = deepcopy(plan)
    p["subtitles"][0]["text"] = "超长字幕" * 30
    with pytest.raises(Fault): contracts.validate(library.root, p)
    p = deepcopy(plan)
    p["audio"][0]["duration"] = 5
    with pytest.raises(Fault): contracts.validate(library.root, p)


def test_preview_review_stale_and_output_tamper(library, plan):
    result = render.render(library.root, plan, "preview")
    revision = result["revision"]
    with pytest.raises(Fault): delivery.deliver(library.root, revision)
    with pytest.raises(Fault): delivery.review(library.root, revision, {})
    with pytest.raises(Fault): delivery.review(library.root, revision, {"reviewer": "x"})
    with pytest.raises(Fault): delivery.review(library.root, revision, {"reviewer": "x", "decision": "approved", "issues": []})
    delivery.review(library.root, revision, {"reviewer": "x", "decision": "rejected", "issues": ["pending view"]})
    assert delivery.status(library.root, revision)["runs"][0]["recorded_state"] == "changes_requested"
    Path(result["video"]).write_bytes(b"broken")
    with pytest.raises(Fault): delivery.current(library.root, revision)
    assert not delivery.status(library.root, revision)["runs"][0]["current_valid"]
    rerendered = render.render(library.root, plan, "preview")
    assert not rerendered["cache_hit"]


def test_render_failure_never_marks_complete(library, plan, monkeypatch):
    def fail(*a, **kw): raise Fault("failure", "injected renderer failure")
    monkeypatch.setattr(render, "clip_render", fail)
    with pytest.raises(Fault): render.render(library.root, plan)
    manifests = list((library.root / "runs").glob("*/manifest.json"))
    assert load_json(manifests[0])["state"] == "failed"


def test_engine_missing(library, plan, monkeypatch, tmp_path):
    monkeypatch.setattr(render, "engine_root", lambda: tmp_path / "missing")
    with pytest.raises(Fault):
        render.clip_render(library.root, library, plan["clips"][0], plan["canvas"], {})
