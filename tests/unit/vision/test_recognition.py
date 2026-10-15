from dataclasses import replace

import pytest

from holocontrol.infrastructure.vision.vision_processor import ProcesadorVision
from holocontrol.ports.vision.models import EstadoVision, FaseGesto, Lateralidad


def test_indice_se_estabiliza_y_no_produce_click_por_permanencia(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    mano = crear_mano()
    resultados = [
        procesador.interpretar(crear_deteccion(mano, instante)) for instante in range(0, 2100, 100)
    ]
    assert resultados[0].eventos == ()
    assert resultados[1].eventos[0].nombre == "indice"
    assert resultados[1].eventos[0].fase is FaseGesto.INICIO
    assert all(evento.nombre == "indice" for r in resultados for evento in r.eventos)
    assert sum(e.fase is FaseGesto.INICIO for r in resultados for e in r.eventos) == 1


def test_pellizco_sostenido_y_fin_inmediato(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    procesador.interpretar(crear_deteccion(crear_mano(), 0))
    procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 50))
    inicio = procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 150))
    mantenido = procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 180))
    fin = procesador.interpretar(crear_deteccion(crear_mano(), 200))
    assert [(e.nombre, e.fase) for e in inicio.eventos] == [("pellizco", FaseGesto.INICIO)]
    assert mantenido.eventos[0].fase is FaseGesto.MANTENIMIENTO
    assert mantenido.eventos[0].duracion_ms == 30
    assert fin.eventos[0].fase is FaseGesto.FIN


def test_no_inicia_pellizco_si_la_captura_empieza_con_mano_cerrada(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    assert not procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 0)).eventos
    assert not procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 100)).eventos


def test_histeresis_evitar_fin_por_ruido_en_pellizco(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    procesador.interpretar(crear_deteccion(crear_mano(), 0))
    mano = crear_mano("pellizco")
    procesador.interpretar(crear_deteccion(mano, 50))
    procesador.interpretar(crear_deteccion(mano, 150))
    puntos = list(mano.puntos)
    puntos[4] = replace(puntos[4], x=mano.puntos[8].x + 0.24 * 0.38)
    ruido = replace(mano, puntos=tuple(puntos))
    resultado = procesador.interpretar(crear_deteccion(ruido, 180))
    assert resultado.eventos[0].nombre == "pellizco"
    assert resultado.eventos[0].fase is FaseGesto.MANTENIMIENTO


def test_perdida_termina_pellizco_y_recuperacion_exige_soltar(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    procesador.interpretar(crear_deteccion(crear_mano(), 0))
    procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 50))
    procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 150))
    perdido = procesador.interpretar(crear_deteccion(instante=180))
    assert perdido.estado is EstadoVision.MANO_PERDIDA
    assert perdido.posicion_indice is None and perdido.mano is None
    assert perdido.eventos[0].fase is FaseGesto.FIN
    assert not procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 200)).eventos
    assert not procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 300)).eventos
    procesador.interpretar(crear_deteccion(crear_mano(), 350))
    procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 400))
    assert procesador.interpretar(crear_deteccion(crear_mano("pellizco"), 500)).eventos[0].fase is (
        FaseGesto.INICIO
    )


@pytest.mark.parametrize("postura", ["palma_abierta", "puno"])
def test_gesto_discreto_exige_800ms_quieto_y_no_se_repite(postura, crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    resultados = [
        procesador.interpretar(crear_deteccion(crear_mano(postura), instante))
        for instante in range(0, 1700, 100)
    ]
    inicios = [
        evento for r in resultados for evento in r.eventos if evento.fase is FaseGesto.INICIO
    ]
    assert len(inicios) == 1
    assert inicios[0].nombre == postura and inicios[0].instante_ms == 800


@pytest.mark.parametrize("signo,direccion", [(1, "derecha"), (-1, "izquierda")])
def test_deslizamiento_no_activa_palma_quieta(signo, direccion, crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    resultados = [
        procesador.interpretar(
            crear_deteccion(crear_mano("palma_abierta", delta_x=signo * delta), t)
        )
        for t, delta in ((0, 0), (100, 0.11), (200, 0.22), (300, 0.22), (400, 0.22))
    ]
    inicios = [
        evento for r in resultados for evento in r.eventos if evento.fase is FaseGesto.INICIO
    ]
    assert [evento.nombre for evento in inicios] == [f"deslizamiento_{direccion}"]


def test_dos_dedos_informa_desplazamiento_vertical(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    procesador.interpretar(crear_deteccion(crear_mano("dos_dedos"), 0))
    resultado = procesador.interpretar(crear_deteccion(crear_mano("dos_dedos", delta_y=0.05), 100))
    assert resultado.eventos[0].nombre == "dos_dedos"
    assert resultado.desplazamiento_indice[1] > 0
    assert resultado.posicion_indice[1] < 0.20


@pytest.mark.parametrize(
    "lateralidad,confianza,estado",
    [
        (Lateralidad.IZQUIERDA, 0.99, EstadoVision.MANO_NO_SELECCIONADA),
        (Lateralidad.DERECHA, 0.4, EstadoVision.BAJA_CONFIANZA),
    ],
)
def test_ignora_mano_no_elegida_o_lateralidad_incierta(
    lateralidad,
    confianza,
    estado,
    crear_mano,
    crear_deteccion,
):
    resultado = ProcesadorVision().interpretar(
        crear_deteccion(
            crear_mano(lateralidad=lateralidad, confianza=confianza),
            0,
        )
    )
    assert resultado.estado is estado and not resultado.es_valido
    assert resultado.posicion_indice is None and not resultado.eventos


def test_dos_manos_no_cambian_el_control_a_la_no_dominante(crear_mano, crear_deteccion):
    dominante = crear_mano()
    otra = crear_mano(lateralidad=Lateralidad.IZQUIERDA)
    deteccion = replace(crear_deteccion(dominante), manos=(otra, dominante))
    assert ProcesadorVision().interpretar(deteccion).mano is dominante
    duplicada = replace(deteccion, manos=(dominante, dominante))
    assert ProcesadorVision().interpretar(duplicada).estado is EstadoVision.BAJA_CONFIANZA


def test_interrupcion_temporal_invalida_coordenadas(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    procesador.interpretar(crear_deteccion(crear_mano(), 0))
    resultado = procesador.interpretar(crear_deteccion(crear_mano(), 201))
    assert resultado.estado is EstadoVision.MANO_PERDIDA
    assert resultado.posicion_indice is None


def test_rechaza_instantes_repetidos(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    deteccion = crear_deteccion(crear_mano(), 0)
    procesador.interpretar(deteccion)
    with pytest.raises(ValueError, match="aumentar"):
        procesador.interpretar(deteccion)


@pytest.mark.parametrize("fps", [25, 30, 60])
@pytest.mark.parametrize("signo,direccion", [(1, "derecha"), (-1, "izquierda")])
def test_deslizamiento_se_reconoce_a_cadencia_de_video(
    fps, signo, direccion, crear_mano, crear_deteccion
):
    procesador = ProcesadorVision()
    resultados = [
        procesador.interpretar(
            crear_deteccion(
                crear_mano("palma_abierta", delta_x=0.05 + signo * 0.25 * min(instante, 200) / 200),
                instante,
            )
        )
        for instante in (round(i * 1000 / fps) for i in range(round(fps * 1.2) + 1))
    ]
    eventos = [evento for resultado in resultados for evento in resultado.eventos]
    inicios = [evento for evento in eventos if evento.fase is FaseGesto.INICIO]
    assert [evento.nombre for evento in inicios] == [f"deslizamiento_{direccion}"]
    assert 100 <= inicios[0].instante_ms <= 200
    assert all(evento.nombre != "palma_abierta" for evento in eventos)


@pytest.mark.parametrize("postura", ["palma_abierta", "puno"])
def test_movimiento_reinicia_quietud_sin_adelantar_gesto_discreto(
    postura, crear_mano, crear_deteccion
):
    procesador = ProcesadorVision()
    resultados = [
        procesador.interpretar(
            crear_deteccion(crear_mano(postura, delta_x=min(instante, 800) * 0.0001), instante)
        )
        for instante in range(0, 1700, 100)
    ]
    inicios = [
        evento
        for resultado in resultados
        for evento in resultado.eventos
        if evento.fase is FaseGesto.INICIO
    ]
    assert [(evento.nombre, evento.instante_ms) for evento in inicios] == [(postura, 1600)]


def test_deslizamiento_demasiado_breve_no_supera_estabilizacion(crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    resultados = [
        procesador.interpretar(
            crear_deteccion(crear_mano("palma_abierta", delta_x=delta), instante)
        )
        for instante, delta in ((0, 0), (40, 0.13), (80, 0.25))
    ]
    resultados.append(procesador.interpretar(crear_deteccion(crear_mano(), 100)))
    assert all(not resultado.eventos for resultado in resultados)
