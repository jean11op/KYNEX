"""Widgets dibujados por Qt: ilustración, mapa de mano y lienzo manual."""

from itertools import pairwise

from PySide6.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
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
        self.show_image = True
        self.live_image = QImage()
        self.live_mode = False
        self.landmarks = ()
        self.setMinimumSize(430, 330)
        self.setAccessibleName('Ilustración de una mano. Cámara y reconocimiento no conectados.')

    def set_camera_frame(self, frame, active=True):
        self.live_mode = active
        self.live_image = QImage()
        self.landmarks = ()
        if frame is not None:
            image = frame.imagen
            height, width = image.shape[:2]
            self.live_image = QImage(image.data, width, height, image.strides[0], QImage.Format.Format_BGR888).copy()
        self.setAccessibleName('Vista de cámara' if active else 'Cámara detenida')
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 18, 18)
        p.setClipPath(clip)
        p.fillRect(self.rect(), QColor('#11171c'))
        if self.live_mode:
            if self.show_image and not self.live_image.isNull():
                scaled = self.live_image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
                ox, oy = (w - scaled.width()) // 2, (h - scaled.height()) // 2
                coords = [QPointF(ox + point.x * scaled.width(), oy + point.y * scaled.height()) for point in self.landmarks]
                if len(coords) == 21:
                    p.setPen(QPen(QColor('#56e7a0'), 2))
                    for chain in CHAINS:
                        for a, b in pairwise(chain):
                            p.drawLine(coords[a], coords[b])
                    p.setBrush(QColor('#91d5ff'))
                    for point in coords:
                        p.drawEllipse(point, 3, 3)
            else:
                p.setPen(QColor('#c5d2df'))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Esperando imagen de cámara' if self.show_image else 'Vista previa oculta')
            return
        p.translate(w / 2, h / 2 - 12)
        p.setPen(QPen(QColor('#6d8599'), 3))
        p.setBrush(QColor('#17222e'))
        p.drawRoundedRect(QRectF(-42, -25, 84, 55), 10, 10)
        p.drawRoundedRect(QRectF(-20, -35, 40, 12), 4, 4)
        p.setBrush(QColor('#11171c'))
        p.drawEllipse(QPointF(0, 2), 16, 16)
        p.resetTransform()
        p.setPen(QColor('#9caebe'))
        p.setFont(QFont('Segoe UI', 11))
        p.drawText(QRectF(0, h / 2 + 38, w, 30), Qt.AlignmentFlag.AlignCenter, 'C?mara apagada')


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
            for a, b in pairwise(chain):
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
            for a, b in pairwise(points):
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
