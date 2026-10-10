"""Frame allocation that preserves explicitly reviewed source action windows."""
from copy import deepcopy
import math

from .core import Fault


def _bounds(item, fps):
    try:
        start, end = item['start'], item['end']
        action = item['action_window']
        values = (start, end, action['start'], action['end'])
        finite = all(not isinstance(n, bool) and math.isfinite(n) for n in values)
        if not finite or not 0 <= start <= action['start'] < action['end'] <= end or not action['evidence']:
            raise ValueError('invalid action window')
        minimum = max(math.ceil(.5 * fps), math.ceil((action['end'] - start) * fps - 1e-8))
        capacity = math.floor((end - start) * fps + 1e-8)
        if minimum > capacity:
            raise ValueError('no full-frame action coverage')
        return minimum, capacity
    except (KeyError, TypeError, ValueError) as exc:
        raise Fault('invalid_action_window', 'Every range needs a finite, evidenced action inside its source bounds') from exc


def allocate_actions(ranges, frames, fps=30):
    if not ranges or type(frames) is not int or frames <= 0 or fps not in (24, 25, 30, 50, 60):
        raise Fault('invalid_allocation', 'Nonempty ranges, positive integer frames and supported fps required')
    bounds = [_bounds(item, fps) for item in ranges]
    lengths = [b[0] for b in bounds]
    if not sum(lengths) <= frames <= sum(b[1] for b in bounds):
        raise Fault('action_coverage', 'Duration cannot contain all actions or exceeds source capacity; revise the beat')
    remaining = frames - sum(lengths)
    for i, (_, capacity) in enumerate(bounds):
        extra = min(remaining, capacity - lengths[i])
        lengths[i] += extra
        remaining -= extra
    result = deepcopy(ranges)
    for item, length in zip(result, lengths):
        item['end'] = round(item['start'] + length / fps, 9)
    return result
