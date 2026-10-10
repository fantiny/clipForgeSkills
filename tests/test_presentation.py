from copy import deepcopy

import pytest

from clipforge_skills.contracts import validate, validate_shape, revise
from clipforge_skills.core import Fault


def overlay(**kwargs):
    return {'id': 'detail', 'start': .2, 'end': 1.8, 'text': '实物细节',
            'fact_ids': [], 'kind': 'emphasis', 'font_size': 24, 'color': '#FFE8A0',
            'box': {'x': .1, 'y': .18, 'width': .8, 'height': .16}, **kwargs}


def test_versions_keep_old_contract_strict(plan):
    plan['overlays'] = [overlay()]
    with pytest.raises(Fault):
        validate_shape(plan)
    plan['schema_version'] = 2
    assert validate_shape(plan) == 4
    for version in [0, 3, True, '2', None]:
        plan['schema_version'] = version
        with pytest.raises(Fault):
            validate_shape(plan)


@pytest.mark.parametrize('change', [
    {'end': 9}, {'end': .1}, {'text': ''}, {'text': '字' * 100},
    {'fade_in': 2}, {'fade_out': -1}, {'color': 'red'}, {'kind': 'script'},
    {'box': {'x': .9, 'y': .2, 'width': .8, 'height': .1}},
    {'box': {'x': .1, 'y': .8, 'width': .8, 'height': .15}},
    {'font_size': float('nan')},
])
def test_overlay_boundaries(plan, change):
    plan.update(schema_version=2, overlays=[overlay(**change)])
    with pytest.raises(Fault):
        validate_shape(plan)


def test_overlay_collisions_and_unique_identity(plan):
    plan.update(schema_version=2, overlays=[overlay(), overlay(id='other')])
    with pytest.raises(Fault, match='overlap'):
        validate_shape(plan)
    plan['overlays'][1].update(start=2, end=3)
    validate_shape(plan)
    plan['overlays'][1]['id'] = 'detail'
    with pytest.raises(Fault):
        validate_shape(plan)


def test_overlay_facts_participate_in_business_validation(library, plan):
    plan.update(schema_version=2, overlays=[overlay(fact_ids=['missing'])])
    with pytest.raises(Fault) as error:
        validate(library.root, plan)
    assert error.value.code == 'unconfirmed_fact'


def test_action_interval_and_replacement_protection(plan):
    plan['schema_version'] = 2
    plan['clips'][0]['action_window'] = {'start': .4, 'end': 1.9, 'evidence': 'viewed source interval'}
    validate_shape(plan)
    replacement = deepcopy(plan['clips'][0])
    replacement.pop('action_window')
    with pytest.raises(Fault):
        revise(plan, {'clip': {'index': 0, 'value': replacement}})
    replacement['action_window'] = {'start': .3, 'end': 1.7, 'evidence': 'new source checked'}
    assert revise(plan, {'clip': {'index': 0, 'value': replacement}})['clips'][0] == replacement
    plan['clips'][0]['action_window']['end'] = 2.1
    with pytest.raises(Fault):
        validate_shape(plan)


def test_fade_and_duck_boundaries(plan):
    plan['schema_version'] = 2
    plan['audio'][0].update(fade_in=2, fade_out=3)
    with pytest.raises(Fault):
        validate_shape(plan)
    plan['audio'][0].update(fade_in=.1, fade_out=.2)
    plan['mix'] = {'ducking': {'reduction_db': -12, 'attack': .1, 'release': .3}}
    validate_shape(plan)
    plan['mix']['ducking']['attack'] = 0
    with pytest.raises(Fault):
        validate_shape(plan)


@pytest.mark.parametrize('version', [1, 2])
def test_both_versions_require_existing_frame_grid(plan, version):
    plan['clips'][0]['end'] = 2.01
    plan['schema_version'] = version
    with pytest.raises(Fault, match='frame'):
        validate_shape(plan)
