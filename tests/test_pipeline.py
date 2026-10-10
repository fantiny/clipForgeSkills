from copy import deepcopy
import json
from pathlib import Path
import pytest

from clipforge_skills.core import Fault, load_json
from clipforge_skills.contracts import revise, validate
from clipforge_skills.delivery import deliver, review, status
from clipforge_skills.render import render


def test_real_renderer_cache_revision_and_delivery(library, plan):
    root = library.root
    first = render(root, plan, "final")
    assert first["cache"]["clips_rendered"] == 2
    assert Path(first["video"]).stat().st_size > 1000
    assert render(root, plan, "final")["cache_hit"]
    modified = revise(plan, {"style": {"color": "#FFFF00"}})
    second = render(root, modified, "final")
    assert second["revision"] != first["revision"]
    assert second["cache"] == {"clips_reused": 2, "clips_rendered": 0}
    with pytest.raises(Fault, match="final|test-story"):
        deliver(root, second["revision"])
    review(root, second["revision"], {"reviewer": "automated-test-contract-only", "decision": "approved",
                                    "watched": True, "listened": True, "notes": "Simulated review record for contract validation", "issues": []})
    output = deliver(root, second["revision"])
    assert output["state"] == "test_delivered"
    assert deliver(root, second["revision"])["idempotent"]
    assert len(load_json(root / "usage.json")["events"]) == 1
    aid = plan["clips"][0]["asset_id"]
    library.annotate(aid, {"metadata": {"packaging": "obsolete"}})
    with pytest.raises(Fault):
        deliver(root, second["revision"])
    assert not status(root, second["revision"])["runs"][0]["current_valid"]


def test_production_rejects_fixture_and_missing_media(library, plan):
    plan["purpose"] = "production"
    with pytest.raises(Fault, match="asset_"):
        validate(library.root, plan)
    plan["purpose"] = "technical_test"
    plan["clips"][0]["end"] = 100
    with pytest.raises(Fault):
        validate(library.root, plan)


def test_patch_cannot_change_locked_middle(library, plan):
    old = deepcopy(plan)
    result = revise(plan, {"style": {"color": "#F2703A"}})
    assert result["clips"] == old["clips"] and result["audio"] == old["audio"]
    with pytest.raises(Fault):
        revise(plan, {"clips": []})
    with pytest.raises(Fault):
        revise(plan, {"clip": {"index": 0, "value": {**plan["clips"][0], "end": 1}}})
