"""Validate plans, media bounds and versioned business evidence before execution."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .core import HOME, Fault, expired, fingerprint, load_json, parse_time, safe_id, write_json
from .library import Library


def _validate_schema(plan):
    try:
        json.dumps(plan, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise Fault("invalid_plan", "Plan must contain only finite JSON values") from exc
    version = plan.get('schema_version') if isinstance(plan, dict) else None
    if type(version) is not int or version not in (1, 2):
        raise Fault('invalid_plan', 'Expected EditPlan version 1 or 2')
    schema = load_json(HOME / f"schemas/edit-plan.v{version}.json")
    errors = list(Draft202012Validator(schema).iter_errors(plan))
    if errors:
        raise Fault("invalid_plan", errors[0].message, details=list(errors[0].absolute_path))
    return version


def validate_shape(plan):
    version = _validate_schema(plan)
    if plan['purpose'] == 'internal_review' and plan['brief']['channel'] != 'internal_review':
        raise Fault('invalid_review_channel', 'Internal review plans require the internal_review channel')
    duration = sum(c["end"] - c["start"] for c in plan["clips"])
    if duration > 600 or any(c["end"] - c["start"] < .5 for c in plan["clips"]):
        raise Fault("invalid_timeline", "Clips must be >=0.5s; total must be <=600s")
    for clip in plan["clips"]:
        frames = (clip["end"] - clip["start"]) * plan["canvas"]["fps"]
        if abs(frames - round(frames)) > .00001:
            raise Fault("unaligned_duration", "Clip duration must be an integer number of output frames")
    _validate_captions(plan, duration)
    for track in plan["audio"]:
        if track["start"] + track["duration"] > duration + .001:
            raise Fault("audio_overflow", "Audio extends beyond video; revise text or timeline")
    if version == 2:
        from .presentation import validate_presentation
        validate_presentation(plan, duration)
    return duration


def _validate_captions(plan, duration):
    previous = 0
    for cue in plan["subtitles"]:
        if not previous <= cue["start"] < cue["end"] <= duration + .001:
            raise Fault("invalid_subtitles", "Cues must not overlap or exceed timeline")
        previous = cue["end"]
        lines = cue["text"].splitlines()
        widths = [sum(.6 if ord(c) < 128 else 1 for c in line) for line in lines]
        if len(lines) > 2 or max(widths, default=0) * plan["style"]["font_size"] > plan["canvas"]["width"] * .8:
            raise Fault("caption_overflow", "Split or shorten captions; text is never truncated")


def _validate_fact_item(item, group, key):
    required = ["sku", "status"]
    required += ["value"] if group == "facts" else ["price", "currency", "gift", "stores", "region", "starts_at", "expires_at", "landing"]
    if not all(k in item for k in required) or item["status"] not in ("pending", "confirmed", "expired"):
        raise Fault("invalid_facts", f"Missing fields or status: {key}")
    if item["status"] == "confirmed" and not (item.get("evidence") and item.get("confirmed_by")):
        raise Fault("unconfirmed_fact", f"Evidence and owner required: {key}")
    for field in ("valid_until", "starts_at", "expires_at"):
        expired(item.get(field))
    if group == "campaigns":
        if not isinstance(item["stores"], list) or not item["landing"]:
            raise Fault("invalid_campaign", key)
        if parse_time(item["starts_at"]) >= parse_time(item["expires_at"]):
            raise Fault("invalid_campaign", "Campaign must end after it starts")


def import_facts(root, data):
    if set(data) != {"facts", "campaigns"} or not all(isinstance(data[x], list) for x in data):
        raise Fault("invalid_facts", "Expected facts and campaigns arrays")
    for group in ("facts", "campaigns"):
        seen = set()
        for item in data[group]:
            key = safe_id(item.get("id"))
            if key in seen:
                raise Fault("duplicate_fact", key)
            seen.add(key)
            _validate_fact_item(item, group, key)
    dest = Path(root) / "facts.json"
    previous = load_json(dest) if dest.exists() else None
    if previous:
        write_json(Path(root) / "fact-history" / f"{fingerprint(previous)}.json", previous)
    write_json(dest, data)
    return {"facts": len(data["facts"]), "campaigns": len(data["campaigns"]), "fingerprint": fingerprint(data)}


def business_snapshot(root, plan):
    data_path = Path(root) / "facts.json"
    data = load_json(data_path) if data_path.exists() else {"facts": [], "campaigns": []}
    facts = {x["id"]: x for x in data["facts"]}
    ids = set(plan["fact_ids"])
    for cue in plan["subtitles"] + plan.get('overlays', []):
        ids.update(cue["fact_ids"])
    selected = []
    for fid in sorted(ids):
        fact = facts.get(fid)
        if not fact or fact.get("status") != "confirmed" or not fact.get("evidence") or not fact.get("confirmed_by"):
            raise Fault("unconfirmed_fact", fid)
        if fact["sku"] not in (plan["brief"]["sku"], "*") or expired(fact.get("valid_until")):
            raise Fault("invalid_fact_scope", fid)
        selected.append(fact)
    return {"facts": selected, "campaign": _campaign_snapshot(data, plan)}


def _campaign_snapshot(data, plan):
    campaign = None
    if plan["brief"]["scenario"] == "promotion" and not plan.get("campaign_id") and plan['purpose'] != 'internal_review':
        raise Fault("missing_campaign", "Promotion requires a confirmed campaign")
    if plan.get("campaign_id"):
        campaign = next((x for x in data["campaigns"] if x["id"] == plan["campaign_id"]), None)
        if not campaign or campaign.get("status") != "confirmed" or not campaign.get("evidence") or not campaign.get("confirmed_by"):
            raise Fault("invalid_campaign", plan["campaign_id"])
        if expired(campaign["expires_at"]) or not expired(campaign["starts_at"]):
            raise Fault("campaign_inactive", campaign["id"])
        if campaign["sku"] != plan["brief"]["sku"]:
            raise Fault("campaign_sku_mismatch", campaign["id"])
        store = plan["brief"].get("store_id")
        if campaign["stores"] and store not in campaign["stores"]:
            raise Fault("campaign_store_mismatch", str(store))
    return campaign


def _asset_eligible(lib, asset, plan):
    if plan['purpose'] != 'internal_review':
        return lib.eligible(asset, plan['brief']['sku'], plan['brief']['channel'])
    meta = asset['metadata']
    rights = meta.get('rights', {})
    return (rights.get('status') == 'confirmed' and not expired(rights.get('expires_at'))
            and 'internal_review' in rights.get('scopes', [])
            and meta.get('source_kind') in ('captured', 'generated')
            and meta.get('packaging') in ('unknown', 'active', 'not_applicable')
            and meta.get('sku') in (None, '*', plan['brief']['sku']))


def validate(root, plan):
    duration = validate_shape(plan)
    snapshot = business_snapshot(root, plan)
    lib = Library(root)
    assets = {}
    for entry in plan["clips"] + plan["audio"]:
        aid = entry["asset_id"]
        asset = lib.get(aid)
        lib.resolve(asset)
        if not _asset_eligible(lib, asset, plan):
            raise Fault("asset_not_eligible", aid)
        if plan["purpose"] == "production" and asset["metadata"]["source_kind"] in ("reference", "technical_fixture"):
            raise Fault("fixture_not_production", aid)
        assets[aid] = {"sha256": asset["sha256"], "metadata": asset["metadata"]}
        is_clip = "end" in entry
        end = entry["end"] if is_clip else entry["source_start"] + entry["duration"]
        if end > asset["technical"]["duration"] + .001:
            raise Fault("source_out_of_range", aid)
        kind = "has_video" if is_clip else "has_audio"
        if not asset["technical"][kind]:
            raise Fault("wrong_media_kind", aid)
    snapshot["assets"] = assets
    return {"duration": duration, "snapshot": snapshot, "signature": fingerprint({"plan": plan, "snapshot": snapshot})}


def revise(plan, patch):
    result = deepcopy(plan)
    if set(patch) - {"style", "clip"}:
        raise Fault("invalid_patch", "Only style or one clip replacement is supported")
    if len(patch) != 1:
        raise Fault("invalid_patch", "Change one factor per revision")
    if "style" in patch:
        result["style"].update(patch["style"])
    else:
        change = patch["clip"]
        index = change.get("index")
        if not isinstance(index, int) or not 0 <= index < len(result["clips"]):
            raise Fault("invalid_patch", "Invalid clip index")
        old = result["clips"][index]
        new = change.get("value", {})
        if old.get('action_window') and not new.get('action_window'):
            raise Fault('invalid_patch', 'Replacement requires an explicitly reviewed action window')
        if abs((old["end"] - old["start"]) - (new.get("end", 0) - new.get("start", 0))) > .001:
            raise Fault("invalid_patch", "Replacement must keep duration to preserve other tracks")
        result["clips"][index] = new
    validate_shape(result)
    return result
