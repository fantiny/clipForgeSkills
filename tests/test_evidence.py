"""Temporal evidence must preserve source events and timestamps, not invent frames."""
import json
from pathlib import Path

import pytest

from clipforge_skills import evidence
from clipforge_skills.core import Fault, digest, load_json, run
from clipforge_skills.media import probe


@pytest.mark.parametrize('start,end,fps,size', [
    (-1,1,4,640),(1,1,4,640),(2,1,4,640),(0,11,4,640),
    (float('nan'),1,4,640),(0,float('inf'),4,640),(0,1,0,640),
    (0,1,61,640),(0,1,4,159),(0,1,4,641),(True,1,4,640),
])
def test_request_bounds(tmp_path, media_dir, start,end,fps,size):
    with pytest.raises(Fault) as exc:
        evidence.extract(media_dir/'first.mp4',tmp_path,start,end,fps=fps,size=size)
    assert exc.value.code=='invalid_evidence_request'


def test_actual_pts_audio_and_cache(tmp_path,media_dir):
    source=media_dir/'first.mp4'
    before=digest(source)
    result=evidence.extract(source,tmp_path,.5,1.5,every_frame=True)
    manifest=load_json(result['artifact'])
    assert len(manifest['frames'])==30
    assert manifest['frames'][0]['source_time']==pytest.approx(.5)
    assert manifest['frames'][-1]['source_time']==pytest.approx(44/30)
    assert all(.5<=f['source_time']<1.5 for f in manifest['frames'])
    clip_info=probe(result['clip'])
    assert clip_info['has_audio']
    assert clip_info['duration']==pytest.approx(1,abs=.08)
    assert evidence.extract(source,tmp_path,.5,1.5,every_frame=True)['cache_hit']
    Path(result['clip']).write_bytes(b'broken')
    assert not evidence.extract(source,tmp_path,.5,1.5,every_frame=True)['cache_hit']
    assert digest(source)==before
    assert manifest['visual_review']=='pending'


def test_audio_only_and_range_exhaustion(tmp_path,media_dir):
    with pytest.raises(Fault): evidence.extract(media_dir/'narration.wav',tmp_path,0,1)
    with pytest.raises(Fault): evidence.extract(media_dir/'first.mp4',tmp_path,2,4)


def test_every_frame_budget_is_not_silent_sampling(tmp_path):
    source=tmp_path/'dense.mp4'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=red:s=160x160:r=60:d=3',
         '-c:v','libx264',source])
    with pytest.raises(Fault) as exc:
        evidence.extract(source,tmp_path/'out',0,3,every_frame=True)
    assert exc.value.code=='evidence_budget_exceeded'
    assert not list((tmp_path/'out').glob('*/evidence.json'))


@pytest.fixture
def temporal_source(tmp_path):
    source=tmp_path/'短暂事件 &test.mp4'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:s=160x160:r=30:d=3',
         '-vf',"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='between(n,31,32)'",
         '-c:v','libx264',source])
    return source


def test_dense_evidence_captures_short_event(temporal_source,tmp_path):
    dense=evidence.extract(temporal_source,tmp_path/'out',1,1.2,every_frame=True)
    manifest=load_json(dense['artifact'])
    assert len(manifest['frames'])==6
    levels=[]
    import subprocess
    for frame in manifest['frames']:
        path=Path(dense['artifact']).parent/frame['file']
        pixel=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','scale=1:1',
                                       '-pix_fmt','gray','-f','rawvideo','-'])
        levels.append(pixel[0])
    assert levels[0]<20 and levels[1]>230 and levels[2]>230 and levels[-1]<20
    assert not probe(dense['clip'])['has_audio']
    html=Path(dense['index']).read_text(encoding='utf-8')
    assert ' &test.mp4' not in html and '&amp;test.mp4' in html
    sampled=evidence.extract(temporal_source,tmp_path/'out',1,1.2,fps=4)
    assert sampled['frame_count']==1


def test_vfr_and_nonzero_origin(tmp_path):
    source=tmp_path/'offset.mkv'
    run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=160x160:r=10:d=2',
         '-vf',"select='not(eq(n,3)+eq(n,4))',setpts=PTS+8/TB",
         '-fps_mode','vfr','-c:v','libx264',source])
    raw=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_frames',
                        '-show_entries','frame=best_effort_timestamp_time','-of','json',source]))
    origin=float(json.loads(run(['ffprobe','-v','error','-show_entries','format=start_time',
                                 '-of','json',source]))['format']['start_time'])
    expected=[round(float(f['best_effort_timestamp_time'])-origin,6) for f in raw['frames']]
    expected=[x for x in expected if .2<=x<1]
    result=evidence.extract(source,tmp_path/'out',.2,1,every_frame=True)
    manifest=load_json(result['artifact'])
    assert manifest['clock']['origin_seconds']==pytest.approx(origin)
    assert [f['source_time'] for f in manifest['frames']]==pytest.approx(expected)


def test_manifest_corruption_and_cli_summary(tmp_path,media_dir,capsys):
    from clipforge_skills.cli import main
    from clipforge_skills.core import write_json
    args=['--data',str(tmp_path),'evidence',str(media_dir/'first.mp4'),
          '--start','.5','--end','1','--fps','6','--size','320']
    assert main(args)==0
    output=json.loads(capsys.readouterr().out)
    result=output['result']
    assert result['frame_count']>0 and 'frames' not in result
    record=load_json(result['artifact'])
    record['frames'][0]['source_time']=999
    write_json(result['artifact'],record)
    assert main(args)==0
    assert not json.loads(capsys.readouterr().out)['result']['cache_hit']
    Path(result['artifact']).write_text('{broken')
    assert main(args)==0
    assert not json.loads(capsys.readouterr().out)['result']['cache_hit']
    assert len(list((tmp_path/'logs').glob('*.json')))==3


def test_failure_does_not_publish_success(tmp_path,media_dir,monkeypatch):
    def fail(*args):
        raise Fault('tool_timeout','simulated failure',retryable=True)
    monkeypatch.setattr(evidence,'_clip',fail)
    with pytest.raises(Fault):
        evidence.extract(media_dir/'first.mp4',tmp_path,0,1)
    assert not list(tmp_path.glob('*/evidence.json'))
    assert not list(tmp_path.glob('.evidence-*'))


def test_source_changed_during_extraction(tmp_path,media_dir,monkeypatch):
    source=(media_dir/'first.mp4').resolve()
    original=evidence.digest
    count=0
    def changed(path):
        nonlocal count
        if Path(path)==source:
            count+=1
            if count>1:
                return 'different-source'
        return original(path)
    monkeypatch.setattr(evidence,'digest',changed)
    with pytest.raises(Fault) as error:
        evidence.extract(source,tmp_path,0,1)
    assert error.value.code=='source_changed'
    assert not list(tmp_path.glob('*/evidence.json'))


def test_frame_logging_failure_paths(tmp_path,monkeypatch):
    import subprocess
    for error,code in [(FileNotFoundError(),'tool_missing'),
                       (subprocess.TimeoutExpired('ffmpeg',120),'tool_timeout')]:
        def fail(*args,**kwargs): raise error
        monkeypatch.setattr(evidence.subprocess,'run',fail)
        with pytest.raises(Fault) as exc:
            evidence._frame_log(['ffmpeg'],tmp_path)
        assert exc.value.code==code
    monkeypatch.setattr(evidence.subprocess,'run',lambda *a,**k:
                        subprocess.CompletedProcess('ffmpeg',1,'','specific failure'))
    with pytest.raises(Fault) as exc:
        evidence._frame_log(['ffmpeg'],tmp_path)
    assert exc.value.details=='specific failure'


def test_missing_and_inconsistent_pts_are_not_invented(tmp_path):
    request={'start':0,'end':1}
    with pytest.raises(Fault): evidence._parse_frames('',tmp_path,request)
    with pytest.raises(Fault): evidence._parse_frames('config in time_base: 1/30',tmp_path,request)
    (tmp_path/'frame-0001.jpg').write_bytes(b'test')
    with pytest.raises(Fault):
        evidence._parse_frames('config in time_base: 1/30\nn: 0 pts: 40 pts_time: 1.333',tmp_path,request)
