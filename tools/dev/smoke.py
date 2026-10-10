#!/usr/bin/env python3
"""Render a reproducible technical demo without recording fictitious approval."""
import argparse
import json
from pathlib import Path
import shutil

from clipforge_skills.audio import speech
from clipforge_skills.core import run, write_json
from clipforge_skills.library import Library
from clipforge_skills.render import render


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('tmp/technical-demo'))
    args = parser.parse_args()
    root = args.out.resolve()
    media = root / 'media'
    media.mkdir(parents=True, exist_ok=True)
    for name, color in [('first', '0x203746'), ('second', '0x41615A')]:
        run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
             f'color=c={color}:s=540x960:r=30:d=6', '-c:v', 'libx264',
             '-pix_fmt', 'yuv420p', media / f'{name}.mp4'])
    text = root / 'narration.txt'
    text.write_text('这是技术样片。字幕和旁白可以跨镜头连续播放。', encoding='utf-8')
    voice = speech(root / 'data', text)
    shutil.copy2(voice['audio'], media / 'narration.wav')
    library = Library(root / 'data')
    library.ingest(media, {'sku':'technical-demo', 'packaging':'not_applicable',
                          'source_kind':'technical_fixture', 'rights':{'status':'confirmed',
                          'scopes':['test'], 'evidence':'Synthetic color cards and local system speech'}})
    assets = {Path(a['locations'][0]['relative_path']).name:a for a in library.records()}
    plan = {'schema_version':1, 'content_id':'technical-demo', 'purpose':'technical_test',
            'brief':{'scenario':'service', 'sku':'technical-demo', 'channel':'test',
                     'audience':'工具验收人员', 'cta':None},
            'canvas':{'width':540,'height':960,'fps':30},
            'clips':[{'asset_id':assets[name+'.mp4']['asset_id'], 'start':0, 'end':6,
                      'role':'technical-card', 'audio':'mute'} for name in ('first','second')],
            'subtitles':[{'start':0,'end':3,'text':'CLIPFORGE\n技术样片','fact_ids':[]},
                         {'start':3,'end':9,'text':'字幕与旁白\n跨镜头连续播放','fact_ids':[]},
                         {'start':9,'end':12,'text':'合成验证完成\n待人工视听审核','fact_ids':[]}],
            'audio':[{'asset_id':assets['narration.wav']['asset_id'],'source_start':0,
                      'start':2,'duration':assets['narration.wav']['technical']['duration'],
                      'gain_db':-3,'role':'narration'}],
            'fact_ids':[], 'style':{'font_size':40,'color':'#FFFFFF'},
            'title':'技术样片：非业务成片'}
    write_json(root / 'plan.json', plan)
    result = render(root / 'data', plan, 'final')
    write_json(root / 'result.json', result)
    run(['ffmpeg','-v','error','-y','-ss','6.5','-i',result['video'],'-frames:v','1', root / 'inspection.jpg'])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
