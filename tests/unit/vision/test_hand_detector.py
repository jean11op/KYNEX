from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from holocontrol.infrastructure.vision.configuration import ConfiguracionVision
from holocontrol.infrastructure.vision.errors import ErrorModelo
from holocontrol.infrastructure.vision.hand_detector import DetectorMediaPipe
from holocontrol.ports.vision.models import EstadoVision, Fotograma, Lateralidad


@pytest.mark.parametrize("etiqueta_modelo,espejo", [("Right", False), ("Left", True)])
def test_convierte_bgr_a_rgb_y_exporta_21_puntos(crear_mano, etiqueta_modelo, espejo):
    mano = crear_mano()
    salida = SimpleNamespace(
        hand_landmarks=[[SimpleNamespace(x=p.x, y=p.y, z=p.z) for p in mano.puntos]],
        handedness=[[SimpleNamespace(category_name=etiqueta_modelo, score=0.95)]],
    )
    modelo = Mock()
    modelo.detect_for_video.return_value = salida
    detector = DetectorMediaPipe()
    detector._detector = modelo
    imagen = np.zeros((2, 2, 3), dtype=np.uint8)
    imagen[:] = (10, 20, 30)
    resultado = detector.detectar(Fotograma(imagen, 10, en_espejo=espejo))
    imagen_mp, instante_ms = modelo.detect_for_video.call_args.args
    assert tuple(imagen_mp.numpy_view()[0, 0]) == (30, 20, 10)
    assert instante_ms == 10
    assert len(resultado.manos[0].puntos) == 21
    assert resultado.manos[0].lateralidad is Lateralidad.DERECHA
    assert resultado.manos[0].confianza_lateralidad == 0.95
    detector.cerrar()
    modelo.close.assert_called_once()


def test_puntos_fuera_de_imagen_se_descartan(crear_mano):
    mano = crear_mano()
    puntos = [SimpleNamespace(x=p.x, y=p.y, z=p.z) for p in mano.puntos]
    puntos[8].x = 1.1
    detector = DetectorMediaPipe()
    modelo = Mock()
    modelo.detect_for_video.return_value = SimpleNamespace(
        hand_landmarks=[puntos],
        handedness=[[SimpleNamespace(category_name="Right", score=0.99)]],
    )
    detector._detector = modelo
    resultado = detector.detectar(Fotograma(np.zeros((2, 2, 3), dtype=np.uint8), 0))
    assert resultado.estado is EstadoVision.BAJA_CONFIANZA and not resultado.manos
    detector.cerrar()


@pytest.mark.parametrize(
    "imagen",
    [
        np.zeros((2, 2), dtype=np.uint8),
        np.zeros((2, 2, 3), dtype=np.float32),
        np.zeros((0, 2, 3), dtype=np.uint8),
    ],
)
def test_rechaza_formatos_de_imagen_invalidos(imagen):
    with pytest.raises(ValueError, match="uint8 BGR"):
        DetectorMediaPipe().detectar(Fotograma(imagen, 0))


def test_falta_de_modelo_se_informa_sin_descargar_nada(tmp_path):
    detector = DetectorMediaPipe(ConfiguracionVision(ruta_modelo=tmp_path / "ausente.task"))
    with pytest.raises(ErrorModelo, match="Falta el modelo local"):
        detector.detectar(Fotograma(np.zeros((2, 2, 3), dtype=np.uint8), 0))
