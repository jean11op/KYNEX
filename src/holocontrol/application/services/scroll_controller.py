"""Continuous wheel fractions with stable activation and immediate neutral stop."""


class ScrollController:
    def __init__(self):
        self.reset()

    def reset(self):
        self._direction = 0
        self._candidate = 0
        self._candidate_since = 0.0
        self._last_time = None
        self._remainder = 0.0

    def update(self, direction: float, now: float) -> float:
        if self._last_time is not None and now <= self._last_time:
            return 0
        if self._last_time is None or now - self._last_time > .25:
            self.reset()
            dt = 0.0
        else:
            dt = min(.1, now - self._last_time)
        self._last_time = now
        # Enter at .35; remain active down to .20. Borderline tracking cannot
        # repeatedly discard progress while the user holds the same direction.
        requested = (1 if direction > 0 else -1) if abs(direction) >= .35 else (
            self._direction if self._direction * direction >= .20 else 0)
        if requested != self._candidate:
            self._candidate = requested
            self._candidate_since = now
        if requested == 0:
            self._direction = 0
            self._remainder = 0.0
            return 0
        if requested != self._direction:
            # Suspend the old direction immediately; confirm the new one before
            # emitting input. A single inverted sample cannot reverse the wheel.
            if now - self._candidate_since < .08:
                return 0
            self._direction = requested
            self._remainder = 0.0
        # Windows accepts fractions of a 120-unit notch. Send small deltas each
        # frame instead of waiting 400 ms for a complete notch. Keep 2.5 notches/s
        # and carry sub-unit rounding across frames, independent of frame rate.
        self._remainder += 300 * dt
        units = int(self._remainder + 1e-9)
        self._remainder -= units
        return self._direction * units / 120
