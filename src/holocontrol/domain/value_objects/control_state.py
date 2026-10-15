
from enum import Enum, auto


class ControlState(Enum):
    """Estados posibles del control de Windows."""

    STOPPED = auto()
    PAUSED = auto()
    ACTIVE = auto()
