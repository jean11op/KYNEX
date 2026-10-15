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


def test_pistola_sostenida_y_fin_inmediato(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    results = [processor.interpretar(crear_deteccion(crear_mano('pistola'), t))
               for t in (0, 100, 180)]
    assert not results[0].eventos
    assert [(e.nombre, e.fase) for e in results[1].eventos] == [('pellizco', FaseGesto.INICIO)]
    assert results[2].eventos[0].fase is FaseGesto.MANTENIMIENTO
    released = processor.interpretar(crear_deteccion(crear_mano('indice'), 200))
    assert released.eventos[0].fase is FaseGesto.FIN
    assert not any(e.nombre == 'pulgar' for e in released.eventos)


def test_old_pinch_does_not_start_drag(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    for t in range(0, 2000, 100):
        result = processor.interpretar(crear_deteccion(crear_mano('pellizco'), t))
        assert all(e.nombre != 'pellizco' for e in result.eventos)


def test_loss_releases_gun_drag(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    for t in (0, 100, 150):
        processor.interpretar(crear_deteccion(crear_mano('pistola'), t))
    lost = processor.interpretar(crear_deteccion(instante=180))
    assert lost.estado is EstadoVision.MANO_PERDIDA
    assert [(e.nombre, e.fase) for e in lost.eventos] == [('pellizco', FaseGesto.FIN)]


@pytest.mark.parametrize("postura", ["palma_abierta", "puno"])
def test_gesto_discreto_respeta_su_duracion_y_no_se_repite(postura, crear_mano, crear_deteccion):
    procesador = ProcesadorVision()
    resultados = [
        procesador.interpretar(crear_deteccion(crear_mano(postura), instante))
        for instante in range(0, 7500, 100)
    ]
    inicios = [
        evento for r in resultados for evento in r.eventos if evento.fase is FaseGesto.INICIO
    ]
    assert len(inicios) == 1
    assert inicios[0].nombre == postura and inicios[0].instante_ms == (7000 if postura == "palma_abierta" else 2000)


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
        (Lateralidad.IZQUIERDA, 0.4, EstadoVision.BAJA_CONFIANZA),
        (Lateralidad.DERECHA, 0.4, EstadoVision.BAJA_CONFIANZA),
    ],
)
def test_single_hand_does_not_require_certain_handedness(
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
    assert resultado.estado is EstadoVision.MANO_DETECTADA and resultado.es_valido
    assert resultado.posicion_indice is not None


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
def test_movimiento_no_reinicia_la_postura_sostenida(
    postura, crear_mano, crear_deteccion
):
    procesador = ProcesadorVision()
    resultados = [
        procesador.interpretar(
            crear_deteccion(crear_mano(postura, delta_x=min(instante, 800) * 0.0001), instante)
        )
        for instante in range(0, 7500, 100)
    ]
    inicios = [
        evento
        for resultado in resultados
        for evento in resultado.eventos
        if evento.fase is FaseGesto.INICIO
    ]
    assert [(evento.nombre, evento.instante_ms) for evento in inicios] == [(postura, 7000 if postura == "palma_abierta" else 2000)]


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


def test_three_fingers_start_move_and_lower(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    processor.interpretar(crear_deteccion(crear_mano("tres_dedos"), 0))
    started = processor.interpretar(crear_deteccion(crear_mano("tres_dedos"), 100))
    assert [(e.nombre, e.fase) for e in started.eventos] == [("tres_dedos", FaseGesto.INICIO)]
    moved = processor.interpretar(crear_deteccion(crear_mano("tres_dedos", delta_x=.1), 150))
    assert moved.eventos[0].fase is FaseGesto.MANTENIMIENTO
    ended = processor.interpretar(crear_deteccion(crear_mano("puno"), 200))
    assert ended.eventos[0].fase is FaseGesto.FIN


def test_fist_with_thumb_touching_index_is_not_pinch(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano("puno")
    points = list(hand.puntos)
    points[4] = replace(points[4], x=points[8].x, y=points[8].y)
    hand = replace(hand, puntos=tuple(points))
    results = [processor.interpretar(crear_deteccion(hand, t)) for t in range(0, 2500, 100)]
    assert any(e.nombre == "puno" and e.fase is FaseGesto.INICIO for r in results for e in r.eventos)
    assert all(e.nombre != "pellizco" for r in results for e in r.eventos)


def test_three_fingers_survive_motion_and_brief_uncertainty(crear_mano, crear_deteccion, monkeypatch):
    processor = ProcesadorVision()
    hand = crear_mano("tres_dedos")
    processor.interpretar(crear_deteccion(hand, 0))
    processor.interpretar(crear_deteccion(hand, 100))
    # A marginal classification while moving must not release Alt.
    monkeypatch.setattr(processor._reconocedor, '_clasificar', lambda *args: (None, 0))
    for t in (140, 180, 220, 260, 300):
        result = processor.interpretar(crear_deteccion(crear_mano("tres_dedos", delta_x=.1), t))
        assert [(e.nombre, e.fase) for e in result.eventos] == [("tres_dedos", FaseGesto.MANTENIMIENTO)]


@pytest.mark.parametrize('up', [True, False])
def test_scroll_direction_comes_from_two_fingers_orientation(crear_mano, crear_deteccion, up):
    from holocontrol.application.dto.reconocimiento import Reconocimiento
    hand = crear_mano('dos_dedos')
    if not up:
        hand = replace(hand, puntos=tuple(replace(p, y=1 - p.y) for p in hand.puntos))
    processor = ProcesadorVision()
    processor.interpretar(crear_deteccion(hand, 0))
    result = processor.interpretar(crear_deteccion(hand, 100))
    assert result.eventos[0].nombre == 'dos_dedos'
    dto = Reconocimiento.desde_vision(result, 1)
    assert dto.direccion_scroll == (1 if up else -1)
