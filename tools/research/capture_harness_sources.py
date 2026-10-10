#!/usr/bin/env python3
"""Capture selected immutable reference sources for a reproducible read-only audit."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REVISIONS = {
    'hypit':'7f730abf72fa1e4a543eed8cd1807319d9f18196',
    'openmontage':'9327439db69021ab4b0e2776729bf3b58fdb5a87',
    'dramaclaw':'9822d6fd9ff6d9d2d47d725209b88af75140f676',
    'huashu-art-motion':'57d67608ab458f57d9b153b1a2831b921e22498b',
    'hyperframes':'188475aaf2cc94d05a5a641341cab3020c131f16',
}
SELECTION = {
    'hypit': ['skills/hypit/references/creation/', 'skills/hypit/references/production/review.md',
              'skills/hypit/references/production/builds.md', 'skills/hypit/references/production/prompt-kits.md',
              'skills/hypit/references/playbooks/craft/b-roll.md', 'packages/runtime/src/scheduler.ts'],
    'openmontage': ['skills/meta/reviewer.md', 'skills/meta/video-reference-analyst.md',
                   'skills/meta/checkpoint-protocol.md', 'skills/meta/taste-direction.md',
                   'skills/creative/broll-planning.md', 'skills/creative/storytelling.md',
                   'skills/pipelines/documentary-montage/', 'pipeline_defs/documentary-montage.yaml',
                   'lib/pipeline_loader.py', 'lib/checkpoint.py', 'backlot/state.py', 'tools/tool_registry.py'],
    'dramaclaw': ['src/novelvideo/agents/episode_planner.py', 'src/novelvideo/agents/episode_reviewer.py',
                 'src/novelvideo/agents/episode_fixer.py', 'src/novelvideo/agents/character_reviewer.py',
                 'src/novelvideo/agents/video_prompt_builder.py', 'src/novelvideo/agents/global_video_optimizer.py',
                 'src/novelvideo/verification/episode_reviewer.py', 'src/novelvideo/verification/prompts.py',
                 'src/novelvideo/freezone/skill_registry.py', '.hermes/skills/dramaclaw/playbooks/resume.md',
                 '.hermes/skills/dramaclaw/references/read-behavior.md', 'src/novelvideo/task_state.py'],
    'huashu-art-motion': ['SKILL.md', 'references/01-拆解.md', 'references/02-机制.md',
                         'references/03-一帧先行四条路线.md', 'references/12-口播整片与经验回流.md',
                         'scripts/qa.py', 'references/06-口播驱动的艺术短片.md'],
    'hyperframes': ['skills/hyperframes/SKILL.md', '.agents/skills/motion-doctrine/SKILL.md',
                   '.agents/skills/motion-doctrine/scripts/seam-gate.mjs',
                   'docs/concepts/determinism.mdx', 'docs/prompting/recreating-references.mdx',
                   'docs/prompting/iterating.mdx', 'packages/lint/src/shouldBlockRender.ts',
                   'packages/lint/src/rules/captions.ts', 'packages/cli/src/commands/validate.ts'],
}


def main():
    records = []
    output = ROOT / 'tmp/harness-research/manifest.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    for repo, selectors in SELECTION.items():
        source = ROOT / 'tmp/references' / repo
        def git(*args):
            return subprocess.check_output(['git', '-C', str(source), *args], timeout=40)
        revision = git('rev-parse', REVISIONS[repo]).decode().strip()
        if revision != REVISIONS[repo]:
            raise ValueError(f'Unexpected revision for {repo}')
        names = git('ls-tree', '-rz', '--name-only', revision).decode().split('\0')
        selected = [n for n in names if n and any(n == s or (s.endswith('/') and n.startswith(s)) for s in selectors)]
        for name in selected:
            try:
                content = git('show', f'{revision}:{name}')
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                records.append({'repo':repo, 'commit':revision, 'path':name, 'error':type(exc).__name__})
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2))
                continue
            dest = ROOT / 'tmp/harness-research' / repo / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            records.append({'repo':repo, 'commit':revision, 'path':name,
                            'sha256':hashlib.sha256(content).hexdigest(), 'lines':len(content.splitlines())})
            output.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    output = ROOT / 'tmp/harness-research/manifest.json'
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(json.dumps({'files':len(records), 'manifest':str(output)}))


if __name__ == '__main__':
    main()
