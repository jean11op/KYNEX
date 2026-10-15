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
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == ([('puno', 2000)] if selected is side else [])


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
def test_other_hand_never_controls(side, gesture, expected, wait, crear_mano, crear_deteccion):
    selected = Lateralidad.IZQUIERDA if side is Lateralidad.DERECHA else Lateralidad.DERECHA
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=selected))
    hand = crear_mano(gesture, lateralidad=side)
    if side is Lateralidad.IZQUIERDA:
        hand = replace(hand, puntos=tuple(replace(p, x=1-p.x) for p in hand.puntos))
    events = [e for t in range(0, wait+301, 100)
              for e in processor.interpretar(crear_deteccion(hand,t)).eventos]
    assert [(e.nombre,e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == []


@pytest.mark.parametrize('side', list(Lateralidad))
def test_gun_moves_continuously_and_releases_on_hand_change(side, crear_mano, crear_deteccion):
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=side))
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


@pytest.mark.parametrize('side', list(Lateralidad))
def test_other_hand_peace_sign_cannot_interrupt_selected_fist(side, crear_mano, crear_deteccion):
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=side))
    fist = crear_mano('puno', lateralidad=side)
    other = Lateralidad.IZQUIERDA if side is Lateralidad.DERECHA else Lateralidad.DERECHA
    peace = crear_mano('dos_dedos', lateralidad=other)
    events = []
    for t in range(0, 2500, 50):
        detection = crear_deteccion(fist, t)
        if t >= 500:
            detection = replace(detection, manos=(peace, fist) if t % 100 else (fist, peace))
        result = processor.interpretar(detection)
        assert result.es_valido and result.mano is fist
        events.extend(result.eventos)
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [('puno', 2000)]
    result = processor.interpretar(crear_deteccion(peace, 2500))
    assert not result.es_valido
    assert all(e.fase is FaseGesto.FIN for e in result.eventos)
    assert processor.interpretar(crear_deteccion(fist, 2550)).es_valido


@pytest.mark.parametrize('side', list(Lateralidad))
@pytest.mark.parametrize('glitch', ['label', 'confidence'])
def test_fist_timer_survives_brief_handedness_uncertainty(side, glitch, crear_mano, crear_deteccion):
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=side))
    hand = crear_mano('puno', lateralidad=side)
    other = Lateralidad.IZQUIERDA if side is Lateralidad.DERECHA else Lateralidad.DERECHA
    events = []
    for t in range(0, 2300, 50):
        current = hand
        if t in (500, 1000, 1500, 1950):
            current = (replace(hand, lateralidad=other) if glitch == 'label'
                       else replace(hand, confianza_lateralidad=.51))
        result = processor.interpretar(crear_deteccion(current, t))
        if current is not hand:
            assert not result.es_valido and not result.eventos
            assert result.posicion_indice is None
        events.extend(result.eventos)
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [('puno', 2000)]


def test_other_hand_cannot_complete_pending_fist(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    hand = crear_mano('puno')
    for t in range(0, 1900, 50):
        processor.interpretar(crear_deteccion(hand, t))
    other = replace(hand, lateralidad=Lateralidad.IZQUIERDA)
    for t in range(1900, 2400, 50):
        result = processor.interpretar(crear_deteccion(other, t))
        assert not result.es_valido and not result.eventos
    for t in range(2400, 4400, 50):
        result = processor.interpretar(crear_deteccion(hand, t))
        assert not result.eventos
    result = processor.interpretar(crear_deteccion(hand, 4400))
    assert [(e.nombre, e.fase) for e in result.eventos] == [('puno', FaseGesto.INICIO)]


@pytest.mark.parametrize('side', list(Lateralidad))
@pytest.mark.parametrize('turns,expected,delay', [(0, 'menique', 500), (1, 'pulgar_abajo', 250), (2, None, 0), (3, None, 0)])
def test_little_finger_direction_selects_enter_or_delete(side, turns, expected, delay, crear_mano, crear_deteccion):
    processor = ProcesadorVision(ConfiguracionVision(mano_dominante=side))
    hand = crear_mano('menique', lateralidad=side)
    if side is Lateralidad.IZQUIERDA:
        hand = replace(hand, puntos=tuple(replace(p, x=1-p.x) for p in hand.puntos))
    for _ in range(turns):
        hand = replace(hand, puntos=tuple(replace(p, x=p.y, y=1-p.x) for p in hand.puntos))
    events = [e for t in range(0, 2600, 50)
              for e in processor.interpretar(crear_deteccion(hand, t)).eventos]
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == (
        [(expected, delay)] if expected else [])


def test_ring_and_little_finger_no_longer_delete(crear_mano, crear_deteccion):
    processor = ProcesadorVision()
    events = [e for t in range(0, 2600, 50)
              for e in processor.interpretar(crear_deteccion(crear_mano('borrar'), t)).eventos]
    assert not any(e.nombre == 'pulgar_abajo' for e in events)


def test_rotating_delete_to_enter_releases_before_new_command(crear_mano, crear_deteccion):
    from math import sqrt
    processor = ProcesadorVision()
    up = crear_mano('menique')
    left = replace(up, puntos=tuple(replace(p, x=p.y, y=1-p.x) for p in up.puntos))
    diagonal = replace(up, puntos=tuple(replace(
        p, x=.5 + ((p.x-.5)+(p.y-.5))/sqrt(2),
        y=.5 + (-(p.x-.5)+(p.y-.5))/sqrt(2)) for p in up.puntos))
    for t in range(0, 300, 50):
        processor.interpretar(crear_deteccion(left, t))
    result = processor.interpretar(crear_deteccion(diagonal, 300))
    assert [(e.nombre, e.fase) for e in result.eventos] == [('pulgar_abajo', FaseGesto.FIN)]
    events = [e for t in range(350, 1000, 50)
              for e in processor.interpretar(crear_deteccion(up, t)).eventos]
    assert [(e.nombre, e.instante_ms) for e in events if e.fase is FaseGesto.INICIO] == [('menique', 850)]


def test_old_thumb_down_no_longer_deletes(crear_mano, crear_deteccion):
    hand = crear_mano('puno')
    points = list(hand.puntos)
    for i, y in ((2, .62), (3, .79), (4, .96)):
        points[i] = replace(points[i], x=.30, y=y)
    hand = replace(hand, puntos=tuple(points))
    processor = ProcesadorVision()
    events = [e for t in range(0, 2600, 50)
              for e in processor.interpretar(crear_deteccion(hand, t)).eventos]
    assert not any(e.nombre == 'pulgar_abajo' for e in events)


@pytest.mark.parametrize('turns,expected', [(0,'up'), (1,'right'), (2,'down'), (3,'left')])
def test_two_finger_pointing_maps_to_four_arrows(turns, expected, crear_mano, crear_deteccion):
    from holocontrol.application.dto.reconocimiento import Reconocimiento
    hand = crear_mano('dos_dedos')
    for _ in range(turns):
        hand = replace(hand, puntos=tuple(replace(p, x=1-p.y, y=p.x) for p in hand.puntos))
    processor = ProcesadorVision()
    processor.interpretar(crear_deteccion(hand, 0))
    result = processor.interpretar(crear_deteccion(hand, 100))
    assert result.eventos[0].nombre == 'dos_dedos'
    assert Reconocimiento.desde_vision(result, 1).direccion_flechas == expected
