
from enum import Enum, auto
class EstadoControl(Enum):
    """Estados posibles del control de Windows."""
    STOPPED = auto()
    PAUSED = auto()
    ACTIVE = auto()
