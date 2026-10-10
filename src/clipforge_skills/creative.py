"""Immutable editorial intent and bounded, evidence-aware recovery context."""
from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from .core import HOME, Fault, digest, fingerprint, load_json, now, safe_id, write_json


def _folder(root, content_id):
    return Path(root).resolve() / 'work' / safe_id(content_id) / 'creative'


def _revision(value):
    if not isinstance(value, str) or not re.fullmatch(r'creative_[a-f0-9]{24}', value):
        raise Fault('invalid_creative_revision', 'Invalid creative revision')
    return value


def _head(folder):
    path = folder / 'head.json'
    return _revision(load_json(path)['revision']) if path.exists() else None


def _unique(items, key):
    ids = [item[key] for item in items]
    if len(ids) != len(set(ids)):
        raise Fault('invalid_creative_state', f'Duplicate {key}')
    return set(ids)


def _refs(actual, known):
    if set(actual) - known:
        raise Fault('invalid_creative_state', 'Unknown reference', details=sorted(set(actual) - known))


def _shape(body):
    schema = load_json(HOME / 'schemas/creative-state.v1.json')
    error = next(Draft202012Validator(schema).iter_errors(body), None)
    if error:
        raise Fault('invalid_creative_state', error.message, details=list(error.absolute_path))
    assets = _unique(body['artifacts'], 'artifact_id')
    beats = _unique(body['beats'], 'beat_id')
    _unique(body['open_issues'], 'issue_id')
    _refs(body['global_artifact_ids'], assets)
    for beat in body['beats']:
        _refs(beat['artifact_ids'], assets)
    for issue in body['open_issues']:
        _refs(issue['artifact_ids'], assets)
        _refs(issue['beat_ids'], beats)


def _pin(body, base):
    body = deepcopy(body)
    for artifact in body['artifacts']:
        path = (base / artifact['path']).resolve()
        if not path.is_file():
            raise Fault('missing_creative_artifact', str(path))
        artifact.update(path=str(path), sha256=digest(path))
    return body


def _read(folder, revision, content_id):
    path = folder / 'revisions' / f'{_revision(revision)}.json'
    record = load_json(path)
    signature = record.pop('signature', None)
    key = 'creative_' + fingerprint({'parent': record.get('parent'), 'body': record.get('body')})[:24]
    valid = (signature == fingerprint(record) and record.get('revision') == revision == key
             and record.get('body', {}).get('content_id') == content_id)
    if not valid:
        raise Fault('corrupt_creative_state', 'Snapshot integrity check failed')
    return record


def save(root, input_path, *, expected=None):
    path = Path(input_path).resolve()
    if path.stat().st_size > 128 * 1024:
        raise Fault('invalid_creative_state', 'Creative input exceeds 128 KiB')
    raw = load_json(path)
    _shape(raw)
    folder = _folder(root, raw['content_id'])
    head = _head(folder)
    previous = _read(folder, head, raw['content_id']) if head else None
    if expected is not None and expected != head:
        raise Fault('creative_conflict', 'expected revision differs from head', details={'head': head})
    body = _pin(raw, path.parent)
    if previous and previous['body'] == body:
        return _saved(folder, head, True)
    if head and expected is None:
        raise Fault('creative_conflict', 'Update requires --expected current revision', details={'head': head})
    revision = 'creative_' + fingerprint({'parent': head, 'body': body})[:24]
    target = folder / 'revisions' / f'{revision}.json'
    if target.exists():
        _read(folder, revision, raw['content_id'])  # interrupted publish: reuse intact snapshot
    else:
        record = {'revision': revision, 'parent': head, 'body': body, 'created_at': now()}
        record['signature'] = fingerprint(record)
        write_json(target, record)
    write_json(folder / 'head.json', {'revision': revision})
    return _saved(folder, revision, False)


def _saved(folder, revision, idempotent):
    return {'revision': revision, 'artifact': str(folder / 'revisions' / f'{revision}.json'),
            'idempotent': idempotent, 'approval': 'not_granted'}


def _artifact_status(artifact):
    result = dict(artifact)
    try:
        current = digest(artifact['path'])
    except OSError:
        current = None
    result['current_sha256'] = current
    result['status'] = 'missing' if current is None else ('current' if current == artifact['sha256'] else 'changed')
    return result


def _select(body, requested):
    known = {beat['beat_id'] for beat in body['beats']}
    chosen = set(requested) if requested else known
    _refs(chosen, known)
    beats = [b for b in body['beats'] if b['beat_id'] in chosen]
    issues = [i for i in body['open_issues'] if i['severity'] == 'blocking'
              or not i['beat_ids'] or set(i['beat_ids']) & chosen]
    ids = set(body['global_artifact_ids'])
    for item in beats + issues:
        ids.update(item['artifact_ids'])
    return beats, issues, ids


def context(root, content_id, *, beats=None, max_chars=12000, revision=None):
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 2000 <= max_chars <= 40000:
        raise Fault('invalid_context_budget', 'max_chars must be an integer from 2000 to 40000')
    folder = _folder(root, content_id)
    head = _head(folder)
    chosen_revision = revision or head
    if not chosen_revision:
        raise Fault('creative_missing', 'No saved creative state for this content')
    record = _read(folder, chosen_revision, content_id)
    body = record['body']
    chosen, issues, relevant = _select(body, beats)
    artifacts = [_artifact_status(a) for a in body['artifacts']]
    stale = [{k: a[k] for k in ('artifact_id', 'kind', 'status')}
             for a in artifacts if a['status'] != 'current']
    result = {'content_id': content_id, 'purpose': body['purpose'], 'revision': chosen_revision,
              'is_head': chosen_revision == head, 'result_contract': body['result_contract'],
              'locked_choices': body['locked_choices'], 'beats': chosen, 'open_issues': issues,
              'artifacts': [a for a in artifacts if a['artifact_id'] in relevant],
              'stale_artifacts': stale,
              'needs_recheck': bool(stale or any(i['severity'] == 'blocking' for i in issues)
                                    or chosen_revision != head),
              'approval': 'not_granted', 'omitted_beats': len(body['beats']) - len(chosen)}
    size = len(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if size > max_chars:
        raise Fault('context_budget_exceeded', 'Select fewer beats or increase max_chars; constraints were not truncated',
                    details={'required_chars': size, 'max_chars': max_chars})
    return result
