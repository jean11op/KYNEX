"""Movimiento corto y accesible; sin bucles ni trabajo en segundo plano."""

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
)


def motion_enabled():
    return QApplication.instance().property('kinexMotion') is not False


class MotionButton(QPushButton):
    """Halo al pasar el puntero y onda breve al pulsar, también con teclado."""
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self._hover = 0.0
        self._ripple = 1.0
        self._origin = QPointF()
        self.hover_animation = QPropertyAnimation(self, b'hoverAmount', self)
        self.hover_animation.setDuration(170)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.ripple_animation = QPropertyAnimation(self, b'rippleAmount', self)
        self.ripple_animation.setDuration(330)
        self.ripple_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.pressed.connect(self.press_feedback)

    def get_hover(self):
        return self._hover

    def set_hover(self, value):
        self._hover = value
        self.update()

    hoverAmount = Property(float, get_hover, set_hover)

    def get_ripple(self):
        return self._ripple

    def set_ripple(self, value):
        self._ripple = value
        self.update()

    rippleAmount = Property(float, get_ripple, set_ripple)

    def animate_hover(self, target):
        self.hover_animation.stop()
        if not motion_enabled():
            self.set_hover(target)
            return
        self.hover_animation.setStartValue(self._hover)
        self.hover_animation.setEndValue(target)
        self.hover_animation.start()

    def enterEvent(self, event):
        if self.isEnabled():
            self.animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_hover(0.0)
        super().leaveEvent(event)

    def press_feedback(self):
        self.ripple_animation.stop()
        if not motion_enabled():
            self.set_ripple(1.0)
            return
        self._origin = QPointF(self.rect().center())
        self.ripple_animation.setStartValue(0.0)
        self.ripple_animation.setEndValue(1.0)
        self.ripple_animation.start()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isEnabled():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        p.setClipPath(path)
        p.fillPath(path, QColor(103, 188, 255, int(22 * self._hover)))
        if self._ripple < 1:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(155, 214, 255, int(42 * (1 - self._ripple))))
            radius = self.width() * self._ripple
            p.drawEllipse(self._origin, radius, radius)


class MotionCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow = 0.0
        self.animation = QPropertyAnimation(self, b'glow', self)
        self.animation.setDuration(220)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_glow(self):
        return self._glow

    def set_glow(self, value):
        self._glow = value
        self.update()

    glow = Property(float, get_glow, set_glow)

    def set_target(self, target):
        self.animation.stop()
        if not motion_enabled():
            self.set_glow(target)
            return
        self.animation.setStartValue(self._glow)
        self.animation.setEndValue(target)
        self.animation.start()

    def enterEvent(self, event):
        self.set_target(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_target(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(111, 188, 238, int(90 * self._glow)), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 18, 18)


class AnimatedStack(QStackedWidget):
    """La página cambia inmediatamente; una instantánea saliente se desvanece."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.overlay = None
        self.transition = None

    def finish_transition(self):
        if self.transition:
            self.transition.stop()
            self.transition.deleteLater()
            self.transition = None
        if self.overlay:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None

    def setCurrentIndex(self, index):
        if index == self.currentIndex():
            return
        self.finish_transition()
        snapshot = self.currentWidget().grab() if self.currentWidget() and self.isVisible() and motion_enabled() else None
        super().setCurrentIndex(index)
        if snapshot is None:
            return
        self.overlay = QLabel(self)
        self.overlay.setPixmap(snapshot)
        self.overlay.setGeometry(self.rect())
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        effect = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b'opacity')
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        slide = QPropertyAnimation(self.overlay, b'pos')
        slide.setStartValue(QPoint(0, 0))
        slide.setEndValue(QPoint(-18, 0))
        self.transition = QParallelAnimationGroup(self)
        for animation in (fade, slide):
            animation.setDuration(240)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.transition.addAnimation(animation)
        self.transition.finished.connect(self.finish_transition)
        self.overlay.show()
        self.overlay.raise_()
        self.transition.start()

    def resizeEvent(self, event):
        self.finish_transition()
        super().resizeEvent(event)

    def hideEvent(self, event):
        self.finish_transition()
        super().hideEvent(event)


class SmoothScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wheel_animation = QPropertyAnimation(self.verticalScrollBar(), b'value', self)
        self.wheel_animation.setDuration(190)
        self.wheel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._target = 0
        self.verticalScrollBar().sliderPressed.connect(self.wheel_animation.stop)

    def wheelEvent(self, event):
        if not motion_enabled() or not event.pixelDelta().isNull() or event.modifiers() or not event.angleDelta().y():
            self.wheel_animation.stop()
            return super().wheelEvent(event)
        bar = self.verticalScrollBar()
        origin = self._target if self.wheel_animation.state() == QPropertyAnimation.State.Running else bar.value()
        self._target = max(bar.minimum(), min(bar.maximum(), origin - event.angleDelta().y()))
        self.wheel_animation.stop()
        self.wheel_animation.setStartValue(bar.value())
        self.wheel_animation.setEndValue(self._target)
        self.wheel_animation.start()
        event.accept()


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('toast')
        self.setWordWrap(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b'opacity', self)
        self.animation.setDuration(200)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, message):
        self.timer.stop()
        self.animation.stop()
        self.setText('✓  ' + message)
        self.setFixedWidth(min(440, self.parentWidget().width() - 50))
        self.adjustSize()
        self.move(self.parentWidget().width() - self.width() - 25, 78)
        self.effect.setOpacity(0.0 if motion_enabled() else 1.0)
        self.show()
        self.raise_()
        if motion_enabled():
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(1.0)
            self.animation.start()
        self.timer.start(2800)
