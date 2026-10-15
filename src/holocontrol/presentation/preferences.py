"""Preferencias de la UI; reemplazables por el repositorio del equipo."""

import copy
import json
import uuid

from PySide6.QtCore import QSettings

DEFAULT_GESTURES = {
    'Índice extendido': 'Mover cursor', 'Pellizco': 'Clic izquierdo',
    'Pellizco sostenido': 'Arrastrar y soltar', 'Dos dedos': 'Desplazar',
    'Mano abierta': 'Pausar control', 'Deslizamiento': 'Cambiar pestaña',
}
ACTIONS = ['Sin asignar', 'Mover cursor', 'Clic izquierdo', 'Clic derecho',
           'Arrastrar y soltar', 'Desplazar', 'Cambiar pestaña', 'Pausar control',
           'Cambiar modo', 'Atajo de teclado']


def new_profile(name='General', hand='Derecha'):
    return {'id': uuid.uuid4().hex, 'name': name, 'hand': hand,
            'sensitivity': 100, 'smoothing': 50, 'threshold': 80,
            'gestures': {key: {'action': value, 'enabled': True, 'shortcut': ''}
                         for key, value in DEFAULT_GESTURES.items()},
            'voice': [], 'dictation_limit': 250, 'calibration': None}


class Preferences:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings('Kinex', 'Interface')
        self.load_error = False
        default = new_profile()
        self.data = {'profiles': [default], 'active': default['id'],
                     'theme': 'Oscuro', 'font_size': 13, 'preview': True,
                     'minimize_tray': False, 'start_minimized': False,
                     'notifications': True, 'pause_shortcut': 'Ctrl+Shift+P'}
        raw = self.settings.value('ui_state')
        if raw:
            try:
                candidate = json.loads(raw)
                profiles = candidate['profiles']
                assert isinstance(profiles, list) and profiles
                normalized = []
                for profile in profiles:
                    assert isinstance(profile['name'], str) and profile['name'].strip()
                    assert isinstance(profile['id'], str)
                    assert profile['hand'] in ('Derecha', 'Izquierda')
                    base = new_profile()
                    base.update(profile)
                    for key, low, high in [('sensitivity', 25, 200), ('smoothing', 0, 100), ('threshold', 50, 100), ('dictation_limit', 20, 2000)]:
                        base[key] = max(low, min(high, int(base[key])))
                    assert isinstance(base['gestures'], dict)
                    for gesture, action in DEFAULT_GESTURES.items():
                        value = base['gestures'].get(gesture, {})
                        assert isinstance(value, dict)
                        base['gestures'][gesture] = {'action': value.get('action', action) if value.get('action', action) in ACTIONS else 'Sin asignar', 'enabled': bool(value.get('enabled', True)), 'shortcut': str(value.get('shortcut', ''))}
                    assert isinstance(base['voice'], list)
                    assert all(isinstance(c, dict) and isinstance(c.get('phrase'), str)
                               and c.get('action') in ACTIONS for c in base['voice'])
                    normalized.append(base)
                assert len({p['id'] for p in normalized}) == len(normalized)
                font_size = max(12, min(18, int(candidate.get('font_size', 13))))
                self.data.update(candidate)
                self.data['profiles'] = normalized
                if self.data['active'] not in [p['id'] for p in normalized]:
                    self.data['active'] = normalized[0]['id']
                self.data['font_size'] = font_size
            except (ValueError, TypeError, KeyError, AssertionError):
                self.load_error = True

    @property
    def profile(self):
        return next(p for p in self.data['profiles'] if p['id'] == self.data['active'])

    def save(self):
        self.settings.setValue('ui_state', json.dumps(self.data, ensure_ascii=False))
        self.settings.sync()
        if self.settings.status() != QSettings.Status.NoError:
            raise OSError('No se pudieron guardar las preferencias en este equipo.')

    def add(self, name, hand):
        self.validate_name(name)
        profile = new_profile(name.strip(), hand)
        self.data['profiles'].append(profile)
        self.data['active'] = profile['id']
        return profile

    def validate_name(self, name, excluding=None):
        if not name.strip():
            raise ValueError('Escribe un nombre para el perfil.')
        if any(p['id'] != excluding and p['name'].casefold() == name.strip().casefold() for p in self.data['profiles']):
            raise ValueError('Ya existe un perfil con ese nombre.')

    def remove(self, profile_id):
        if len(self.data['profiles']) == 1:
            raise ValueError('Debes conservar al menos un perfil.')
        self.data['profiles'] = [p for p in self.data['profiles'] if p['id'] != profile_id]
        if self.data['active'] == profile_id:
            self.data['active'] = self.data['profiles'][0]['id']

    def reset_gestures(self):
        self.profile['gestures'] = copy.deepcopy(new_profile()['gestures'])
