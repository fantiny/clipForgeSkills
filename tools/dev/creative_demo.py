#!/usr/bin/env python3
"""Exercise the public CLI on an existing technical video, never approve it."""
import json
from pathlib import Path
import subprocess
import sys

from clipforge_skills.core import load_json, write_json

ROOT = Path(__file__).resolve().parents[2]


def main():
    technical = ROOT / 'tmp/technical-demo'
    if not (technical / 'result.json').is_file():
        subprocess.run([sys.executable, ROOT / 'tools/dev/smoke.py'], cwd=ROOT, check=True)
    rendered = load_json(technical / 'result.json')
    video = rendered['video']
    work = ROOT / 'tmp/creative-demo'
    work.mkdir(parents=True, exist_ok=True)
    plan_copy = work / 'plan-copy.json'
    write_json(plan_copy, load_json(technical / 'plan.json'))
    state = {
        'schema_version': 1, 'content_id': 'technical-demo', 'purpose': 'technical_test',
        'result_contract': {'audience': '工具验收人员',
                            'viewer_takeaway': '辨认两张色卡，并检查跨镜字幕与旁白是否连续',
                            'viewer_action': None,
                            'success_checks': ['6秒切点前后字幕不提前消失', '旁白完整听取后再判断连续性']},
        'locked_choices': ['此片仅为技术样例，不能当作示例品牌业务成片', '不得伪造完整视听批准'],
        'beats': [
            {'beat_id': 'opening', 'purpose': '标明技术演示范围', 'message': '前6秒第一张色卡',
             'visual_requirement': '标题完整可读，保留技术样例标识', 'audio_intent': '2秒开始的旁白',
             'acceptance': ['查看真实视频确认标题'], 'artifact_ids': ['video']},
            {'beat_id': 'continuity', 'purpose': '检查跨镜关系', 'message': '6秒切换色卡',
             'visual_requirement': '字幕继续显示到9秒，不能随镜头消失', 'audio_intent': '旁白跨镜连续',
             'acceptance': ['查看5.5到6.5秒片段', '实际听取完整混音'], 'artifact_ids': ['video']}],
        'artifacts': [{'artifact_id': 'plan', 'kind': 'plan', 'path': str(plan_copy)},
                      {'artifact_id': 'video', 'kind': 'media', 'path': video}],
        'global_artifact_ids': ['plan'],
        'open_issues': [{'issue_id': 'actual-review', 'beat_ids': ['continuity'], 'severity': 'blocking',
                         'observation': '技术运行不证明完整画面和听感已审',
                         'next_check': '打开成片，检查切点并听完整旁白；不能仅凭哈希通过',
                         'artifact_ids': ['video']}],
    }
    input_path = write_json(work / 'creative.json', state)
    data = work / 'data'

    def cli(*args):
        result = subprocess.run([sys.executable, '-X', 'utf8', ROOT / 'tools/clipforge.py', '--data', data, *args],
                                text=True, encoding='utf-8', capture_output=True, check=True)
        return json.loads(result.stdout)['result']

    # The demo has a fixed input. Repeat runs reconcile only its own prior head.
    head_path = data / 'work/technical-demo/creative/head.json'
    expected = ['--expected', load_json(head_path)['revision']] if head_path.exists() else []
    saved = cli('creative-save', str(input_path), *expected)
    full = cli('creative-context', 'technical-demo')
    selected = cli('creative-context', 'technical-demo', '--beat', 'opening')
    assert len(selected['beats']) == 1 and selected['open_issues'][0]['issue_id'] == 'actual-review'
    assert selected['locked_choices'] == full['locked_choices']
    changed = load_json(plan_copy)
    changed['title'] = 'Technical mutation to prove dependency invalidation'
    write_json(plan_copy, changed)
    stale = cli('creative-context', 'technical-demo', '--beat', 'opening')
    assert stale['stale_artifacts'] == [{'artifact_id': 'plan', 'kind': 'plan', 'status': 'changed'}]
    report = {'purpose': 'technical_test', 'saved': saved, 'video': video,
              'full_context_chars': len(json.dumps(full, ensure_ascii=False)),
              'selected_context_chars': len(json.dumps(selected, ensure_ascii=False)),
              'selected': selected, 'after_plan_change': stale,
              'semantic_quality': 'not_evaluated', 'host_tokens': None}
    write_json(work / 'result.json', report)
    print(json.dumps({'result': str(work / 'result.json'), 'revision': saved['revision'],
                      'full_chars': report['full_context_chars'],
                      'selected_chars': report['selected_context_chars'],
                      'stale_artifacts': stale['stale_artifacts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
