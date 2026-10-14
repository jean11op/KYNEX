from dataclasses import replace
from math import cos, sin

import pytest

from holocontrol.infrastructure.vision.geometry import descriptor_postura
from holocontrol.infrastructure.vision.gesture_training import (
    EntrenadorGestos,
    distancia_descriptores,
)
from holocontrol.infrastructure.vision.vision_processor import ProcesadorVision
from holocontrol.ports.vision.models import EstadoVision, FaseGesto, PuntoMano


def test_exige_20_muestras_y_rechaza_fotogramas_reutilizados(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    deteccion = crear_deteccion(crear_mano("personalizado"), 0)
    entrenador.registrar(deteccion)
    with pytest.raises(ValueError, match="50 ms"):
        entrenador.registrar(deteccion)
    with pytest.raises(ValueError, match="Faltan muestras"):
        entrenador.finalizar("mi_postura")
    with pytest.raises(ValueError, match="20 muestras"):
        EntrenadorGestos(minimo_muestras=19)


def test_postura_personalizada_se_reconoce_con_muestras_coherentes(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    for indice in range(20):
        mano = crear_mano("personalizado", delta_x=(indice % 3) * 0.005)
        entrenador.registrar(crear_deteccion(mano, indice * 50))
    plantilla = entrenador.finalizar("medio_extendiendo")
    assert len(plantilla.muestras) == 20
    assert len(plantilla.muestras[0].mano.puntos) == 21
    procesador = ProcesadorVision(plantillas=(plantilla,))
    procesador.interpretar(crear_deteccion(crear_mano("personalizado"), 0))
    resultado = procesador.interpretar(crear_deteccion(crear_mano("personalizado"), 100))
    assert resultado.eventos[0].nombre == "personalizado:medio_extendiendo"
    assert resultado.eventos[0].fase is FaseGesto.INICIO


def test_descriptor_es_invariante_a_posicion_escala_y_rotacion(crear_mano):
    original = crear_mano("personalizado")
    puntos = []
    for punto in original.puntos:
        x, y = (punto.x - 0.5) * (640 / 480), punto.y - 0.85
        rotado_x = 0.8 * (x * cos(0.15) - y * sin(0.15))
        rotado_y = 0.8 * (x * sin(0.15) + y * cos(0.15))
        puntos.append(PuntoMano(punto.indice, 0.5 + rotado_x / (640 / 480), 0.85 + rotado_y, 0))
    transformada = replace(original, puntos=tuple(puntos))
    primer_descriptor = descriptor_postura(original, 640 / 480)
    segundo_descriptor = descriptor_postura(transformada, 640 / 480)
    assert distancia_descriptores(primer_descriptor, segundo_descriptor) < 1e-8


def test_rechaza_mezcla_de_posturas_distintas(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    for indice in range(20):
        postura = "personalizado" if indice < 10 else "palma_abierta"
        entrenador.registrar(crear_deteccion(crear_mano(postura), indice * 50))
    with pytest.raises(ValueError, match="posturas diferentes"):
        entrenador.finalizar("inconsistente")


def test_muestras_invalidas_o_nombres_basicos_no_se_entrenan(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    with pytest.raises(ValueError, match="inválida"):
        entrenador.registrar(crear_deteccion(instante=0, estado=EstadoVision.BAJA_CONFIANZA))
    with pytest.raises(ValueError, match="lateralidad fiable"):
        entrenador.registrar(crear_deteccion(crear_mano(confianza=0.1), 0))
    with pytest.raises(ValueError, match="nombre propio"):
        entrenador.finalizar("pellizco")


def test_plantillas_ambiguas_no_generan_acciones(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    for indice in range(20):
        entrenador.registrar(crear_deteccion(crear_mano("personalizado"), indice * 50))
    primera = entrenador.finalizar("primera")
    segunda = replace(primera, nombre="segunda")
    procesador = ProcesadorVision(plantillas=(primera, segunda))
    procesador.interpretar(crear_deteccion(crear_mano("personalizado"), 0))
    assert not procesador.interpretar(crear_deteccion(crear_mano("personalizado"), 100)).eventos


def test_reiniciar_entrenamiento_descarta_muestras(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    entrenador.registrar(crear_deteccion(crear_mano("personalizado"), 0))
    entrenador.reiniciar()
    assert entrenador.muestras == ()


def test_postura_basica_no_se_puede_disfrazar_de_personalizada(crear_mano, crear_deteccion):
    entrenador = EntrenadorGestos()
    for indice in range(20):
        entrenador.registrar(crear_deteccion(crear_mano(), indice * 50))
    with pytest.raises(ValueError, match="gesto básico"):
        entrenador.finalizar("mi_indice")
