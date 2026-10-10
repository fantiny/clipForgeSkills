"""Review and delivery are bound to actual files and current business evidence."""
from pathlib import Path
import shutil
import os
import tempfile

from .contracts import validate
from .core import Fault, digest, fingerprint, load_json, now, safe_id, write_json
from .render import file_cache_valid


def current(root, revision):
    work = Path(root) / "runs" / safe_id(revision)
    manifest = load_json(work / "manifest.json")
    if manifest["state"] == "failed" or not manifest.get("files") or not file_cache_valid(work, manifest["files"]):
        raise Fault("stale_output", "Rendered files are missing, changed or failed")
    plan = load_json(work / "plan.json")
    validated = validate(root, plan)
    if validated["signature"] != manifest["input_signature"]:
        raise Fault("stale_evidence", "Facts or asset metadata changed; render and review a new revision")
    return work, manifest, plan


def review(root, revision, decision):
    work, manifest, _ = current(root, revision)
    if not isinstance(decision.get("reviewer"), str) or not decision["reviewer"].strip():
        raise Fault("invalid_review", "reviewer is required")
    if decision.get("decision") not in ("approved", "rejected") or not isinstance(decision.get("issues"), list):
        raise Fault("invalid_review", "decision and issues are required")
    if decision["decision"] == "approved" and (decision.get("watched") is not True or decision.get("listened") is not True or decision["issues"]):
        raise Fault("incomplete_review", "Approval requires actual visual/audio review and no unresolved issues")
    record = {"revision": revision, "input_signature": manifest["input_signature"], "files": manifest["files"],
              "review": decision, "at": now()}
    write_json(work / "reviews" / f"{fingerprint(record)}.json", record)
    write_json(work / "review.json", record)
    manifest["state"] = "reviewed" if decision["decision"] == "approved" else "changes_requested"
    write_json(work / "manifest.json", manifest)
    return {"revision": revision, "state": manifest["state"]}


def deliver(root, revision):
    root = Path(root)
    work, manifest, plan = current(root, revision)
    if plan['purpose'] == 'internal_review':
        raise Fault('internal_review_not_deliverable', 'Internal drafts require a new production plan and review before delivery')
    if manifest["mode"] != "final":
        raise Fault("preview_not_deliverable", "Render final output before delivery")
    review_path = work / "review.json"
    if not review_path.exists():
        raise Fault("review_required", revision)
    approval = load_json(review_path)
    if approval["review"]["decision"] != "approved" or approval["input_signature"] != manifest["input_signature"] or approval["files"] != manifest["files"]:
        raise Fault("review_required", "Review does not approve these exact files")
    dest = root / "deliveries" / revision
    if dest.exists():
        old = load_json(dest / "delivery.json")
        if not file_cache_valid(dest, old["files"]) or old.get("review_hash") != fingerprint(approval):
            raise Fault("delivery_changed", "Existing delivery or approval changed; retain it and create a new revision")
        record_usage(root, revision, plan, manifest, old["state"])
        return {"state": old["state"], "directory": str(dest), "idempotent": True}
    dest.parent.mkdir(parents=True, exist_ok=True)
    state = "test_delivered" if plan["purpose"] == "technical_test" else "delivered"
    with tempfile.TemporaryDirectory(prefix=".delivery-", dir=dest.parent) as temporary:
        staging = Path(temporary)
        for name in manifest["files"]:
            shutil.copy2(work / name, staging / name)
        shutil.copy2(review_path, staging / "review.json")
        write_json(staging / "sources.json", manifest["snapshot"])
        write_json(staging / "copy.json", {"title": plan.get("title", ""), "description": plan.get("description", ""), "purpose": plan["purpose"]})
        files = {p.name: digest(p) for p in staging.iterdir() if p.is_file()}
        write_json(staging / "delivery.json", {"revision": revision, "state": state, "purpose": plan["purpose"],
                                              "content_id": plan["content_id"], "files": files, "review_hash": fingerprint(approval),
                                              "created_at": now(), "cost": manifest["cost"]})
        os.rename(staging, dest)
    record_usage(root, revision, plan, manifest, state)
    return {"state": state, "directory": str(dest), "idempotent": False}


def record_usage(root, revision, plan, manifest, state):
    """Reconcile event/state even after a crash following atomic package creation."""
    usage_path = root / "usage.json"
    usage = load_json(usage_path) if usage_path.exists() else {"events": []}
    if not any(e["delivery_id"] == revision for e in usage["events"]):
        usage["events"].append({"delivery_id": revision, "content_id": plan["content_id"],
                                "master_id": plan.get("master_id", plan["content_id"]),
                                "variant_id": plan.get("variant_id"), "kind": state,
                                "assets": sorted(manifest["snapshot"]["assets"]), "at": now()})
        write_json(usage_path, usage)
    manifest["state"] = state
    write_json(root / "runs" / revision / "manifest.json", manifest)


def status(root, revision=None):
    root = Path(root)
    paths = [root / "runs" / safe_id(revision) / "manifest.json"] if revision else sorted((root / "runs").glob("*/manifest.json"))[-20:]
    results = []
    for path in paths:
        item = load_json(path)
        try:
            current(root, item["revision"])
            valid, reason = True, None
        except Fault as exc:
            valid, reason = False, exc.code
        results.append({"revision": item["revision"], "recorded_state": item["state"], "current_valid": valid,
                        "blocking_reason": reason, "purpose": item["purpose"], "cost": item.get("cost"), "cache": item.get("cache")})
    return {"runs": results}
