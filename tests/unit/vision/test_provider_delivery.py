from dataclasses import replace

import pytest

from holocontrol.infrastructure.vision import vision_worker
from holocontrol.infrastructure.vision.errors import ErrorCamara
from holocontrol.infrastructure.vision.vision_processor import ProcesadorVision
from holocontrol.infrastructure.vision.vision_worker import AdaptadorVision
from holocontrol.ports.vision.models import (
    EstadoVision,
    EventoGesto,
    FaseGesto,
    ResultadoVision,
)
from holocontrol.ports.vision.vision_provider import ProveedorVision


@pytest.fixture
def reloj_vision(monkeypatch):
    reloj_ms = [10_000]
    monkeypatch.setattr(vision_worker, "monotonic_ns", lambda: reloj_ms[0] * 1_000_000)
    return reloj_ms


def publicar_gesto(adaptador, mano, evento):
    adaptador._publicar(
        ResultadoVision(
            evento.instante_ms,
            EstadoVision.MANO_DETECTADA,
            mano,
            (0.5, 0.5),
            (0.0, 0.0),
            (evento,),
        )
    )


def test_proveedor_expone_estado_inicial_y_detencion_sin_iniciar():
    proveedor = AdaptadorVision()
    assert isinstance(proveedor, ProveedorVision)
    assert proveedor.estado is EstadoVision.DETENIDO
    assert not proveedor.en_ejecucion and not proveedor.camara_disponible
    assert proveedor.obtener_resultado() is None
    assert proveedor.detener()
    resultado = proveedor.obtener_resultado()
    assert resultado.estado is EstadoVision.DETENIDO
    assert not resultado.mano_detectada and not resultado.camara_disponible


def test_todas_las_fases_se_entregan_una_vez_y_en_orden(reloj_vision, crear_mano):
    proveedor = AdaptadorVision()
    mano = crear_mano()
    eventos = tuple(
        EventoGesto("pellizco", fase, 9_900 + indice * 25, indice * 25, 0.95)
        for indice, fase in enumerate(
            (FaseGesto.INICIO, FaseGesto.MANTENIMIENTO, FaseGesto.MANTENIMIENTO, FaseGesto.FIN)
        )
    )
    for evento in eventos[:2]:
        publicar_gesto(proveedor, mano, evento)
    primera_consulta = proveedor.obtener_resultado()
    assert primera_consulta.eventos == eventos[:2]
    assert primera_consulta.eventos_actuales == eventos[1:2]
    assert proveedor.obtener_resultado() is None
    for evento in eventos[2:]:
        publicar_gesto(proveedor, mano, evento)
    assert proveedor.obtener_resultado().eventos == eventos[2:]
    assert proveedor.obtener_resultado() is None


def test_mas_de_64_eventos_no_desbordan_ni_pierden_fases(reloj_vision, crear_mano):
    proveedor = AdaptadorVision()
    mano = crear_mano()
    eventos = tuple(
        EventoGesto(
            "pellizco",
            FaseGesto.INICIO
            if indice == 0
            else FaseGesto.FIN
            if indice == 127
            else FaseGesto.MANTENIMIENTO,
            9_873 + indice,
            indice,
            0.95,
        )
        for indice in range(128)
    )
    for evento in eventos:
        publicar_gesto(proveedor, mano, evento)
    resultado = proveedor.obtener_resultado()
    assert resultado.mano_detectada
    assert resultado.eventos == eventos
    assert resultado.eventos_actuales == eventos[-1:]
    assert proveedor.obtener_resultado() is None


@pytest.mark.parametrize(
    "estado",
    [
        EstadoVision.MANO_PERDIDA,
        EstadoVision.ERROR_CAMARA,
        EstadoVision.ERROR_PROCESAMIENTO,
        EstadoVision.DETENIDO,
    ],
)
def test_estado_invalido_conserva_historial_sin_coordenadas(estado, reloj_vision, crear_mano):
    proveedor = AdaptadorVision()
    inicio = EventoGesto("pellizco", FaseGesto.INICIO, 9_000, 0, 0.95)
    mantenimiento = replace(
        inicio, fase=FaseGesto.MANTENIMIENTO, instante_ms=9_100, duracion_ms=100
    )
    fin = replace(inicio, fase=FaseGesto.FIN, instante_ms=10_000, duracion_ms=1_000)
    for evento in (inicio, mantenimiento):
        publicar_gesto(proveedor, crear_mano(), evento)
    proveedor._publicar(ResultadoVision(10_000, estado, eventos=(fin,)))
    resultado = proveedor.obtener_resultado()
    assert resultado.eventos == (inicio, mantenimiento, fin)
    assert resultado.eventos_actuales == (fin,)
    assert not resultado.mano_detectada
    assert resultado.mano is None and resultado.posicion_indice is None
    assert resultado.desplazamiento_vertical is None


def test_historial_antiguo_no_se_descarta_con_un_fotograma_actual(reloj_vision, crear_mano):
    proveedor = AdaptadorVision()
    inicio = EventoGesto("indice", FaseGesto.INICIO, 9_000, 0, 0.95)
    actual = replace(inicio, fase=FaseGesto.MANTENIMIENTO, instante_ms=10_000, duracion_ms=1_000)
    for evento in (inicio, actual):
        publicar_gesto(proveedor, crear_mano(), evento)
    resultado = proveedor.obtener_resultado()
    assert resultado.mano_detectada
    assert resultado.eventos == (inicio, actual)
    assert resultado.eventos_actuales == (actual,)


def test_desplazamiento_vertical_acumula_movimiento_entre_consultas(reloj_vision, crear_mano):
    proveedor = AdaptadorVision()
    mano = crear_mano()
    proveedor._publicar(
        ResultadoVision(9_900, EstadoVision.MANO_DETECTADA, mano, (0.5, 0.6), (0, 0))
    )
    proveedor.obtener_resultado()
    for instante, y, delta_y in ((9_930, 0.61, 0.01), (9_960, 0.63, 0.02), (10_000, 0.63, 0.0)):
        proveedor._publicar(
            ResultadoVision(instante, EstadoVision.MANO_DETECTADA, mano, (0.5, y), (0, delta_y))
        )
    resultado = proveedor.obtener_resultado()
    assert resultado.posicion_indice == (0.5, 0.63)
    assert resultado.desplazamiento_vertical == pytest.approx(0.03)
    reloj_vision[0] = 10_033
    proveedor._publicar(
        ResultadoVision(10_033, EstadoVision.MANO_DETECTADA, mano, (0.5, 0.63), (0, 0))
    )
    assert proveedor.obtener_resultado().desplazamiento_vertical == 0


def test_perdida_reinicia_desplazamiento_antes_de_otra_mano(reloj_vision, crear_mano):
    proveedor = AdaptadorVision()
    mano = crear_mano()
    proveedor._publicar(
        ResultadoVision(9_900, EstadoVision.MANO_DETECTADA, mano, (0.5, 0.6), (0, 0.2))
    )
    proveedor._publicar(ResultadoVision(9_930, EstadoVision.MANO_PERDIDA))
    proveedor._publicar(
        ResultadoVision(10_000, EstadoVision.MANO_DETECTADA, mano, (0.5, 0.5), (0, 0))
    )
    assert proveedor.obtener_resultado().desplazamiento_vertical == 0


def test_resultado_calculado_durante_cierre_conserva_eventos_sin_reactivar(
    reloj_vision, crear_mano
):
    proveedor = AdaptadorVision()
    proveedor._parada.set()
    inicio = EventoGesto("pellizco", FaseGesto.INICIO, 9_990, 0, 0.95)
    publicar_gesto(proveedor, crear_mano(), inicio)
    resultado = proveedor.obtener_resultado()
    assert resultado.estado is EstadoVision.DETENIENDO
    assert resultado.eventos == (inicio,) and resultado.eventos_actuales == ()
    assert not resultado.mano_detectada and not resultado.camara_disponible
    assert resultado.posicion_indice is None


def test_reinicio_descarta_eventos_pendientes_del_ciclo_anterior(reloj_vision, crear_mano):
    class CamaraConFallo:
        def abrir(self):
            raise ErrorCamara("Cámara no disponible")

        def cerrar(self):
            pass

    class DetectorSinRecursos:
        def cerrar(self):
            pass

    proveedor = AdaptadorVision(crear_camara=CamaraConFallo, crear_detector=DetectorSinRecursos)
    inicio = EventoGesto("pellizco", FaseGesto.INICIO, 9_000, 0, 0.95)
    publicar_gesto(proveedor, crear_mano(), inicio)
    assert proveedor.detener()
    proveedor.iniciar()
    assert proveedor.detener(1)
    resultado = proveedor.obtener_resultado()
    assert resultado.estado is EstadoVision.ERROR_CAMARA
    assert resultado.eventos == ()
    assert proveedor.obtener_resultado() is None


@pytest.mark.parametrize("campo,valor", [("espera_s", -1), ("espera_s", float("nan"))])
def test_esperas_invalidas_no_bloquean_el_proveedor(campo, valor):
    proveedor = AdaptadorVision()
    with pytest.raises(ValueError, match="finita"):
        proveedor.obtener_resultado(**{campo: valor})
    with pytest.raises(ValueError, match="finita"):
        proveedor.detener(**{campo: valor})


def test_procesamiento_conserva_gestos_hasta_perdida_y_recuperacion(
    reloj_vision, crear_mano, crear_deteccion
):
    proveedor = AdaptadorVision()
    procesador = ProcesadorVision()
    secuencia = (
        (9_400, "indice"),
        (9_500, "indice"),
        (9_533, "pellizco"),
        (9_633, "pellizco"),
        (9_666, "pellizco"),
        (9_700, None),
        (9_733, "indice"),
        (9_833, "indice"),
        (9_866, "pellizco"),
        (9_966, "pellizco"),
        (10_000, None),
    )
    for instante, postura in secuencia:
        mano = crear_mano(postura) if postura is not None else None
        proveedor._publicar(procesador.interpretar(crear_deteccion(mano, instante)))
    resultado = proveedor.obtener_resultado()
    assert [(evento.nombre, evento.fase, evento.instante_ms) for evento in resultado.eventos] == [
        ("indice", FaseGesto.INICIO, 9_500),
        ("indice", FaseGesto.FIN, 9_533),
        ("pellizco", FaseGesto.INICIO, 9_633),
        ("pellizco", FaseGesto.MANTENIMIENTO, 9_666),
        ("pellizco", FaseGesto.FIN, 9_700),
        ("indice", FaseGesto.INICIO, 9_833),
        ("indice", FaseGesto.FIN, 9_866),
        ("pellizco", FaseGesto.INICIO, 9_966),
        ("pellizco", FaseGesto.FIN, 10_000),
    ]
    assert resultado.estado is EstadoVision.MANO_PERDIDA
    assert resultado.posicion_indice is None and not resultado.mano_detectada
    assert proveedor.obtener_resultado() is None
