import pytest

from holocontrol.application.services.scroll_controller import ScrollController


@pytest.mark.parametrize('fps', [15, 30, 60])
def test_reversal_without_releasing_gesture_at_different_frame_rates(fps):
    scroll = ScrollController()
    steps = []
    for i in range(4 * fps):
        t = i / fps
        direction = 1 if t < 2 else -1
        step = scroll.update(direction, t)
        if step:
            steps.append((t, step))
    up = [(t, s) for t, s in steps if t < 2]
    down = [(t, s) for t, s in steps if t >= 2]
    assert 4 <= sum(s for _, s in up) <= 5
    assert 4 <= -sum(s for _, s in down) <= 5
    assert all(0 < s < 1 for _, s in up)
    assert all(-1 < s < 0 for _, s in down)
    assert down[0][0] < 2.2
    # Once acquired, every camera frame contributes; no 400 ms wheel pauses.
    assert all(b[0] - a[0] <= 1.01 / fps for a, b in zip(up, up[1:]))
    assert all(b[0] - a[0] <= 1.01 / fps for a, b in zip(down, down[1:]))


def test_threshold_jitter_does_not_starve_scroll():
    scroll = ScrollController()
    for i in range(8):
        scroll.update(.5, i * .05)
    steps = [scroll.update(.34 if i % 2 else .36, i * .05) for i in range(8, 48)]
    assert 4 <= sum(steps) <= 5


def test_single_opposite_sample_does_not_reverse_or_reset_progress():
    scroll = ScrollController()
    steps = [scroll.update(-1 if i == 7 else 1, i * .05) for i in range(30)]
    assert all(step >= 0 for step in steps)
    assert sum(steps) >= 3


def test_neutral_release_and_long_gap_cannot_replay_old_steps():
    scroll = ScrollController()
    for i in range(10):
        scroll.update(1, i * .05)
    assert scroll.update(0, .5) == 0
    assert scroll.update(-1, .55) == 0
    assert scroll.update(-1, 5) == 0
    assert scroll.update(-1, 5.05) == 0
    scroll.reset()
    assert scroll.update(1, 6) == 0
