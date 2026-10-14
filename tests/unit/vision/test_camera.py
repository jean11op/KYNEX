from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from holocontrol.infrastructure.vision.camera import CamaraOpenCV
from holocontrol.infrastructure.vision.configuration import ConfiguracionCamara
from holocontrol.infrastructure.vision.errors import ErrorCamara


def test_captura_camara_elegida_espejo_y_cierre(monkeypatch):
    imagen = np.zeros((2, 3, 3), dtype=np.uint8)
    imagen[:, 0] = (10, 20, 30)
    captura = Mock()
    captura.isOpened.return_value = True
    captura.read.return_value = True, imagen
    constructor = Mock(return_value=captura)
    monkeypatch.setattr(cv2, "VideoCapture", constructor)
    camara = CamaraOpenCV(ConfiguracionCamara(indice=2))
    with camara:
        primer_fotograma = camara.leer()
        segundo_fotograma = camara.leer()
    camara.cerrar()
    constructor.assert_called_once_with(2)
    assert np.array_equal(primer_fotograma.imagen[:, 2], imagen[:, 0])
    assert segundo_fotograma.instante_ms > primer_fotograma.instante_ms
    assert primer_fotograma.en_espejo is True
    captura.release.assert_called_once()


def test_apertura_fallida_libera_dispositivo(monkeypatch):
    captura = Mock()
    captura.isOpened.return_value = False
    monkeypatch.setattr(cv2, "VideoCapture", Mock(return_value=captura))
    camara = CamaraOpenCV()
    with pytest.raises(ErrorCamara, match="No se puede abrir"):
        camara.abrir()
    captura.release.assert_called_once()


def test_lectura_fallida_no_reutiliza_imagen_anterior(monkeypatch):
    captura = Mock()
    captura.isOpened.return_value = True
    captura.read.side_effect = [(True, np.zeros((2, 2, 3), dtype=np.uint8)), (False, None)]
    monkeypatch.setattr(cv2, "VideoCapture", Mock(return_value=captura))
    with CamaraOpenCV() as camara:
        camara.leer()
        with pytest.raises(ErrorCamara, match="dejó de entregar"):
            camara.leer()
    captura.release.assert_called_once()
