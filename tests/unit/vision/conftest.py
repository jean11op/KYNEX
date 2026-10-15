import pytest

from holocontrol.ports.vision.models import (
    DeteccionManos,
    EstadoVision,
    Lateralidad,
    ManoDetectada,
    PuntoMano,
)


@pytest.fixture
def crear_mano():
    def construir(
        postura="indice", delta_x=0.0, delta_y=0.0, lateralidad=Lateralidad.DERECHA, confianza=0.99
    ):
        coordenadas = [(0.5, 0.85, 0.0)] * 21
        coordenadas[1:5] = [
            (0.40, 0.74, 0.0),
            (0.32, 0.66, 0.0),
            (0.26, 0.58, 0.0),
            (0.22, 0.50, 0.0),
        ]
        extendidos = {
            "indice": (True, False, False, False),
            "pellizco": (True, False, False, False),
            "dos_dedos": (True, True, False, False),
            "palma_abierta": (True, True, True, True),
            "puno": (False, False, False, False),
            "personalizado": (False, True, False, False),
        }[postura]
        for base, x, extendido in zip((5, 9, 13, 17), (0.42, 0.50, 0.58, 0.66), extendidos):
            coordenadas[base : base + 4] = (
                [(x, y, 0.0) for y in (0.60, 0.45, 0.30, 0.15)]
                if extendido
                else [(x, y, 0.0) for y in (0.60, 0.47, 0.57, 0.64)]
            )
        if postura == "pellizco":
            coordenadas[4] = (0.44, 0.15, 0.0)
        puntos = tuple(
            PuntoMano(indice, x + delta_x, y + delta_y, z)
            for indice, (x, y, z) in enumerate(coordenadas)
        )
        return ManoDetectada(puntos, lateralidad, confianza)

    return construir


@pytest.fixture
def crear_deteccion():
    def construir(mano=None, instante=0, estado=None):
        return DeteccionManos(
            instante,
            (mano,) if mano is not None else (),
            estado or (EstadoVision.MANO_DETECTADA if mano else EstadoVision.SIN_MANO),
            640,
            480,
        )

    return construir
