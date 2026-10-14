from dataclasses import replace

import pytest

from holocontrol.infrastructure.vision.gesture_training import EntrenadorGestos
from holocontrol.infrastructure.vision.vision_processor import ProcesadorVision
from holocontrol.ports.vision.models import DeteccionManos, EstadoVision, FaseGesto


def test_plantilla_se_reconstruye_desde_sus_21_puntos_sin_dimensiones_originales(
    crear_mano,
    crear_deteccion,
):
    entrenador = EntrenadorGestos()
    for indice in range(20):
        entrenador.registrar(crear_deteccion(crear_mano("personalizado"), indice * 50))
    original = entrenador.finalizar("propio")
    reconstruccion = EntrenadorGestos()
    for indice, muestra in enumerate(original.muestras):
        deteccion = DeteccionManos(
            indice * 50,
            (muestra.mano,),
            EstadoVision.MANO_DETECTADA,
            1,
            1,
        )
        reconstruccion.registrar(deteccion)
    recuperada = reconstruccion.finalizar("propio")
    assert recuperada.descriptor == pytest.approx(original.descriptor)
    procesador = ProcesadorVision(plantillas=(recuperada,))
    procesador.interpretar(crear_deteccion(crear_mano("personalizado"), 0))
    resultado = procesador.interpretar(crear_deteccion(crear_mano("personalizado"), 100))
    assert resultado.eventos[0].nombre == "personalizado:propio"
    assert resultado.eventos[0].fase is FaseGesto.INICIO


def test_postura_guardada_se_reconoce_al_cambiar_el_espejo(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    original = crear_mano("personalizado")
    for indice in range(20):
        entrenador.registrar(crear_deteccion(original, indice * 50))
    plantilla = entrenador.finalizar("propio")
    reflejada = replace(original, puntos=tuple(replace(p, x=1 - p.x) for p in original.puntos))
    procesador = ProcesadorVision(plantillas=(plantilla,))
    procesador.interpretar(replace(crear_deteccion(reflejada, 0), en_espejo=True))
    resultado = procesador.interpretar(replace(crear_deteccion(reflejada, 100), en_espejo=True))
    assert resultado.eventos[0].nombre == "personalizado:propio"
