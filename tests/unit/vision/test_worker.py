from dataclasses import replace
from threading import Event
from time import monotonic, monotonic_ns

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


def esperar_estado(adaptador, estado):
    limite = monotonic() + 1
    while (restante := limite - monotonic()) > 0:
        resultado = adaptador.obtener_resultado(restante)
        if resultado is not None and resultado.estado is estado:
            return resultado
    pytest.fail(f"El proveedor no informó {estado}; estado actual: {adaptador.estado}")


def test_hilo_entrega_resultados_y_libera_ambos_recursos(crear_mano):
    camara = CamaraSimulada()
    detector = DetectorSimulado(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    resultado = esperar_estado(adaptador, EstadoVision.MANO_DETECTADA)
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
    resultado = esperar_estado(adaptador, EstadoVision.ERROR_CAMARA)
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
    assert (
        esperar_estado(adaptador, EstadoVision.ERROR_PROCESAMIENTO).estado
        is EstadoVision.ERROR_PROCESAMIENTO
    )
    assert adaptador.detener(1)
    assert camara.cerrada and detector.cerrado


def test_consulta_invalida_coordenadas_caducadas_y_conserva_historial(crear_mano):
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
    assert resultado.mano is None and resultado.posicion_indice is None
    assert not resultado.mano_detectada and resultado.desplazamiento_vertical is None
    assert resultado.eventos == (evento,)
    assert resultado.eventos_actuales == ()
    assert adaptador.estado is EstadoVision.MANO_PERDIDA
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


def test_perdida_conserva_inicio_y_fin_pendientes_sin_reactivar_mano(crear_mano):
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
    assert resultado.eventos == (inicio, fin)
    assert resultado.eventos_actuales == (fin,)
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
        assert esperar_estado(adaptador, EstadoVision.MANO_DETECTADA).es_valido
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
        assert esperar_estado(adaptador, EstadoVision.MANO_DETECTADA).es_valido
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
        assert esperar_estado(adaptador, EstadoVision.MANO_DETECTADA).es_valido
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
    resultado = esperar_estado(adaptador, EstadoVision.ERROR_PROCESAMIENTO)
    assert resultado.estado is EstadoVision.ERROR_PROCESAMIENTO
    assert "nombres distintos" in resultado.mensaje
    assert adaptador.detener(1)


def test_camara_disponible_se_expone_antes_del_primer_fotograma(crear_mano):
    lectura_iniciada = Event()
    liberar_lectura = Event()

    class CamaraControlada(CamaraSimulada):
        def leer(self):
            lectura_iniciada.set()
            liberar_lectura.wait(2)
            return super().leer()

    camara = CamaraControlada()
    detector = DetectorSimulado(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    try:
        assert lectura_iniciada.wait(1)
        assert adaptador.en_ejecucion and adaptador.camara_disponible
        resultado = adaptador.obtener_resultado()
        assert resultado.estado is EstadoVision.CAMARA_DISPONIBLE
        assert resultado.camara_disponible and not resultado.mano_detectada
        assert resultado.posicion_indice is None
        liberar_lectura.set()
        assert esperar_estado(adaptador, EstadoVision.MANO_DETECTADA).mano_detectada
    finally:
        liberar_lectura.set()
        assert adaptador.detener(1)
    assert adaptador.estado is EstadoVision.DETENIDO
    assert not adaptador.en_ejecucion and not adaptador.camara_disponible


def test_estado_iniciando_no_confirma_disponibilidad_antes_de_abrir(crear_mano):
    inicio_detector = Event()
    liberar_detector = Event()
    camara = CamaraSimulada()
    detector = DetectorSimulado(crear_mano())

    def crear_detector():
        inicio_detector.set()
        liberar_detector.wait(2)
        return detector

    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=crear_detector)
    adaptador.iniciar()
    try:
        assert inicio_detector.wait(1)
        assert adaptador.estado is EstadoVision.INICIANDO
        assert adaptador.en_ejecucion and not adaptador.camara_disponible
        assert adaptador.obtener_resultado().estado is EstadoVision.INICIANDO
    finally:
        liberar_detector.set()
        assert adaptador.detener(1)


def test_camara_puede_estar_disponible_sin_una_mano(crear_mano):
    class DetectorSinMano(DetectorSimulado):
        def detectar(self, fotograma):
            return DeteccionManos(fotograma.instante_ms, (), EstadoVision.SIN_MANO, 640, 480)

    camara = CamaraSimulada()
    detector = DetectorSinMano(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    try:
        resultado = esperar_estado(adaptador, EstadoVision.SIN_MANO)
        assert resultado.camara_disponible and adaptador.camara_disponible
        assert not resultado.mano_detectada and resultado.posicion_indice is None
    finally:
        assert adaptador.detener(1)


def test_error_se_informa_antes_de_un_cierre_nativo_bloqueado(crear_mano):
    cierre_iniciado = Event()
    liberar_cierre = Event()

    class CamaraConFallo(CamaraSimulada):
        def abrir(self):
            raise ErrorCamara("Cámara desconectada")

    class DetectorConCierreLento(DetectorSimulado):
        def cerrar(self):
            cierre_iniciado.set()
            liberar_cierre.wait(2)
            super().cerrar()

    camara = CamaraConFallo()
    detector = DetectorConCierreLento(crear_mano())
    adaptador = AdaptadorVision(crear_camara=lambda: camara, crear_detector=lambda: detector)
    adaptador.iniciar()
    try:
        assert cierre_iniciado.wait(1)
        resultado = esperar_estado(adaptador, EstadoVision.ERROR_CAMARA)
        assert not resultado.camara_disponible and not resultado.mano_detectada
        assert adaptador.en_ejecucion and not adaptador.camara_disponible
        assert not detector.cerrado and not camara.cerrada
        with pytest.raises(RuntimeError, match="todavía"):
            adaptador.iniciar()
    finally:
        liberar_cierre.set()
        assert adaptador.detener(1)
    assert camara.cerrada and detector.cerrado
    assert adaptador.estado is EstadoVision.ERROR_CAMARA
