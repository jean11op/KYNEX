from dataclasses import replace

from holocontrol.infrastructure.vision.vision_processor import ProcesadorVision
from holocontrol.ports.vision.models import FaseGesto


def test_palm_waits_seven_seconds_and_resets_on_gesture_change(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    palm = crear_mano('palma_abierta')
    for t in range(0,7000,100):
        result = processor.interpretar(crear_deteccion(palm,t))
        assert not any(e.nombre == 'palma_abierta' and e.fase is FaseGesto.INICIO for e in result.eventos)
    result = processor.interpretar(crear_deteccion(palm,7000))
    assert [(e.nombre,e.fase) for e in result.eventos] == [('palma_abierta',FaseGesto.INICIO)]
    processor.interpretar(crear_deteccion(crear_mano('indice'),7100))
    for t in range(7200,14200,100):
        result = processor.interpretar(crear_deteccion(palm,t))
        assert not any(e.nombre == 'palma_abierta' and e.fase is FaseGesto.INICIO for e in result.eventos)


def test_like_is_not_fist_and_fires_once_per_hold(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano('puno')
    points = list(hand.puntos)
    for index,y in [(2,.62),(3,.45),(4,.28)]:
        points[index] = replace(points[index],x=.30,y=y)
    hand = replace(hand,puntos=tuple(points))
    events = [e for t in range(0,1200,50) for e in processor.interpretar(crear_deteccion(hand,t)).eventos]
    assert [(e.nombre,e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [('like',250)]
    assert all(e.nombre != 'puno' for e in events)


def test_two_finger_spread_enters_zoom_until_posture_changes(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano('dos_dedos')
    processor.interpretar(crear_deteccion(hand,0))
    processor.interpretar(crear_deteccion(hand,100))
    points = list(hand.puntos)
    # Translate both extended fingers in opposite directions: center stays still.
    for i in range(5,9):
        points[i] = replace(points[i],x=points[i].x-.05)
    for i in range(9,13):
        points[i] = replace(points[i],x=points[i].x+.05)
    spread = replace(hand,puntos=tuple(points))
    processor.interpretar(crear_deteccion(spread,150))
    result = processor.interpretar(crear_deteccion(spread,250))
    assert any(e.nombre == 'zoom' and e.fase is FaseGesto.INICIO for e in result.eventos)
    result = processor.interpretar(crear_deteccion(hand,300))
    assert any(e.nombre == 'zoom' and e.fase is FaseGesto.MANTENIMIENTO for e in result.eventos)
    result = processor.interpretar(crear_deteccion(crear_mano('indice'),350))
    assert any(e.nombre == 'zoom' and e.fase is FaseGesto.FIN for e in result.eventos)


def test_lowering_like_does_not_minimize_typing_window(crear_mano, crear_deteccion):
    processor=ProcesadorVision()
    hand=crear_mano('puno')
    points=list(hand.puntos)
    for i,y in [(2,.62),(3,.45),(4,.28)]:
        points[i]=replace(points[i],x=.30,y=y)
    like=replace(hand,puntos=tuple(points))
    for t in range(0,400,50):
        processor.interpretar(crear_deteccion(like,t))
    for t in range(400,1400,50):
        result=processor.interpretar(crear_deteccion(hand,t))
        assert not any(e.nombre == 'puno' and e.fase is FaseGesto.INICIO for e in result.eventos)


import pytest
from holocontrol.ports.vision.models import Lateralidad
from holocontrol.infrastructure.vision.configuration import ConfiguracionVision


@pytest.mark.parametrize('selected', list(Lateralidad))
@pytest.mark.parametrize('side', list(Lateralidad))
def test_fist_both_hands_two_seconds_once(selected, side, crear_mano, crear_deteccion):
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=selected))
    hand = crear_mano('puno', lateralidad=side)
    if side is Lateralidad.IZQUIERDA:
        hand = replace(hand, puntos=tuple(replace(p, x=1-p.x) for p in hand.puntos))
    events = [e for t in range(0, 3000, 100)
              for e in processor.interpretar(crear_deteccion(hand, t)).eventos]
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [('puno', 2000)]


@pytest.mark.parametrize('interruption', ['open', 'lost'])
def test_fist_timer_restarts_after_interruption(interruption, crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    fist = crear_mano('puno')
    for t in range(0, 1900, 100):
        assert not processor.interpretar(crear_deteccion(fist, t)).eventos
    processor.interpretar(crear_deteccion(crear_mano('indice') if interruption == 'open' else None, 1900))
    events = [e for t in range(2000, 4100, 100)
              for e in processor.interpretar(crear_deteccion(fist, t)).eventos]
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [('puno', 4000)]


@pytest.mark.parametrize('gesture', ['menique', 'cuernos'])
@pytest.mark.parametrize('side', list(Lateralidad))
def test_keyboard_postures_confirm_once_after_half_second(gesture, side, crear_mano, crear_deteccion):
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=side))
    hand = crear_mano(gesture, lateralidad=side)
    if side is Lateralidad.IZQUIERDA:
        hand = replace(hand, puntos=tuple(replace(p, x=1-p.x) for p in hand.puntos))
    events = [e for t in range(0, 1500, 100)
              for e in processor.interpretar(crear_deteccion(hand, t)).eventos]
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [(gesture, 500)]


@pytest.mark.parametrize('side', list(Lateralidad))
@pytest.mark.parametrize('gesture,expected,wait', [
    ('indice','indice',100), ('dos_dedos','dos_dedos',100),
    ('tres_dedos','tres_dedos',100), ('puno','puno',2000),
    ('menique','menique',500), ('cuernos','cuernos',500),
    ('palma_abierta','palma_abierta',7000), ('pistola','pellizco',100),
])
def test_all_postures_work_even_if_profile_selects_other_hand(side, gesture, expected, wait, crear_mano, crear_deteccion):
    selected = Lateralidad.IZQUIERDA if side is Lateralidad.DERECHA else Lateralidad.DERECHA
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=selected))
    hand = crear_mano(gesture, lateralidad=side)
    if side is Lateralidad.IZQUIERDA:
        hand = replace(hand, puntos=tuple(replace(p, x=1-p.x) for p in hand.puntos))
    events = [e for t in range(0, wait+301, 100)
              for e in processor.interpretar(crear_deteccion(hand,t)).eventos]
    assert [(e.nombre,e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [(expected,wait)]


@pytest.mark.parametrize('side', list(Lateralidad))
def test_gun_moves_continuously_and_releases_on_hand_change(side, crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano('pistola', lateralidad=side)
    for t in (0,100,200):
        processor.interpretar(crear_deteccion(hand,t))
    moved = replace(hand, puntos=tuple(replace(p,y=p.y-.05) for p in hand.puntos))
    result = processor.interpretar(crear_deteccion(moved,300))
    assert result.eventos[0].nombre == 'pellizco'
    assert result.eventos[0].fase is FaseGesto.MANTENIMIENTO
    other = Lateralidad.IZQUIERDA if side is Lateralidad.DERECHA else Lateralidad.DERECHA
    result = processor.interpretar(crear_deteccion(replace(moved,lateralidad=other),400))
    assert [(e.nombre,e.fase) for e in result.eventos] == [('pellizco',FaseGesto.FIN)]
