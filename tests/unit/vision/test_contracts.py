from dataclasses import FrozenInstanceError, replace
from math import nan

import pytest

from holocontrol.infrastructure.vision.configuration import ConfiguracionCamara, ConfiguracionVision
from holocontrol.ports.vision.models import PuntoMano


@pytest.mark.parametrize(
    "indice,x,y,z",
    [(-1, 0.5, 0.5, 0), (21, 0.5, 0.5, 0), (0, -0.1, 0.5, 0), (0, 0.5, 1.1, 0), (0, 0.5, 0.5, nan)],
)
def test_rechaza_puntos_invalidos(indice, x, y, z):
    with pytest.raises(ValueError):
        PuntoMano(indice, x, y, z)


def test_z_puede_ser_negativo_y_los_puntos_son_inmutables():
    punto = PuntoMano(0, 0.5, 0.5, -0.2)
    with pytest.raises(FrozenInstanceError):
        punto.x = 0.4


def test_no_admite_muestras_incompletas_o_desordenadas(crear_mano):
    mano = crear_mano()
    with pytest.raises(ValueError, match="21 puntos"):
        replace(mano, puntos=mano.puntos[:-1])
    with pytest.raises(ValueError, match="21 puntos"):
        replace(mano, puntos=tuple(reversed(mano.puntos)))


@pytest.mark.parametrize(
    "campo,valor", [("indice", -1), ("ancho", 0), ("alto", False), ("fps", 0), ("espejo", "si")]
)
def test_valida_configuracion_camara(campo, valor):
    with pytest.raises(ValueError):
        ConfiguracionCamara(**{campo: valor})


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("umbral_deteccion", nan),
        ("factor_suavizado", 0),
        ("vigencia_ms", -1),
        ("umbral_pellizco_salida", 0.2),
    ],
)
def test_valida_parametros_vision(campo, valor):
    with pytest.raises(ValueError):
        ConfiguracionVision(**{campo: valor})
