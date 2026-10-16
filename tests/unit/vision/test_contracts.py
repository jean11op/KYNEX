from dataclasses import FrozenInstanceError, replace
from math import nan

import pytest

from holocontrol.infrastructure.vision.configuration import ConfiguracionCamara, ConfiguracionVision
from holocontrol.ports.vision import (
    EstadoVision,
    EventoGesto,
    FaseGesto,
    PuntoMano,
    ResultadoVision,
)


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


@pytest.mark.parametrize("desplazamiento", [(0.1,), (0.1, nan), (0.1, float("inf"))])
def test_resultado_rechaza_desplazamientos_invalidos(desplazamiento, crear_mano):
    with pytest.raises(ValueError, match="desplazamiento"):
        ResultadoVision(
            100,
            EstadoVision.MANO_DETECTADA,
            crear_mano(),
            (0.5, 0.5),
            desplazamiento,
        )


def test_resultado_rechaza_eventos_fuera_de_orden_o_futuros():
    anterior = EventoGesto("indice", FaseGesto.INICIO, 50, 0, 0.9)
    posterior = replace(anterior, instante_ms=100, fase=FaseGesto.MANTENIMIENTO, duracion_ms=50)
    with pytest.raises(ValueError, match="ordenados"):
        ResultadoVision(100, EstadoVision.MANO_PERDIDA, eventos=(posterior, anterior))
    with pytest.raises(ValueError, match="posteriores"):
        ResultadoVision(50, EstadoVision.MANO_PERDIDA, eventos=(posterior,))


def test_estado_invalido_no_conserva_coordenadas_aunque_admita_historial(crear_mano):
    inicio = EventoGesto("indice", FaseGesto.INICIO, 50, 0, 0.9)
    resultado = ResultadoVision(100, EstadoVision.MANO_PERDIDA, eventos=(inicio,))
    assert resultado.eventos == (inicio,) and not resultado.mano_detectada
    with pytest.raises(ValueError, match="datos de una mano"):
        replace(resultado, mano=crear_mano(), posicion_indice=(0.5, 0.5))
