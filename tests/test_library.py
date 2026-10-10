import pytest
from clipforge_skills.core import Fault, digest, load_json


def test_repeat_import_preserves_sources(library, media_dir):
    before = {p.name: digest(p) for p in media_dir.iterdir()}
    result = library.ingest(media_dir)
    assert result["new"] == 0 and result["existing"] == 3
    assert before == {p.name: digest(p) for p in media_dir.iterdir()}
    assert len(library.records()) == 3


def test_tags_require_evidence_and_filter_rights(library):
    asset = library.records()[0]
    aid = asset["asset_id"]
    with pytest.raises(Fault):
        library.annotate(aid, {"annotations": [{"value": "dog"}]})
    library.annotate(aid, {"annotations": [{"label": "subject", "value": "红色 色块", "start": 0, "end": 1,
                                           "source": "manual", "evidence": "generated signal", "version": 1}]})
    assert len(library.search("红色", "test", "test")["candidates"]) == 1
    assert library.search("红色", "other", "test")["candidates"] == []
    library.annotate(aid, {"metadata": {"packaging": "obsolete"}})
    assert library.search("红色", "test", "test")["candidates"] == []


def test_unknown_rights_and_empty_library(tmp_path, media_dir):
    from clipforge_skills.library import Library
    lib = Library(tmp_path / "empty")
    assert lib.search()["candidates"] == []
    lib.ingest(media_dir)
    assert lib.search()["candidates"] == []
    assert len(lib.search(include_unconfirmed=True)["candidates"]) == 3


def test_coverage_reports_missing_shot(library):
    result = library.coverage({"sku": "test", "channel": "test", "shots": [{"query": "不存在", "duration": 2}]})
    assert result["missing"] == 1


@pytest.mark.parametrize('metadata,code', [
    ({'surprise': 1}, 'invalid_metadata'),
    ({'packaging': 'bad'}, 'invalid_metadata'),
    ({'source_kind': 'bad'}, 'invalid_metadata'),
    ({'rights': {'status': 'bad'}}, 'invalid_rights'),
    ({'rights': {'status': 'confirmed'}}, 'invalid_rights'),
    ({'rights': {'scopes': 'test'}}, 'invalid_rights'),
])
def test_reject_invalid_metadata_before_import(library, media_dir, metadata, code):
    with pytest.raises(Fault) as error:
        library.ingest(media_dir, metadata)
    assert error.value.code == code


def test_location_move_and_missing_search(library, media_dir, tmp_path):
    import shutil
    from clipforge_skills.core import write_json
    moved = tmp_path / 'moved'
    shutil.copytree(media_dir, moved)
    library.ingest(moved)
    roots = load_json(library.root / 'roots.json')
    roots = {k: v for k, v in roots.items() if v == str(moved)}
    write_json(library.root / 'roots.json', roots)
    assert len(library.search()['candidates']) == 3
    for file in moved.iterdir():
        file.unlink()
    assert library.search()['candidates'] == []


def test_bad_media_is_reported_without_losing_good_media(library, tmp_path):
    source = tmp_path / 'bad'
    source.mkdir()
    (source / 'bad.mp4').write_text('not media')
    result = library.ingest(source)
    assert result['status'] == 'partial' and len(result['errors']) == 1
    assert len(library.records()) == 3
    with pytest.raises(Fault, match=re.escape(str(tmp_path / 'absent'))):
        library.ingest(tmp_path / 'absent')


def test_query_limits_and_annotation_ranges(library):
    for query, limit in [('x'*501, 1), ('x', 0), ('x', 51)]:
        with pytest.raises(Fault):
            library.search(query, limit=limit)
    assert library.search(sku='different', include_unconfirmed=True)['candidates'] == []
    assert len(library.search(limit=1)['candidates']) == 1
    aid = library.records()[0]['asset_id']
    annotation = {'label':'subject', 'value':'test', 'start':0, 'end':1,
                  'source':'unsupported', 'evidence':'test', 'version':1}
    with pytest.raises(Fault):
        library.annotate(aid, {'annotations':[annotation]})
    annotation.update(source='manual', end=10000)
    with pytest.raises(Fault):
        library.annotate(aid, {'annotations':[annotation]})


def test_corrupt_derived_index_recovers_from_manifests(library):
    before = {p.name:digest(p) for p in (library.root / 'assets').iterdir()}
    (library.root / 'index.sqlite').write_bytes(b'corrupt sqlite')
    assert len(library.search()['candidates']) == 3
    assert before == {p.name:digest(p) for p in (library.root / 'assets').iterdir()}


def test_coverage_uses_matching_evidence_span_not_whole_file(library):
    aid = next(a['asset_id'] for a in library.records() if a['technical']['has_video'])
    annotation = {'label':'action','value':'pour food','start':0,'end':.5,'source':'manual',
                  'evidence':'synthetic temporal fixture','version':1}
    library.annotate(aid, {'annotations':[annotation]})
    request = {'sku':'test','channel':'test','shots':[{'query':'pour food','duration':2}]}
    assert library.coverage(request)['missing'] == 1
    library.annotate(aid, {'annotations':[{**annotation,'start':.5,'end':3}]})
    result = library.coverage(request)
    assert result['missing'] == 0
    assert result['shots'][0]['candidates'][0]['usable_ranges'] == [
        {'start':.5,'end':3,'evidence':'synthetic temporal fixture'}]


def test_coverage_does_not_join_unrelated_times_or_truncate_before_filter(library):
    from copy import deepcopy
    from clipforge_skills.core import write_json
    base = next(a for a in library.records() if a['technical']['has_video'])
    base['annotations'] = [{'label':'action','value':'pour','start':0,'end':1,
                           'source':'manual','evidence':'test','version':1},
                          {'label':'subject','value':'food','start':2,'end':3,
                           'source':'manual','evidence':'test','version':1}]
    for index in range(7):
        asset = deepcopy(base)
        asset['asset_id'] = f'asset_{index:024x}'
        if index == 6:
            asset['annotations'] = [{**base['annotations'][0], 'value':'pour food','end':3}]
        write_json(library.root / 'assets' / (asset['asset_id']+'.json'), asset)
    library.rebuild()
    result = library.coverage({'shots':[{'query':'pour food','duration':2}]})
    assert [a['asset_id'] for a in result['shots'][0]['candidates']] == ['asset_'+f'{6:024x}']
    assert library.coverage({'shots':[{'duration':2}]})['missing'] == 0


@pytest.mark.parametrize('duration', [0, -1, float('nan'), float('inf'), True, '2', 601])
def test_coverage_invalid_duration(library, duration):
    with pytest.raises(Fault) as error:
        library.coverage({'shots':[{'duration':duration}]})
    assert error.value.code == 'invalid_coverage'
def test_single_file_import_does_not_ingest_siblings_or_create_links(tmp_path, media_dir, monkeypatch):
    from clipforge_skills.library import Library
    from pathlib import Path
    def no_links(*args, **kwargs):
        raise AssertionError('Media registration must not create symlinks')
    monkeypatch.setattr(Path, 'symlink_to', no_links)
    lib = Library(tmp_path / 'one-file')
    source = next(media_dir.glob('*.mp4'))
    result = lib.ingest_file(source)
    assert result['new'] == 1 and len(lib.records()) == 1
    assert lib.resolve(lib.records()[0]) == source.resolve()
import re
