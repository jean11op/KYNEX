from dataclasses import replace
from threading import Event
from time import monotonic_ns

import numpy as np
import pytest

from holocontrol.infrastructure.vision.errors import ErrorCamara
from holocontrol.infrastructure.vision.vision_worker import AdaptadorVision
from holocontrol.ports.vision.models import (
    DeteccionManos,
    EstadoVision,
    EventoGesto,
    FaseGesto,
    Fotograma,
    ResultadoVision,
)


class CamaraSimulada:
    def __init__(self):
        self.cerrada = False
        self.primer_fotograma = True
        self.permitir_lectura = Event()

    def abrir(self):
        pass

    def leer(self):
        if not self.primer_fotograma:
            self.permitir_lectura.wait(0.05)
        self.primer_fotograma = False
        return Fotograma(np.zeros((10, 10, 3), dtype=np.uint8), monotonic_ns() // 1_000_000)

    def cerrar(self):
        self.cerrada = True


class DetectorSimulado:
    def __init__(self, mano):
        self.mano = mano
        self.cerrado = False

    def detectar(self, fotograma):
        return DeteccionManos(
            fotograma.instante_ms,
            (self.mano,),
            EstadoVision.MANO_DETECTADA,
            640,
            480,
        )

    def cerrar(self):
        self.cerrado = True


def test_hilo_entrega_resultados_y_libera_ambos_recursos(crear_mano):
    camara = CamaraSimulada()
    detector = DetectorSimulado(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    resultado = adaptador.obtener_resultado(1)
    assert resultado.es_valido
    assert adaptador.detener(1)
    assert camara.cerrada and detector.cerrado
    assert not adaptador.en_ejecucion
    assert adaptador.obtener_resultado().estado is EstadoVision.DETENIDO


def test_fallo_de_camara_se_comunica_y_libera_detector(crear_mano):
    class CamaraConFallo(CamaraSimulada):
        def abrir(self):
            raise ErrorCamara("Cámara desconectada")

    camara = CamaraConFallo()
    detector = DetectorSimulado(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    resultado = adaptador.obtener_resultado(1)
    assert resultado.estado is EstadoVision.ERROR_CAMARA and not resultado.es_valido
    assert resultado.mano is None and not resultado.eventos
    assert adaptador.detener(1)
    assert camara.cerrada and detector.cerrado


def test_fallo_del_detector_no_deja_camara_abierta(crear_mano):
    class DetectorConFallo(DetectorSimulado):
        def detectar(self, fotograma):
            raise RuntimeError("Fallo del modelo")

    camara = CamaraSimulada()
    detector = DetectorConFallo(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    assert adaptador.obtener_resultado(1).estado is EstadoVision.ERROR_PROCESAMIENTO
    assert adaptador.detener(1)
    assert camara.cerrada and detector.cerrado


def test_consulta_descarta_coordenadas_y_eventos_caducados(crear_mano):
    adaptador = AdaptadorVision()
    pasado_ms = monotonic_ns() // 1_000_000 - 201
    evento = EventoGesto("pellizco", FaseGesto.INICIO, pasado_ms, 0, 0.9)
    adaptador._publicar(
        ResultadoVision(
            pasado_ms,
            EstadoVision.MANO_DETECTADA,
            crear_mano(),
            (0.5, 0.5),
            eventos=(evento,),
        )
    )
    resultado = adaptador.obtener_resultado()
    assert resultado.estado is EstadoVision.MANO_PERDIDA
    assert resultado.mano is None and resultado.posicion_indice is None and not resultado.eventos
    assert adaptador.obtener_resultado() is None


def test_fin_no_se_pierde_si_la_interfaz_consume_mas_lento(crear_mano):
    adaptador = AdaptadorVision()
    instante_ms = monotonic_ns() // 1_000_000
    fin = EventoGesto("pellizco", FaseGesto.FIN, instante_ms, 50, 0.9)
    primer_resultado = ResultadoVision(
        instante_ms,
        EstadoVision.MANO_DETECTADA,
        crear_mano(),
        (0.5, 0.5),
        eventos=(fin,),
    )
    adaptador._publicar(primer_resultado)
    adaptador._publicar(replace(primer_resultado, eventos=()))
    assert adaptador.obtener_resultado().eventos == (fin,)


def test_perdida_descarta_inicio_que_todavia_no_consumio_la_interfaz(crear_mano):
    adaptador = AdaptadorVision()
    instante_ms = monotonic_ns() // 1_000_000
    inicio = EventoGesto("pellizco", FaseGesto.INICIO, instante_ms, 0, 0.9)
    adaptador._publicar(
        ResultadoVision(
            instante_ms,
            EstadoVision.MANO_DETECTADA,
            crear_mano(),
            (0.5, 0.5),
            eventos=(inicio,),
        )
    )
    fin = replace(inicio, fase=FaseGesto.FIN)
    adaptador._publicar(ResultadoVision(instante_ms, EstadoVision.MANO_PERDIDA, eventos=(fin,)))
    resultado = adaptador.obtener_resultado()
    assert resultado.eventos == (fin,)
    assert not resultado.es_valido


def test_se_puede_reiniciar_con_recursos_nuevos(crear_mano):
    camaras = []
    detectores = []

    def crear_camara():
        camara = CamaraSimulada()
        camaras.append(camara)
        return camara

    def crear_detector():
        detector = DetectorSimulado(crear_mano())
        detectores.append(detector)
        return detector

    adaptador = AdaptadorVision(crear_camara=crear_camara, crear_detector=crear_detector)
    for _ in range(2):
        adaptador.iniciar()
        assert adaptador.obtener_resultado(1).es_valido
        assert adaptador.detener(1)
    assert len(camaras) == len(detectores) == 2
    assert all(camara.cerrada for camara in camaras)
    assert all(detector.cerrado for detector in detectores)


def test_lectura_nativa_bloqueada_no_impide_invalidar_control(crear_mano):
    lectura_bloqueada = Event()
    liberar_lectura = Event()

    class CamaraBloqueada(CamaraSimulada):
        def leer(self):
            if not self.primer_fotograma:
                lectura_bloqueada.set()
                liberar_lectura.wait(2)
            self.primer_fotograma = False
            return Fotograma(np.zeros((10, 10, 3), dtype=np.uint8), monotonic_ns() // 1_000_000)

    camara = CamaraBloqueada()
    detector = DetectorSimulado(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    try:
        assert adaptador.obtener_resultado(1).es_valido
        assert lectura_bloqueada.wait(1)
        assert not adaptador.detener(0.01)
        assert adaptador.obtener_resultado().estado is EstadoVision.ERROR_CAMARA
        assert not camara.cerrada and not detector.cerrado
        with pytest.raises(RuntimeError, match="todavía"):
            adaptador.iniciar()
    finally:
        liberar_lectura.set()
        assert adaptador.detener(1)
    assert camara.cerrada and detector.cerrado


def test_vista_previa_es_opcional_copiada_y_se_descarta_al_desactivarla(crear_mano):
    camara = CamaraSimulada()
    detector = DetectorSimulado(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    assert adaptador.obtener_fotograma() is None
    adaptador.activar_vista_previa(True)
    adaptador.iniciar()
    try:
        assert adaptador.obtener_resultado(1).es_valido
        imagen = adaptador.obtener_fotograma()
        assert imagen is not None
        imagen.imagen[:] = 255
        assert not np.any(adaptador.obtener_fotograma().imagen)
        adaptador.activar_vista_previa(False)
        assert adaptador.obtener_fotograma() is None
    finally:
        assert adaptador.detener(1)
    assert adaptador.obtener_fotograma() is None


def test_plantillas_duplicadas_informan_error_al_iniciar(crear_mano):
    from holocontrol.ports.vision.models import MuestraPostura, PlantillaGesto

    muestras = tuple(MuestraPostura(indice * 50, crear_mano()) for indice in range(20))
    plantilla = PlantillaGesto("duplicada", muestras, (0.0,) * 63, 0.8)
    adaptador = AdaptadorVision(plantillas=(plantilla, plantilla))
    adaptador.iniciar()
    resultado = adaptador.obtener_resultado(1)
    assert resultado.estado is EstadoVision.ERROR_PROCESAMIENTO
    assert "nombres distintos" in resultado.mensaje
    assert adaptador.detener(1)
