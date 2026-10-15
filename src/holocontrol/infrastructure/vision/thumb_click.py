"""A deliberate closed/open/closed thumb cycle with a stationary index."""
from holocontrol.infrastructure.vision.geometry import coordenadas_mano, distancia, puntuaciones_dedos


class ThumbClick:
    def __init__(self):
        self.reset()

    def reset(self):
        self.ready = False
        self.opened_at = None
        self.closed_at = None
        self.anchor = None
        self.locked = False
        self.open_confirmed = False
        self.held = False
        self.moved = False

    def update(self, hand, timestamp, aspect):
        points = coordenadas_mano(hand, aspect)
        width = distancia(points[5], points[17])
        index, middle, ring, little = puntuaciones_dedos(points)
        if width < .02 or min(index, 1-middle, 1-ring, 1-little) < .6:
            self.reset()
            return False, False
        lateral = tuple((a-b)/width for a,b in zip(points[5], points[17]))
        opening = sum((a-b)*c for a,b,c in zip(points[4], points[5], lateral))/width
        # Pinching toward the index tip must never complete a lateral thumb click.
        if distancia(points[4], points[8]) < width * .5:
            self.reset()
            return False, False
        closed = opening <= .30
        if not self.locked:
            if closed:
                self.ready = True
            if self.ready and opening >= .40:
                self.locked = True
                self.anchor = (hand.puntos[8].x, hand.puntos[8].y)
                self.opened_at = timestamp
            else:
                return False, False
        tip = (hand.puntos[8].x, hand.puntos[8].y)
        if distancia(tip, self.anchor) > .06:
            self.moved = True
        if opening >= .50 and timestamp-self.opened_at >= 60:
            self.open_confirmed = True
        if not closed and self.open_confirmed and timestamp-self.opened_at >= 400:
            self.held = True
        if self.held:
            if closed:
                self.reset()
                self.ready = True
            return False, False
        if closed:
            if self.closed_at is None:
                self.closed_at = timestamp
            if timestamp-self.closed_at >= 40:
                clicked = self.open_confirmed and not self.moved
                self.reset()
                self.ready = True
                return True, clicked
        else:
            self.closed_at = None
        return True, False
