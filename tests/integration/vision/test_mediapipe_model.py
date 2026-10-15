import hashlib
from pathlib import Path

import numpy as np
import pytest

from holocontrol.infrastructure.vision import DetectorMediaPipe, ProcesadorVision
from holocontrol.ports.vision.models import EstadoVision, Fotograma


def test_modelo_local_tiene_la_huella_de_la_version_oficial():
    ruta = (
        Path(__file__).parents[3]
        / "src/holocontrol/infrastructure/vision/models/hand_landmarker.task"
    )
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == (
        "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
    )


def test_modelo_real_procesa_imagenes_sin_mano_y_no_emite_gestos():
    procesador = ProcesadorVision()
    imagen = np.zeros((480, 640, 3), dtype=np.uint8)
    with DetectorMediaPipe() as detector:
        for instante_ms in (0, 40, 80):
            resultado = procesador.procesar(Fotograma(imagen, instante_ms), detector)
            assert resultado.estado is EstadoVision.SIN_MANO
            assert not resultado.es_valido and not resultado.eventos
            assert resultado.posicion_indice is None
        with pytest.raises(ValueError, match="aumentar"):
            detector.detectar(Fotograma(imagen, 80))
