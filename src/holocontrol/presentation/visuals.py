"""Widgets dibujados por Qt: ilustración, mapa de mano y lienzo manual."""

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget
from holocontrol.presentation.motion import motion_enabled

# Coordenadas editoriales sobre la imagen estática, no detecciones.
POINTS = [(.509, .713), (.584, .662), (.626, .595), (.666, .536), (.699, .498),
          (.574, .474), (.585, .380), (.590, .305), (.589, .262),
          (.528, .458), (.531, .353), (.531, .282), (.528, .225),
          (.482, .480), (.478, .391), (.475, .327), (.470, .271),
          (.456, .543), (.441, .475), (.428, .416), (.418, .365)]
CHAINS = [(0, 1, 2, 3, 4), (0, 5, 6, 7, 8), (5, 9, 10, 11, 12),
          (9, 13, 14, 15, 16), (13, 17, 18, 19, 20), (17, 0)]


class HandPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.image = QPixmap(str(Path(__file__).parent / 'assets' / 'hand-demo.png'))
        self.show_image = True
        self.setMinimumSize(430, 330)
        self.setAccessibleName('Ilustración de una mano. Cámara y reconocimiento no conectados.')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 18, 18)
        p.setClipPath(clip)
        p.fillRect(self.rect(), QColor('#11171c'))
        if self.show_image and not self.image.isNull():
            scale = max(w / self.image.width(), h / self.image.height())
            iw, ih = self.image.width() * scale, self.image.height() * scale
            ox, oy = (w - iw) / 2, (h - ih) / 2
            p.drawPixmap(QRectF(ox, oy, iw, ih), self.image, QRectF(self.image.rect()))
            p.fillRect(self.rect(), QColor(0, 5, 9, 60))
            p.setPen(QPen(QColor(175, 208, 230, 30), 1))
            for i in range(1, 4):
                p.drawLine(QPointF(w * i / 4, 0), QPointF(w * i / 4, h))
                p.drawLine(QPointF(0, h * i / 4), QPointF(w, h * i / 4))
            coords = [QPointF(ox + x * iw, oy + y * ih) for x, y in POINTS]
            p.setPen(QPen(QColor(128, 192, 244, 170), 1))
            for chain in CHAINS:
                for a, b in zip(chain, chain[1:]):
                    p.drawLine(coords[a], coords[b])
            for point in coords:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(56, 161, 254, 55))
                p.drawEllipse(point, 7, 7)
                p.setBrush(QColor('#95d0ff'))
                p.drawEllipse(point, 2.5, 2.5)
            bounds = QRectF(ox + .397 * iw, oy + .19 * ih, .32 * iw, .56 * ih)
            p.setPen(QPen(QColor('#79bfff'), 2))
            for x, y, dx, dy in [(bounds.left(), bounds.top(), 1, 1), (bounds.right(), bounds.top(), -1, 1), (bounds.left(), bounds.bottom(), 1, -1), (bounds.right(), bounds.bottom(), -1, -1)]:
                p.drawLine(QPointF(x, y), QPointF(x + dx * 16, y))
                p.drawLine(QPointF(x, y), QPointF(x, y + dy * 16))
        else:
            p.setPen(QColor('#9aabba'))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Vista previa oculta\nEl control permanece detenido')
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 12, 16, 200))
        p.drawRoundedRect(QRectF(16, 16, 82, 30), 7, 7)
        p.drawRoundedRect(QRectF(w - 186, 16, 170, 30), 7, 7)
        p.drawRoundedRect(QRectF(16, h * .39, 112, 115), 8, 8)
        p.setPen(QColor('#cdd7de'))
        p.setFont(QFont('Segoe UI', 9))
        p.drawText(QRectF(16, 16, 82, 30), Qt.AlignmentFlag.AlignCenter, 'HD  ·  DEMO')
        p.drawText(QRectF(w - 186, 16, 170, 30), Qt.AlignmentFlag.AlignCenter, '●  IMAGEN ILUSTRATIVA')
        p.setFont(QFont('Segoe UI', 8))
        p.drawText(21, 73, '— FPS')
        p.drawText(21, 92, 'Sin señal de cámara')
        y = h * .39
        p.drawText(QRectF(24, y + 13, 100, 20), 'GESTO DE EJEMPLO')
        p.setPen(QPen(QColor('#dbe7ee'), 1.5))
        for i in range(4):
            p.drawLine(QPointF(51 + i * 7, y + 61), QPointF(51 + i * 7, y + 39 - (i % 3) * 3))
        p.drawArc(QRectF(47, y + 49, 32, 29), 180 * 16, 180 * 16)
        p.setFont(QFont('Segoe UI', 9))
        p.drawText(QRectF(24, y + 85, 100, 20), 'Mano abierta')
        p.setPen(QColor('#c5d2df'))
        p.drawText(QRectF(18, h - 30, w - 36, 20), 'ILUSTRACIÓN  ·  No hay detección activa')


class SensitivityDial(QWidget):
    def __init__(self):
        super().__init__()
        self._value = 100
        self._display_value = 100.0
        self.animation = QPropertyAnimation(self, b'displayValue', self)
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setMinimumSize(135, 135)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
        self.animation.stop()
        if not motion_enabled() or not self.isVisible():
            self.set_display_value(float(value))
            return
        self.animation.setStartValue(self._display_value)
        self.animation.setEndValue(float(value))
        self.animation.start()

    def get_display_value(self):
        return self._display_value

    def set_display_value(self, value):
        self._display_value = value
        self.update()

    displayValue = Property(float, get_display_value, set_display_value)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(side / 160, side / 160)
        p.setBrush(QColor('#10161c'))
        p.setPen(QPen(QColor('#264459'), 1))
        p.drawEllipse(QPointF(0, 0), 67, 67)
        for i in range(45):
            p.save()
            p.rotate(-135 + i * 6)
            p.setPen(QColor('#65b9ff' if i < self._display_value / 200 * 45 else '#35434c'))
            p.drawLine(0, -58, 0, -53)
            p.restore()
        p.setFont(QFont('Segoe UI', 20, QFont.Weight.DemiBold))
        p.setPen(QColor('#eff7ff'))
        p.drawText(QRectF(-55, -15, 110, 30), Qt.AlignmentFlag.AlignCenter, f'{self._display_value / 100:.2g}×')
        p.setFont(QFont('Segoe UI', 8))
        p.setPen(QColor('#b5c5d2'))
        p.drawText(QRectF(-60, 20, 120, 20), Qt.AlignmentFlag.AlignCenter, 'Sensibilidad')


class HandMap(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(120, 145)
        self.setAccessibleName('Mapa de mano ilustrativo, sin datos de reconocimiento')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#0d141a'))
        p.setPen(QColor('#1a2a36'))
        for x in range(0, self.width(), 12):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 12):
            p.drawLine(0, y, self.width(), y)
        coords = [QPointF((x - .38) / .35 * self.width(), (y - .18) / .59 * self.height()) for x, y in POINTS]
        for chain in CHAINS:
            for a, b in zip(chain, chain[1:]):
                for i in range(9):
                    point = coords[a] + (coords[b] - coords[a]) * i / 8
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(47, 152, 255, 45))
                    p.drawEllipse(point, 6, 6)
                    p.setBrush(QColor('#78c2ff'))
                    p.drawEllipse(point, 1.5, 1.5)


class DrawingCanvas(QWidget):
    """Lienzo manual; el motor podrá entregar puntos mediante una integración futura."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(500, 330)
        self.setAccessibleName('Lienzo de dibujo manual')
        self.color = QColor('#249bff')
        self.width_value = 4
        self.strokes = []
        self.current = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.current = (self.color.name(), self.width_value, [event.position()])
            self.update()

    def mouseMoveEvent(self, event):
        if self.current and event.buttons() & Qt.MouseButton.LeftButton:
            self.current[2].append(event.position())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.current and event.button() == Qt.MouseButton.LeftButton:
            self.strokes.append(self.current)
            self.current = None
            self.update()

    def render_strokes(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for color, width, points in self.strokes + ([self.current] if self.current else []):
            painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            if len(points) == 1:
                painter.drawPoint(points[0])
            for a, b in zip(points, points[1:]):
                painter.drawLine(a, b)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#f5f7fa'))
        self.render_strokes(p)

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.update()

    def clear(self):
        self.strokes.clear()
        self.current = None
        self.update()

    def export(self, path):
        image = QImage(self.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor('#f5f7fa'))
        p = QPainter(image)
        self.render_strokes(p)
        p.end()
        return image.save(str(path), 'PNG')
