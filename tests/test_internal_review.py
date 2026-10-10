"""Internal real-media drafts keep unknown facts honest and cannot ship."""
from copy import deepcopy

import pytest

from clipforge_skills.captions import write_captions
from clipforge_skills.contracts import validate
from clipforge_skills.core import Fault
from clipforge_skills.delivery import deliver
from clipforge_skills.render import render


def draft(library, plan):
    plan = deepcopy(plan)
    plan['purpose'] = 'internal_review'
    plan['brief'].update(channel='internal_review', scenario='promotion')
    for asset in library.records():
        library.annotate(asset['asset_id'], {'metadata': {
            'source_kind': 'captured', 'sku': None, 'packaging': 'unknown',
            'rights': {'status': 'confirmed', 'scopes': ['internal_review'], 'evidence': 'Test owner grant'}}})
    return plan


def test_draft_preserves_unknown_and_production_stays_strict(library, plan):
    p = draft(library, plan)
    validated = validate(library.root, p)
    assert validated['snapshot']['campaign'] is None
    assert all(a['metadata']['packaging'] == 'unknown' for a in validated['snapshot']['assets'].values())
    p['purpose'] = 'production'
    with pytest.raises(Fault) as exc:
        validate(library.root, p)
    assert exc.value.code == 'missing_campaign'
    p['brief']['scenario'] = 'product'
    with pytest.raises(Fault) as exc:
        validate(library.root, p)
    assert exc.value.code == 'asset_not_eligible'


@pytest.mark.parametrize('change', [
    {'source_kind': 'reference'}, {'source_kind': 'technical_fixture'}, {'sku': 'other'},
    {'packaging': 'obsolete'}, {'rights': {'status': 'unknown'}},
    {'rights': {'status': 'confirmed', 'scopes': ['elsewhere'], 'evidence': 'test'}},
    {'rights': {'status': 'confirmed', 'scopes': ['internal_review'], 'evidence': 'test', 'expires_at': '2000-01-01T00:00:00Z'}},
])
def test_draft_still_checks_sources(library, plan, change):
    p = draft(library, plan)
    library.annotate(p['clips'][0]['asset_id'], {'metadata': change})
    with pytest.raises(Fault):
        validate(library.root, p)


def test_draft_channel_and_explicit_facts_remain_checked(library, plan):
    p = draft(library, plan)
    p['brief']['channel'] = 'public'
    with pytest.raises(Fault):
        validate(library.root, p)
    p['brief']['channel'] = 'internal_review'
    p['fact_ids'] = ['missing']
    with pytest.raises(Fault):
        validate(library.root, p)
    p['fact_ids'] = []
    p['campaign_id'] = 'missing'
    with pytest.raises(Fault):
        validate(library.root, p)


def test_draft_watermark_without_cues_and_no_delivery(library, plan, tmp_path):
    p = draft(library, plan)
    p['subtitles'] = []
    write_captions(p, tmp_path, p['canvas'])
    assert '内部审阅' in (tmp_path / 'captions.ass').read_text(encoding='utf-8')
    output = render(library.root, p, 'final')
    with pytest.raises(Fault) as exc:
        deliver(library.root, output['revision'])
    assert exc.value.code == 'internal_review_not_deliverable'
