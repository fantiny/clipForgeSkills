"""Portable asset manifests are authoritative; SQLite is a rebuildable search index."""
from contextlib import closing
import os
import tempfile
from pathlib import Path
import sqlite3

from .core import Fault, digest, expired, fingerprint, load_json, now, safe_id, write_json
from .media import probe

EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".wav", ".mp3", ".m4a", ".aac", ".flac"}


class Library:
    def __init__(self, root):
        self.root = Path(root).resolve()
        (self.root / "assets").mkdir(parents=True, exist_ok=True)

    def get(self, asset_id):
        return load_json(self.root / "assets" / f"{safe_id(asset_id)}.json")

    def records(self):
        return [load_json(p) for p in sorted((self.root / "assets").glob("*.json"))]

    def resolve(self, asset, verify=True):
        roots = load_json(self.root / "roots.json")
        for loc in asset["locations"]:
            if loc["root_id"] not in roots:
                continue
            path = (Path(roots[loc["root_id"]]) / loc["relative_path"]).resolve()
            if path.is_file() and (not verify or digest(path) == asset["sha256"]):
                return path
        raise Fault("missing_or_changed_media", asset["asset_id"])

    def ingest(self, directory, metadata=None):
        directory = Path(directory).resolve()
        if directory.is_file():
            return self.ingest_file(directory, metadata)
        if not directory.is_dir():
            raise Fault("missing_directory", str(directory))
        paths = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
        if len(paths) > 50000:
            raise Fault("batch_too_large", "Split imports into at most 50000 media files")
        return self._ingest(directory, paths, metadata)

    def ingest_file(self, source, metadata=None):
        source = Path(source).resolve()
        if not source.is_file() or source.suffix.lower() not in EXTENSIONS:
            raise Fault('invalid_media', str(source))
        return self._ingest(source.parent, [source], metadata)

    def _ingest(self, directory, paths, metadata):
        metadata = metadata or {}
        allowed = {"sku", "packaging", "rights", "source_kind"}
        if set(metadata) - allowed:
            raise Fault("invalid_metadata", "Unknown metadata fields")
        self._check_metadata(metadata)
        roots_path = self.root / "roots.json"
        roots = load_json(roots_path) if roots_path.exists() else {}
        root_id = "root_" + fingerprint(str(directory))[:16]
        roots[root_id] = str(directory)
        write_json(roots_path, roots)
        counts = {"new": 0, "existing": 0, "errors": [], "asset_ids": []}
        for path in paths:
            try:
                sha = digest(path)
                aid = "asset_" + sha[:24]
                dest = self.root / "assets" / f"{aid}.json"
                loc = {"root_id": root_id, "relative_path": path.relative_to(directory).as_posix()}
                if dest.exists():
                    asset = load_json(dest)
                    if loc not in asset["locations"]:
                        asset["locations"].append(loc)
                    counts["existing"] += 1
                else:
                    asset = {"schema_version": 1, "asset_id": aid, "sha256": sha,
                             "locations": [loc], "technical": probe(path), "annotations": [],
                             "metadata": {"sku": None, "packaging": "unknown", "source_kind": "captured",
                                          "rights": {"status": "unknown", "scopes": [], "evidence": ""}, **metadata},
                             "created_at": now()}
                    counts["new"] += 1
                write_json(dest, asset)
                counts["asset_ids"].append(aid)
            except Fault as exc:
                counts["errors"].append({"file": str(path), "code": exc.code, "message": str(exc)})
        self.rebuild()
        counts["asset_ids"] = list(dict.fromkeys(counts["asset_ids"]))
        counts["status"] = "partial" if counts["errors"] else "complete"
        return counts

    @staticmethod
    def _check_metadata(data):
        if "packaging" in data and data["packaging"] not in ("active", "unknown", "obsolete", "not_applicable"):
            raise Fault("invalid_metadata", "Invalid packaging state")
        if "source_kind" in data and data["source_kind"] not in ("captured", "generated", "technical_fixture", "reference"):
            raise Fault("invalid_metadata", "Invalid source kind")
        rights = data.get("rights", {})
        if not isinstance(rights, dict) or rights.get("status", "unknown") not in ("confirmed", "unknown", "denied"):
            raise Fault("invalid_rights", "Invalid rights")
        if rights.get("status") == "confirmed" and (not rights.get("evidence") or not rights.get("scopes")):
            raise Fault("invalid_rights", "Confirmed rights require evidence and scopes")
        if not isinstance(rights.get("scopes", []), list):
            raise Fault("invalid_rights", "scopes must be an array")
        expired(rights.get("expires_at"))

    def annotate(self, asset_id, data):
        asset = self.get(asset_id)
        if "metadata" in data:
            self._check_metadata(data["metadata"])
            asset["metadata"].update(data["metadata"])
        for annotation in data.get("annotations", []):
            fields = ("label", "value", "start", "end", "source", "evidence", "version")
            if not all(k in annotation for k in fields) or not annotation["evidence"]:
                raise Fault("invalid_annotation", "Annotation requires label/value/time/source/evidence/version")
            if annotation["source"] not in ("manual", "host", "local_model", "legacy"):
                raise Fault("invalid_annotation", "Invalid annotation source")
            if not 0 <= annotation["start"] < annotation["end"] <= asset["technical"]["duration"] + .01:
                raise Fault("invalid_annotation", "Annotation time is out of range")
            if annotation not in asset["annotations"]:
                asset["annotations"].append(annotation)
        write_json(self.root / "assets" / f"{asset_id}.json", asset)
        self.rebuild()
        return {"asset_id": asset_id, "annotation_count": len(asset["annotations"])}

    def rebuild(self):
        # Build separately so a corrupt derived index cannot damage manifests.
        fd, filename = tempfile.mkstemp(prefix=".index-", suffix=".sqlite", dir=self.root)
        os.close(fd)
        temporary = Path(filename)
        try:
            with closing(sqlite3.connect(temporary)) as db, db:
                db.execute("CREATE TABLE assets(id TEXT PRIMARY KEY, text TEXT NOT NULL)")
                for asset in self.records():
                    text = " ".join(str(a["value"]) for a in asset["annotations"])
                    db.execute("INSERT INTO assets VALUES (?, ?)", (asset["asset_id"], text.casefold()))
            os.replace(temporary, self.root / "index.sqlite")
        finally:
            temporary.unlink(missing_ok=True)

    def _index_rows(self):
        try:
            with closing(sqlite3.connect(self.root / "index.sqlite")) as db:
                return db.execute("SELECT id,text FROM assets ORDER BY id").fetchall()
        except sqlite3.DatabaseError:
            self.rebuild()
            with closing(sqlite3.connect(self.root / "index.sqlite")) as db:
                return db.execute("SELECT id,text FROM assets ORDER BY id").fetchall()

    def eligible(self, asset, sku=None, channel=None):
        meta = asset["metadata"]
        rights = meta.get("rights", {})
        if rights.get("status") != "confirmed" or expired(rights.get("expires_at")):
            return False
        if channel and channel not in rights.get("scopes", []):
            return False
        if meta.get("packaging") not in ("active", "not_applicable"):
            return False
        if sku and meta.get("sku") not in (sku, "*"):
            return False
        return meta.get("source_kind") != "reference"

    def search(self, query="", sku=None, channel=None, limit=5, include_unconfirmed=False, *, required_duration=None):
        if not 1 <= limit <= 50 or len(query) > 500:
            raise Fault("invalid_query", "limit must be 1-50; query at most 500 characters")
        if not (self.root / "index.sqlite").exists():
            self.rebuild()
        rows = self._index_rows()
        results = []
        for aid, text in rows:
            if query and not all(t in text for t in query.casefold().split()):
                continue
            asset = self.get(aid)
            if not include_unconfirmed and not self.eligible(asset, sku, channel):
                continue
            if include_unconfirmed and sku and asset["metadata"].get("sku") not in (sku, "*"):
                continue
            try:
                self.resolve(asset)
            except Fault:
                continue
            candidate = self._candidate(asset, query, required_duration)
            if candidate is None:
                continue
            results.append(candidate)
            if len(results) == limit:
                break
        return {"candidates": results, "limit": limit, "query": query}

    @staticmethod
    def _candidate(asset, query, duration):
        result = {"asset_id": asset["asset_id"], "technical": asset["technical"],
                  "metadata": asset["metadata"], "annotations": asset["annotations"][:20]}
        if duration is None:
            return result
        if not asset["technical"]["has_video"]:
            return None
        terms = query.casefold().split()
        spans = asset["annotations"] if terms else [
            {"start": 0, "end": asset["technical"]["duration"], "value": "", "evidence": "technical_duration_only"}]
        ranges = [{"start": a["start"], "end": a["end"], "evidence": a["evidence"]}
                  for a in spans if a["end"] - a["start"] >= duration
                  and all(t in str(a["value"]).casefold() for t in terms)]
        if not ranges:
            return None
        result["usable_ranges"] = ranges[:20]
        return result

    def coverage(self, request):
        results = []
        for need in request.get("shots", []):
            duration = need.get("duration", .5)
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 0 < duration <= 600:
                raise Fault("invalid_coverage", "Shot duration must be finite and within (0, 600]")
            candidates = self.search(need.get("query", ""), request.get("sku"), request.get("channel"),
                                     required_duration=duration)["candidates"]
            results.append({"need": need, "candidates": candidates, "gap": not candidates})
        return {"shots": results, "missing": sum(x["gap"] for x in results)}
