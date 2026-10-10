"""Result-first context must retain constraints and expose stale evidence."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from clipforge_skills import creative
from clipforge_skills.core import Fault, load_json, write_json


@pytest.fixture
def state_input(tmp_path):
    (tmp_path / 'plan.json').write_text('{"technical_fixture":true}')
    (tmp_path / 'evidence.json').write_text('{"observation":"technical fixture"}')
    body = {'schema_version': 1, 'content_id': 'result-demo', 'purpose': 'technical_test',
            'result_contract': {'audience': '测试人员', 'viewer_takeaway': '辨认两个测试色卡',
                                'viewer_action': None, 'success_checks': ['主体和字幕互不遮挡']},
            'locked_choices': ['不要变更目标画幅'],
            'beats': [{'beat_id': name, 'purpose': '展示', 'message': name,
                       'visual_requirement': '看清指定色卡', 'audio_intent': '原声连续',
                       'acceptance': ['字幕完整可读'], 'artifact_ids': ['evidence']}
                      for name in ('opening', 'body')],
            'artifacts': [{'artifact_id': 'plan', 'kind': 'plan', 'path': 'plan.json'},
                          {'artifact_id': 'evidence', 'kind': 'evidence', 'path': 'evidence.json'}],
            'global_artifact_ids': ['plan'],
            'open_issues': [{'issue_id': 'hard', 'beat_ids': ['body'], 'severity': 'blocking',
                             'observation': '第二段尚未验证', 'next_check': '实际查看第二段',
                             'artifact_ids': ['evidence']},
                            {'issue_id': 'soft', 'beat_ids': ['body'], 'severity': 'improvement',
                             'observation': '考虑收短尾帧', 'next_check': '比较两个版本',
                             'artifact_ids': []}]}
    path = tmp_path / 'creative.json'
    write_json(path, body)
    return path


def test_save_context_and_history(tmp_path, state_input):
    root = tmp_path / 'data'
    first = creative.save(root, state_input)
    assert not first['idempotent']
    assert creative.save(root, state_input)['idempotent']
    ctx = creative.context(root, 'result-demo', beats=['opening'])
    assert len(ctx['beats']) == 1 and ctx['locked_choices'] == ['不要变更目标画幅']
    assert [i['issue_id'] for i in ctx['open_issues']] == ['hard']
    assert ctx['needs_recheck'] and ctx['approval'] == 'not_granted'
    assert all(a['status'] == 'current' for a in ctx['artifacts'])
    assert all(Path(a['path']).is_absolute() for a in ctx['artifacts'])
    assert 'technical_fixture' not in json.dumps(ctx)  # file contents are not embedded
    state = load_json(state_input)
    state['beats'][0]['message'] = 'new opening'
    write_json(state_input, state)
    with pytest.raises(Fault, match='expected'):
        creative.save(root, state_input)
    second = creative.save(root, state_input, expected=first['revision'])
    assert first['revision'] != second['revision']
    with pytest.raises(Fault):
        creative.save(root, state_input, expected='creative_' + '0' * 24)
    old = creative.context(root, 'result-demo', revision=first['revision'])
    assert not old['is_head'] and old['beats'][0]['message'] == 'opening'
    assert creative.context(root, 'result-demo')['beats'][0]['message'] == 'new opening'


@pytest.mark.parametrize('change', ['empty', 'long', 'duplicate', 'reference', 'beat_reference', 'path', 'unknown'])
def test_bad_inputs(tmp_path, state_input, change):
    state = load_json(state_input)
    if change == 'empty': state['result_contract']['viewer_takeaway'] = '  '
    if change == 'long': state['beats'][0]['message'] = 'x' * 2001
    if change == 'duplicate': state['beats'].append(deepcopy(state['beats'][0]))
    if change == 'reference': state['beats'][0]['artifact_ids'] = ['unknown']
    if change == 'beat_reference': state['open_issues'][0]['beat_ids'] = ['unknown']
    if change == 'path': state['content_id'] = '../escape'
    if change == 'unknown': state['approved'] = True
    write_json(state_input, state)
    with pytest.raises(Fault): creative.save(tmp_path / 'data', state_input)
    assert not list((tmp_path / 'data').glob('work/*/creative/head.json'))


def test_missing_or_large_input(tmp_path, state_input):
    (tmp_path / 'evidence.json').unlink()
    with pytest.raises(Fault): creative.save(tmp_path / 'data', state_input)
    state_input.write_text(' ' * (128 * 1024 + 1))
    with pytest.raises(Fault): creative.save(tmp_path / 'data', state_input)


def test_stale_files_cannot_hide_behind_selected_beat(tmp_path, state_input):
    root = tmp_path / 'data'
    state = load_json(state_input)
    state['open_issues'] = []
    state['beats'][0]['artifact_ids'] = []
    write_json(state_input, state)
    saved = creative.save(root, state_input)
    assert not creative.context(root, 'result-demo')['needs_recheck']
    (tmp_path / 'evidence.json').write_text('changed')
    (tmp_path / 'plan.json').unlink()
    ctx = creative.context(root, 'result-demo', beats=['opening'])
    assert ctx['needs_recheck']
    assert {a['status'] for a in ctx['stale_artifacts']} == {'missing', 'changed'}
    assert ctx['revision'] == saved['revision']


def test_budget_does_not_truncate_constraints(tmp_path, state_input):
    state = load_json(state_input)
    state['locked_choices'] = ['不可丢弃' + 'x' * 300] * 8
    write_json(state_input, state)
    creative.save(tmp_path / 'data', state_input)
    with pytest.raises(Fault) as exc:
        creative.context(tmp_path / 'data', 'result-demo', max_chars=2000)
    assert exc.value.code == 'context_budget_exceeded'
    assert exc.value.details['required_chars'] > 2000
    for value in (None, True, 1999, 40001):
        with pytest.raises(Fault): creative.context(tmp_path / 'data', 'result-demo', max_chars=value)


def test_corrupt_snapshot_and_unknown_ids(tmp_path, state_input):
    root = tmp_path / 'data'
    saved = creative.save(root, state_input)
    with pytest.raises(Fault): creative.context(root, 'result-demo', beats=['absent'])
    with pytest.raises(Fault): creative.context(root, '../outside')
    with pytest.raises(Fault): creative.context(root, 'result-demo', revision='../outside')
    snap = load_json(saved['artifact'])
    snap['body']['locked_choices'] = []
    write_json(saved['artifact'], snap)
    with pytest.raises(Fault): creative.context(root, 'result-demo')
    with pytest.raises(Fault): creative.save(root, state_input, expected=saved['revision'])


def test_cli_uses_actual_contract(tmp_path, state_input, capsys):
    from clipforge_skills.cli import main
    prefix = ['--data', str(tmp_path / 'data')]
    assert main(prefix + ['creative-save', str(state_input)]) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved['ok']
    assert main(prefix + ['creative-context', 'result-demo', '--beat', 'opening']) == 0
    ctx = json.loads(capsys.readouterr().out)['result']
    assert ctx['revision'] == saved['result']['revision']
    assert len(ctx['beats']) == 1


def test_interrupted_head_publish_recovers_snapshot(tmp_path, state_input, monkeypatch):
    root = tmp_path / 'data'
    original = creative.write_json
    def fail_head(path, data):
        if Path(path).name == 'head.json':
            raise OSError('injected head publication failure')
        return original(path, data)
    monkeypatch.setattr(creative, 'write_json', fail_head)
    with pytest.raises(OSError): creative.save(root, state_input)
    snapshots = list(root.glob('work/*/creative/revisions/*.json'))
    assert len(snapshots) == 1
    before = snapshots[0].read_bytes()
    with pytest.raises(Fault): creative.context(root, 'result-demo')
    monkeypatch.setattr(creative, 'write_json', original)
    creative.save(root, state_input)
    assert snapshots[0].read_bytes() == before
    assert creative.context(root, 'result-demo')['is_head']


def test_budget_with_many_beats_keeps_global_blocker(tmp_path, state_input):
    state = load_json(state_input)
    for i in range(30):
        beat = deepcopy(state['beats'][0])
        beat.update(beat_id=f'extra-{i}', message='synthetic context filler ' * 30)
        state['beats'].append(beat)
    write_json(state_input, state)
    creative.save(tmp_path / 'data', state_input)
    with pytest.raises(Fault) as exc:
        creative.context(tmp_path / 'data', 'result-demo', max_chars=5000)
    assert exc.value.code == 'context_budget_exceeded'
    ctx = creative.context(tmp_path / 'data', 'result-demo', beats=['opening'], max_chars=5000)
    assert ctx['omitted_beats'] == 31
    assert ctx['open_issues'][0]['issue_id'] == 'hard'
    assert ctx['locked_choices'] == state['locked_choices']
