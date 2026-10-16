"""Iconografía Phosphor de QtAwesome, compatible con PySide6."""
import qtawesome as qta
from PySide6.QtGui import QIcon

_NAMES = {
    'home': 'ph.house', 'profile': 'ph.user-circle', 'target': 'ph.crosshair',
    'dashboard': 'ph.hand', 'image': 'ph.paint-brush', 'chart': 'ph.chart-bar',
    'settings': 'ph.sliders-horizontal', 'info': 'ph.info', 'power': 'ph.power',
    'minimize': 'ph.minus', 'hand': 'ph.hand-palm',
    'cursor': 'ph.cursor', 'click': 'ph.hand-pointing', 'drag': 'ph.arrows-out',
    'scroll': 'ph.arrows-down-up', 'pause': 'ph.pause', 'tabs': 'ph.browsers',
    'arrow': 'ph.arrow-up-right', 'sparkle': 'ph.sparkle', 'camera': 'ph.camera',
    'check': 'ph.check-circle', 'chevron': 'ph.caret-down', 'play': 'ph.play',
}


def icon(name, color='#a8b9ca') -> QIcon:
    return qta.icon(_NAMES.get(name, 'ph.info'), color=color,
                    color_active='#8dcfff', color_selected='#8dcfff',
                    color_disabled='#586677')
