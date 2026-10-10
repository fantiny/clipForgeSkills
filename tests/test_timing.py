import pytest

from clipforge_skills.core import Fault
from clipforge_skills.timing import allocate_actions


def shot(start=0, end=4, action_start=.3, action_end=2):
    return {'asset_id': 'x', 'start': start, 'end': end,
            'action_window': {'start': action_start, 'end': action_end, 'evidence': 'source frames'}}


def test_action_completion_precedes_extra_hold():
    inputs = [shot(), shot(action_end=.6)]
    result = allocate_actions(inputs, 105)
    assert sum(round((s['end'] - s['start']) * 30) for s in result) == 105
    assert result[0]['end'] >= 2
    assert result[1]['end'] >= .6
    assert inputs[0]['end'] == 4


@pytest.mark.parametrize('ranges,frames,fps', [
    ([], 30, 30), ([shot()], 30, 30), ([shot()], 121, 30),
    ([shot(action_start=-1)], 90, 30), ([shot(action_end=5)], 90, 30),
    ([shot(action_end=.2)], 90, 30), ([shot()], True, 30),
    ([shot()], 90, 0), ([shot()], 90.1, 30),
    ([shot(end=float('nan'))], 90, 30),
])
def test_invalid_or_insufficient_ranges(ranges, frames, fps):
    with pytest.raises(Fault):
        allocate_actions(ranges, frames, fps)


def test_rounds_action_outward_without_exceeding_capacity():
    result = allocate_actions([shot(action_end=1.01)], 31)
    assert result[0]['end'] == pytest.approx(31 / 30)
    result = allocate_actions([shot()], 60, 25)
    assert result[0]['end'] == 2.4
