"""Bounded v2 presentation rules; these do not prove editorial semantics."""
from .core import Fault


def check_fades(item, duration):
    if item.get('fade_in', 0) + item.get('fade_out', 0) > duration + 1e-8:
        raise Fault('invalid_fades', 'Fade durations exceed the media interval')


def _overlay(item, canvas, duration):
    if not 0 <= item['start'] < item['end'] <= duration:
        raise Fault('overlay_time', 'Overlay must fit the output timeline')
    check_fades(item, item['end'] - item['start'])
    b = item['box']
    # Reserve the upper review mark and the lower reading-caption area.
    if b['x'] < .05 or b['x'] + b['width'] > .95 or b['y'] < .14 or b['y'] + b['height'] > .72:
        raise Fault('overlay_bounds', 'Overlay box exceeds the reserved safe region')
    lines = item['text'].splitlines()
    width = max((sum(.6 if ord(c) < 128 else 1 for c in line) for line in lines), default=0)
    size = item['font_size']
    if len(lines) > 2 or width * size > b['width'] * canvas['width'] - 16 or len(lines) * size * 1.3 > b['height'] * canvas['height'] - 12:
        raise Fault('overlay_text_overflow', 'Shorten text or enlarge the box; glyph visual review is still required')


def _overlaps(a, b):
    if max(a['start'], b['start']) >= min(a['end'], b['end']):
        return False
    x, y = a['box'], b['box']
    return (max(x['x'], y['x']) < min(x['x'] + x['width'], y['x'] + y['width'])
            and max(x['y'], y['y']) < min(x['y'] + x['height'], y['y'] + y['height']))


def validate_presentation(plan, duration):
    items = plan.get('overlays', [])
    if len({x['id'] for x in items}) != len(items):
        raise Fault('overlay_id', 'Overlay IDs must be unique')
    for i, item in enumerate(items):
        _overlay(item, plan['canvas'], duration)
        if any(_overlaps(item, other) for other in items[:i]):
            raise Fault('overlay_overlap', 'Timed overlay boxes overlap')
    for track in plan['audio']:
        check_fades(track, track['duration'])
    for clip in plan['clips']:
        action = clip.get('action_window')
        if action and not clip['start'] <= action['start'] < action['end'] <= clip['end'] + 1e-8:
            raise Fault('action_truncated', 'Selected source interval truncates the reviewed action')
