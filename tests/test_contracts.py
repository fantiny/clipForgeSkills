"""Reject incomplete business evidence and unsupported timeline semantics."""
from copy import deepcopy
import pytest

from clipforge_skills.core import Fault
from clipforge_skills.contracts import validate_shape, import_facts


@pytest.fixture
def minimal_plan():
    return {"schema_version": 1, "content_id": "sample", "purpose": "technical_test",
            "brief": {"scenario": "service", "sku": "test", "audience": "test", "channel": "test", "cta": None},
            "canvas": {"width": 320, "height": 480, "fps": 30},
            "clips": [{"asset_id": "asset_" + "a" * 24, "start": 0, "end": 2, "role": "body", "audio": "mute"}],
            "subtitles": [], "audio": [], "fact_ids": [], "style": {"font_size": 20, "color": "#FFFFFF"}}


def test_shape_rejects_unknown_and_nan(minimal_plan):
    p = deepcopy(minimal_plan)
    p["clips"][0]["speed"] = 2
    with pytest.raises(Fault):
        validate_shape(p)
    p = deepcopy(minimal_plan)
    p["clips"][0]["end"] = float("nan")
    with pytest.raises(Fault):
        validate_shape(p)


def test_shape_rejects_overlong_audio_and_caption(minimal_plan):
    p = deepcopy(minimal_plan)
    p["subtitles"] = [{"start": 0, "end": 3, "text": "long", "fact_ids": []}]
    with pytest.raises(Fault):
        validate_shape(p)


def test_confirmed_fact_needs_source_and_owner(tmp_path):
    with pytest.raises(Fault):
        import_facts(tmp_path, {"facts": [{"id": "f", "sku": "s", "status": "confirmed", "value": "10"}], "campaigns": []})


def test_confirmed_fact_date_requires_timezone(tmp_path):
    with pytest.raises(Fault):
        import_facts(tmp_path, {"facts": [{"id": "f", "sku": "s", "status": "confirmed", "value": "10", "confirmed_by": "owner", "evidence": "label", "valid_until": "2030-01-01"}], "campaigns": []})
