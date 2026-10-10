#!/usr/bin/env python3
"""Make a local viewing page and traceable review bundle; never approve delivery."""
import argparse
from html import escape
import json
from pathlib import Path
import subprocess

from clipforge_skills.core import digest, write_json
from clipforge_skills.library import Library


def inspect(folder, library):
    plan = json.loads((folder / 'plan.json').read_text(encoding='utf-8'))
    result = json.loads((folder / 'render-result.json').read_text(encoding='utf-8'))
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        if digest(folder / name) != expected:
            raise ValueError(f'Changed review file: {folder / name}')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(folder / 'output.mp4'),
                    '-vf', r'select=not(mod(n\,30)),scale=180:320,tile=6x3:color=0x182025',
                    '-frames:v', '1', str(folder / 'contact.jpg')], check=True)
    volume = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(folder / 'output.mp4'),
                             '-vn', '-af', 'volumedetect', '-f', 'null', '-'],
                            capture_output=True, text=True, encoding='utf-8', check=True)
    (folder / 'audio-measurement.log').write_text(volume.stderr, encoding='utf-8')
    sources = []
    for aid in sorted({x['asset_id'] for x in plan['clips'] + plan['audio']}):
        record = library.get(aid)
        sources.append({'asset_id': aid, 'sha256': record['sha256'], 'path': str(library.resolve(record)),
                        'metadata': record['metadata'], 'technical': record['technical']})
    write_json(folder / 'sources.json', {'sources': sources, 'originals_modified': False})
    return {'scenario': folder.name, 'revision': result['revision'],
            'duration': sum(x['end'] - x['start'] for x in plan['clips']),
            'files': manifest['files'], 'status': 'internal_review',
            'technical_decode': 'passed', 'audio_listening': 'pending', 'business_approval': 'pending'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    root = args.out.resolve()
    batch = json.loads((root / 'batch.json').read_text(encoding='utf-8'))
    cards, records = [], []
    library = Library('.clipforge')
    for number, scene in enumerate(batch['scenes'], 1):
        sid = scene['scenario']
        record = inspect(root / sid, library)
        records.append(record)
        links = ' · '.join(f'<a href="{sid}/{name}">{label}</a>' for name, label in
                            [('output.mp4', 'MP4'), ('captions.srt', '字幕'), ('plan.json', '剪辑方案'),
                             ('creative-notes.json', '文案与选片'), ('sources.json', '素材来源')])
        gaps = ''.join(f'<li>{escape(g)}</li>' for g in scene['gaps'])
        cards.append(f'''<article id="{sid}"><div class="head"><span>{number:02}</span>
<h2>{escape(scene['title'])}</h2></div><video controls playsinline preload="metadata"
poster="{sid}/cover.jpg" src="{sid}/output.mp4"></video><div class="body">
<p class="spec">{record['duration']:.1f} 秒 · 1080 × 1920 · 30 fps</p>
<p>{escape(scene['goal'])}</p><p class="links">{links}</p>
<details><summary>正式发布前待补</summary><ul>{gaps}</ul></details></div></article>''')
    html = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ClipForge · 视频审阅</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f6f2eb;color:#263b32;font:16px/1.65 system-ui,-apple-system,sans-serif}
header,main,footer{max-width:1320px;margin:auto;padding:36px 28px}header{padding-bottom:16px}
.eyebrow{color:#a4502c;font-size:13px;font-weight:700;letter-spacing:2px}h1{font-size:clamp(28px,4vw,46px);line-height:1.2;margin:12px 0}
.intro{max-width:850px;color:#526259}.notice{background:#e8e6d8;border-left:4px solid #b56d41;padding:14px 18px;border-radius:6px}
main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;padding-top:18px}article{background:#fff;border:1px solid #e4dfd5;border-radius:16px;overflow:hidden;box-shadow:0 8px 22px #223c3208}
.head{display:flex;gap:12px;padding:20px;align-items:center;min-height:98px}.head span{font:24px Georgia;color:#bd6a3d}h2{font-size:18px;line-height:1.5;margin:0}
video{display:block;width:100%;aspect-ratio:9/16;background:#142018;max-height:580px;object-fit:contain}.body{padding:18px 20px 24px}.body p{margin:0 0 14px}.spec{font-size:13px;color:#6c786e}.links{font-size:14px}a{color:#93532e;text-underline-offset:4px}summary{cursor:pointer;font-size:14px}li{font-size:14px;margin:6px 0}footer{padding-top:0;color:#626e66;font-size:14px}
@media(max-width:950px){main{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){main{grid-template-columns:1fr}header,main,footer{padding-left:18px;padding-right:18px}}
</style></head><body><header><div class="eyebrow">CLIPFORGE / LOCAL FOOTAGE STUDIES</div>
<h1>ClipForge · 视频审阅</h1><p class="intro">按本批计划展示内部审阅视频。技术检查、实际视听与业务批准分别记录。</p>
<div class="notice"><strong>内部审阅版 · 不用于直接发布</strong><br>含全程水印。活动、SKU、包装现行状态、门店及产品说明待确认；系统语音听感和完整视听审阅尚待完成。</div></header><main>'''
    html += ''.join(cards) + '''</main><footer>已完成本地解码、尺寸、时间线校验；技术通过不代表业务批准。
原片只读，未调用额外付费 AI 接口。<a href="review-batch.json">批次清单</a> · <a href="README.md">复现与待验说明</a></footer>
<script>document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>document.querySelectorAll('video').forEach(other=>{if(other!==v)other.pause()})))</script></body></html>'''
    (root / 'index.html').write_text(html, encoding='utf-8')
    write_json(root / 'review-batch.json', {'purpose': 'internal_review', 'videos': records,
               'extra_paid_api_calls': 0, 'host_token_cost': 'not_measured', 'publication_approved': False})
    print(json.dumps({'index': str(root / 'index.html'), 'videos': len(records)}))


if __name__ == '__main__':
    main()
