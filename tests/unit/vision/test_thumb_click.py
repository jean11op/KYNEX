from dataclasses import replace

import pytest

from holocontrol.infrastructure.vision.vision_processor import ProcesadorVision
from holocontrol.ports.vision.models import FaseGesto


def thumb(hand, opening, mirror=False):
    points = list(hand.puntos)
    points[4] = replace(points[4], x=.42-opening*.24, y=.57)
    if mirror:
        points = [replace(p, x=1-p.x) for p in points]
    return replace(hand, puntos=tuple(points))


@pytest.mark.parametrize('mirror', [False, True])
def test_one_click_on_close_with_no_cursor_during_thumb_motion(crear_mano, crear_deteccion, mirror):
    processor = ProcesadorVision()
    hand = crear_mano()
    results = []
    for time, opening in [(0,.1),(100,.1),(150,.65),(220,.65),(280,.65),(320,.1),(370,.1),(420,.1),(520,.1)]:
        results.append(processor.interpretar(crear_deteccion(thumb(hand, opening, mirror), time)))
    clicks = [(r.instante_ms,e) for r in results for e in r.eventos if e.nombre == 'pulgar']
    assert [(t,e.fase) for t,e in clicks] == [(370,FaseGesto.INICIO),(370,FaseGesto.FIN)]
    assert not any(e.nombre == 'indice' and e.fase != FaseGesto.FIN for r in results[2:7] for e in r.eventos)
    assert results[-1].eventos[0].nombre == 'indice'


def test_open_on_entry_then_close_does_not_click(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano()
    for t, opening in [(0,.7),(100,.7),(150,.1),(200,.1)]:
        result = processor.interpretar(crear_deteccion(thumb(hand,opening),t))
        assert not any(e.nombre == 'pulgar' for e in result.eventos)


def test_lost_hand_cancels_pending_click(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano()
    for t, opening in [(0,.1),(100,.1),(150,.7),(220,.7)]:
        processor.interpretar(crear_deteccion(thumb(hand,opening),t))
    processor.interpretar(crear_deteccion(instante=250))
    for t in (300,400,500):
        result = processor.interpretar(crear_deteccion(thumb(hand,.1),t))
        assert not any(e.nombre == 'pulgar' for e in result.eventos)


def test_pinch_is_not_a_thumb_click(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano()
    for t, opening in [(0,.1),(100,.1),(150,.7),(220,.7)]:
        processor.interpretar(crear_deteccion(thumb(hand,opening),t))
    for t in (250,350,450):
        result = processor.interpretar(crear_deteccion(crear_mano('pellizco'),t))
        assert not any(e.nombre == 'pulgar' for e in result.eventos)


def test_real_pipeline_clicks_at_previous_cursor_position(crear_mano, crear_deteccion):
    from holocontrol.application.dto.reconocimiento import Reconocimiento
    from holocontrol.application.use_cases import AplicacionControl
    from holocontrol.domain.entities import Calibracion
    from tests.soporte import EjecutorRegistro, RelojSimulado, RepositorioPerfilesMemoria
    clock = RelojSimulado()
    executor = EjecutorRegistro()
    app = AplicacionControl(RepositorioPerfilesMemoria(), executor, clock)
    profile = app.crear_perfil('Thumb')
    app.seleccionar_perfil(profile.id)
    app.calibrar_perfil(Calibracion(profile.id))
    state = app.iniciar_control(camara_disponible=True, ancho_pantalla=1920, alto_pantalla=1080)
    processor = ProcesadorVision()
    hand = crear_mano()
    for t, opening in [(0,.1),(100,.1),(150,.65),(220,.65),(300,.1),(350,.1)]:
        current = thumb(hand,opening)
        if t >= 150:
            current = replace(current, puntos=tuple(replace(p, x=p.x+.01, y=p.y+.01) for p in current.puntos))
        clock.ahora = (100000+t)/1000
        result = processor.interpretar(crear_deteccion(current,100000+t))
        app.procesar_reconocimiento(Reconocimiento.desde_vision(result,state.generacion))
    assert len(executor.llamadas) == 2
    assert executor.llamadas[0][0] == 'mover'
    assert executor.llamadas[1] == ('clic_izquierdo',)


def test_lateral_motion_of_whole_hand_does_not_click(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano()
    for t, offset in [(0,0),(100,0),(150,.1),(220,.1),(300,0),(350,0)]:
        current = thumb(hand,.1)
        current = replace(current, puntos=tuple(replace(p,x=p.x+offset) for p in current.puntos))
        result = processor.interpretar(crear_deteccion(current,t))
        assert not any(e.nombre == 'pulgar' for e in result.eventos)


@pytest.mark.parametrize('mirror', [False, True])
def test_held_thumb_drags_until_hidden_without_extra_click(crear_mano, crear_deteccion, mirror):
    processor = ProcesadorVision()
    hand = crear_mano()
    events = []
    for t in range(0, 2300, 50):
        opening = .1 if t < 150 or t >= 2100 else .65
        current = thumb(hand, opening, mirror)
        if 700 <= t < 2100:
            current = replace(current, puntos=tuple(replace(p, y=p.y-.1) for p in current.puntos))
        events.extend(processor.interpretar(crear_deteccion(current, t)).eventos)
    drag = [e for e in events if e.nombre == 'pellizco']
    assert [e.fase for e in drag].count(FaseGesto.INICIO) == 1
    assert any(e.fase is FaseGesto.MANTENIMIENTO and e.instante_ms == 2000 for e in drag)
    assert [(e.fase, e.instante_ms) for e in drag if e.fase is FaseGesto.FIN] == [(FaseGesto.FIN, 2100)]
    assert not any(e.nombre == 'pulgar' for e in events)


def test_losing_hand_releases_held_thumb(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano()
    for t in range(0, 1000, 50):
        processor.interpretar(crear_deteccion(thumb(hand, .1 if t < 150 else .65), t))
    result = processor.interpretar(crear_deteccion(instante=1000))
    assert [(e.nombre, e.fase) for e in result.eventos] == [('pellizco', FaseGesto.FIN)]
