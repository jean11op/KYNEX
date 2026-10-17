from __future__ import annotations

import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from holocontrol.bootstrap import MainWindow, crear_nucleo
from holocontrol.domain.entities import Calibracion, Mano
from holocontrol.domain.value_objects.estado_control import EstadoControl
from holocontrol.ports.vision.models import EstadoVision


class EjecutorSimulado:
    def __init__(self, eventos):
        self.eventos = eventos

    def activate(self):
        self.eventos.append("ejecutor_activo")

    def pause(self):
        self.eventos.append("ejecutor_pausado")

    def stop(self):
        self.eventos.append("ejecutor_detenido")

    def set_hand_detected(self, _detectada):
        pass

    def move_cursor(self, _x, _y):
        pass

    def left_click(self):
        pass

    def right_click(self):
        pass

    def scroll(self, _amount):
        pass


class ProveedorSimulado:
    def __init__(self, eventos, *, disponible=True):
        self.eventos = eventos
        self.disponible = disponible
        self._activo = False

    @property
    def estado(self):
        return EstadoVision.CAMARA_DISPONIBLE if self._activo else EstadoVision.DETENIDO

    @property
    def en_ejecucion(self):
        return self._activo

    @property
    def camara_disponible(self):
        return self._activo and self.disponible

    def iniciar(self):
        self._activo = True
        self.eventos.append("camara_iniciada")

    def obtener_resultado(self, _espera_s=0.0):
        return None

    def activar_vista_previa(self, _activa):
        pass

    def obtener_fotograma(self):
        return None

    def detener(self, _espera_s=2.0):
        self._activo = False
        self.eventos.append("camara_detenida")
        return True


class PantallaSimulada:
    class Tamano:
        @staticmethod
        def width():
            return 1280

        @staticmethod
        def height():
            return 720

    @staticmethod
    def size():
        return PantallaSimulada.Tamano()


class TestDashboardCore:
    @classmethod
    def setup_class(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setup_method(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.settings = QSettings(str(self.path / "ui.ini"), QSettings.Format.IniFormat)
        self.eventos = []
        self.proveedor = ProveedorSimulado(self.eventos)
        self.componentes = crear_nucleo(
            self.path / "core.sqlite3",
            ejecutor_existente=EjecutorSimulado(self.eventos),
            proveedor_vision=self.proveedor,
        )
        self.componentes.aplicacion.calibrar_perfil(
            Calibracion(self.componentes.id_perfil)
        )
        self.window = MainWindow(
            self.componentes, settings=self.settings, enable_tray=False
        )

    def teardown_method(self):
        self.window.close()
        self._esperar(lambda: self.window._cerrado and self.window._futuro is None)
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def _esperar(self, condicion, timeout=3.0):
        limite = time.monotonic() + timeout
        while time.monotonic() < limite and not condicion():
            self.app.processEvents()
            QTest.qWait(10)
        self.app.processEvents()
        assert condicion()

    def test_control_espera_camara_y_operaciones_no_bloquean_qt(self, monkeypatch):
        monkeypatch.setattr(
            "holocontrol.bootstrap.QApplication.primaryScreen",
            lambda: PantallaSimulada(),
        )
        self.window.start_control()
        self._esperar(
            lambda: self.componentes.aplicacion.estado_actual().estado
            is EstadoControl.ACTIVE and self.window._futuro is None
        )
        assert self.eventos.index("camara_iniciada") < self.eventos.index("ejecutor_activo")
        assert self.window.camera_status_label.text() == "Disponible"
        self.window.pause_control()
        self._esperar(
            lambda: self.componentes.aplicacion.estado_actual().estado
            is EstadoControl.PAUSED and self.window._futuro is None
        )
        self.window.start_control()
        self._esperar(
            lambda: self.componentes.aplicacion.estado_actual().estado
            is EstadoControl.ACTIVE and self.window._futuro is None
        )
        self.window.stop_control()
        self._esperar(
            lambda: self.componentes.aplicacion.estado_actual().estado
            is EstadoControl.STOPPED and self.window._futuro is None
        )

    def test_inicio_libera_sesion_antes_de_cambiar_camara_sin_sondeo_doble(self, monkeypatch):
        from unittest.mock import Mock
        monkeypatch.setattr('holocontrol.bootstrap.AdaptadorVision', type(self.proveedor))
        probe = Mock(side_effect=AssertionError('No abrir dos veces una cámara explícita'))
        monkeypatch.setattr('holocontrol.bootstrap.seleccionar_camara', probe)
        self.window.camera_selector.setCurrentIndex(self.window.camera_selector.findData(1))
        self.proveedor._activo = True
        original = self.proveedor.detener
        def detener(espera_s):
            assert not hasattr(self.proveedor, 'camara') or not self.proveedor.en_ejecucion
            return original(espera_s)
        monkeypatch.setattr(self.proveedor, 'detener', detener)
        self.window.start_control()
        self._esperar(lambda: self.window._futuro is None)
        assert self.proveedor.camara.indice == 1
        assert self.componentes.aplicacion.estado_actual().estado is EstadoControl.ACTIVE
        probe.assert_not_called()
        monkeypatch.setattr(self.proveedor, 'detener', original)

    def test_buscar_camaras_actualiza_lista_y_conserva_seleccion(self, monkeypatch):
        self.window.camera_selector.setCurrentIndex(self.window.camera_selector.findData(1))
        def buscar(indices):
            assert not self.proveedor.en_ejecucion
            return (0, 1, 7)
        monkeypatch.setattr('holocontrol.bootstrap.detectar_camaras', buscar)
        self.window.camera_scan_button.click()
        self._esperar(lambda: self.window._futuro is None)
        assert self.window.camera_selector.currentData() == 1
        assert [self.window.camera_selector.itemData(i) for i in range(4)] == [-1, 0, 1, 7]
        assert '3 cámaras' in self.window.camera_hint.text()
        self.window.camera_selector.setCurrentIndex(3)
        assert self.window.preferences.data['camera_selection'] == 7
        assert self.window.camera_scan_button.isEnabled()

    def test_buscar_camaras_no_sustituye_camara_desconectada(self, monkeypatch):
        self.window.camera_selector.setCurrentIndex(self.window.camera_selector.findData(1))
        monkeypatch.setattr('holocontrol.bootstrap.detectar_camaras', lambda indices: ())
        self.window.camera_scan_button.click()
        self._esperar(lambda: self.window._futuro is None)
        assert self.window.camera_selector.currentData() == 1
        assert 'no disponible' in self.window.camera_selector.currentText()
        assert 'No se encontró' in self.window.camera_hint.text()

    def test_probar_camara_abre_vista_previa_sin_acciones(self, monkeypatch):
        from unittest.mock import Mock
        preview = Mock()
        monkeypatch.setattr(self.window, 'start_control', preview)
        self.window.camera_test_button.click()
        self._esperar(lambda: self.window._futuro is None)
        preview.assert_called_once_with(vista_previa=True)
        assert self.window.stack.currentIndex() == 0
        assert 'ejecutor_activo' not in self.eventos

    def test_perfiles_mostrados_y_seleccionados_salen_de_sqlite(self):
        otro = self.componentes.aplicacion.crear_perfil("Perfil izquierdo", Mano.IZQUIERDA)
        self.window.refresh()
        indice = next(
            i
            for i in range(self.window.profile_list.count())
            if self.window.profile_list.item(i).data(Qt.ItemDataRole.UserRole) == otro.id
        )
        self.window.profile_list.setCurrentRow(indice)
        self.window.select_profile()
        self._esperar(
            lambda: self.componentes.aplicacion.estado_actual().id_perfil_seleccionado
            == otro.id and self.window._futuro is None
        )
        assert self.window.header_profile.text() == otro.nombre
        assert otro.calibracion is None

    def test_camara_no_disponible_no_activa_el_ejecutor(self, monkeypatch):
        self.proveedor.disponible = False
        self.componentes.coordinador._espera_inicio_s = 0.05
        monkeypatch.setattr(
            "holocontrol.bootstrap.QApplication.primaryScreen",
            lambda: PantallaSimulada(),
        )
        self.window.start_control()
        self._esperar(
            lambda: self.window._futuro is None
            and "esperando" not in self.window.feedback.text().casefold()
        )
        assert self.componentes.aplicacion.estado_actual().estado is EstadoControl.STOPPED
        assert "ejecutor_activo" not in self.eventos
        assert self.window.start_button.isEnabled()

    def test_perfil_nuevo_abre_vista_previa_sin_activar_raton(self):
        perfil = self.componentes.aplicacion.crear_perfil('Nuevo', Mano.DERECHA)
        self.componentes.aplicacion.seleccionar_perfil(perfil.id)
        self.window.start_button.click()
        self._esperar(lambda: self.window._futuro is None and self.proveedor.en_ejecucion)
        self.window._consultar_vision()
        assert self.window.camera_status_label.text() == 'Disponible'
        assert self.window.preview.live_mode
        assert 'ejecutor_activo' not in self.eventos
        assert self.componentes.aplicacion.estado_actual().estado is EstadoControl.STOPPED
        self.window.stop_control()
        self._esperar(lambda: self.window._futuro is None)
        assert not self.proveedor.en_ejecucion
        assert not self.window.preview.live_mode

    def test_vista_previa_recibe_copia_del_fotograma(self):
        import numpy as np
        from holocontrol.ports.vision.models import Fotograma
        imagen = np.zeros((10, 20, 3), dtype=np.uint8)
        imagen[:, :, 2] = 255
        self.window.preview.set_camera_frame(Fotograma(imagen, 1))
        imagen[:] = 0
        assert self.window.preview.live_image.pixelColor(0, 0).name() == '#ff0000'
        self.window.preview.set_camera_frame(None)
        assert self.window.preview.live_image.isNull()

    def test_calibracion_medida_se_guarda_y_permite_acciones(self):
        from dataclasses import replace
        from tests.integration.test_vision_domain_windows import _mano
        from holocontrol.ports.vision.models import ResultadoVision
        perfil = self.componentes.aplicacion.crear_perfil('Por calibrar', Mano.DERECHA)
        self.componentes.aplicacion.seleccionar_perfil(perfil.id)
        self.window.start_control()
        self._esperar(lambda: self.window._futuro is None)
        for esquina, x, y in [('superior', .2, .2), ('inferior', .8, .8)]:
            mano = _mano('indice')
            puntos = tuple(replace(p, x=x, y=y) if p.indice == 8 else p for p in mano.puntos)
            self.window._resultado_visual = ResultadoVision(time.monotonic_ns() // 1_000_000, EstadoVision.MANO_DETECTADA, replace(mano, puntos=puntos))
            self.window._medir_esquina(esquina, perfil.id)
        self.window.save_calibration_preferences()
        self._esperar(lambda: self.window._futuro is None)
        guardado = self.componentes.repositorio.obtener(perfil.id)
        assert guardado.calibracion.x_min == .2
        assert guardado.calibracion.x_max == .8
        assert not self.proveedor.en_ejecucion
        self.window.start_control()
        self._esperar(lambda: self.window._futuro is None)
        assert self.componentes.aplicacion.estado_actual().estado is EstadoControl.ACTIVE
        assert 'ejecutor_activo' in self.eventos

    def test_calibracion_rechaza_datos_vencidos(self):
        from tests.integration.test_vision_domain_windows import _mano
        from holocontrol.ports.vision.models import ResultadoVision
        self.window._solo_vista_previa = True
        self.window._resultado_visual = ResultadoVision(1, EstadoVision.MANO_DETECTADA, _mano('indice'))
        self.window._medir_esquina('superior', self.componentes.id_perfil)
        assert not self.window._esquinas

    def test_asignacion_puno_se_guarda_en_nucleo(self):
        combo, enabled = self.window.core_gesture_fields['puno']
        combo.setCurrentIndex(combo.findData('clic_derecho'))
        enabled.setChecked(True)
        self.window.save_gestures()
        self._esperar(lambda: self.window._futuro is None)
        perfil = self.componentes.repositorio.obtener(self.componentes.id_perfil)
        asignacion = next(a for a in perfil.asignaciones if a.id_gesto == 'puno')
        assert asignacion.activo and asignacion.id_accion == 'clic_derecho'

    def test_slow_control_keeps_camera_and_qt_responsive_without_queue(self, monkeypatch):
        from threading import Event
        from PySide6.QtCore import QTimer
        from holocontrol.application.dto.resultados import ResultadoGesto
        entered, release = Event(), Event()
        calls, frames, beats = [], [], []

        def slow_control():
            # Match the application's lock held during a native Windows call.
            with self.componentes.aplicacion._bloqueo:
                calls.append(1)
                entered.set()
                release.wait(2)
            return ResultadoGesto(False, 'sin_resultado')

        def camera_frame():
            frames.append(1)
            return None

        monkeypatch.setattr(self.componentes.coordinador, 'consultar_vision', slow_control)
        monkeypatch.setattr(self.proveedor, 'obtener_fotograma', camera_frame)
        heartbeat = QTimer()
        heartbeat.setInterval(5)
        heartbeat.timeout.connect(lambda: beats.append(1))
        heartbeat.start()
        try:
            self.window.start_control()
            self._esperar(entered.is_set)
            before = len(frames)
            QTest.qWait(100)
            assert len(calls) == 1  # No stale actions queued behind the slow one.
            assert len(frames) >= before + 2
            assert len(beats) >= 5
            assert not self.window._futuro_accion.done()
            self.window.stop_control()
            release.set()
            self._esperar(lambda: self.window._futuro is None)
            assert self.componentes.aplicacion.estado_actual().estado is EstadoControl.STOPPED
            assert self.window._futuro_accion is None
        finally:
            release.set()
            heartbeat.stop()

    def test_background_action_error_stops_camera_and_allows_retry(self, monkeypatch):
        def fail():
            raise RuntimeError('fallo de acción')
        monkeypatch.setattr(self.componentes.coordinador, 'consultar_vision', fail)
        self.window.start_control()
        self._esperar(lambda: 'fallo de acción' in self.window.feedback.text() and self.window._futuro is None)
        assert self.componentes.aplicacion.estado_actual().estado is EstadoControl.STOPPED
        assert not self.proveedor.en_ejecucion
        assert self.window.start_button.isEnabled()


    def test_save_button_persists_without_wizard_or_remeasurement(self):
        self.window.navigate(2)
        assert self.window.save_cal_button.isEnabled()
        self.window.cal_sensitivity.setValue(135)
        self.window.save_cal_button.click()
        self._esperar(lambda: self.window._futuro is None)
        stored = self.componentes.repositorio.obtener(self.componentes.id_perfil)
        assert stored.calibracion.sensibilidad == 1.35
        assert 'guardada' in self.window.cal_description.text()

    def test_refresh_preserves_measured_corners(self):
        self.window._esquinas = {'superior': (.2, .2), 'inferior': (.8, .8)}
        self.window.refresh()
        assert len(self.window._esquinas) == 2

    def test_control_runs_without_gui_polling_when_minimized(self, monkeypatch):
        from holocontrol.application.dto.resultados import ResultadoGesto
        calls = []
        def consume():
            calls.append(1)
            return ResultadoGesto(False, 'sin_resultado')
        monkeypatch.setattr(self.componentes.coordinador, 'consultar_vision', consume)
        self.window.start_control()
        self._esperar(lambda: self.window._futuro is None)
        self.window.showMinimized()
        self.window._sondeo.stop()
        before = len(calls)
        # Deliberately don't process Qt events: gesture execution must be independent.
        time.sleep(.15)
        assert len(calls) >= before + 3
        self.window.stop_control()
        self._esperar(lambda: self.window._futuro is None)

    def test_physical_screen_dimensions_used_with_windows_scaling(self, monkeypatch):
        monkeypatch.setattr('holocontrol.bootstrap.pyautogui.size', lambda: (1920, 1080))
        self.window.start_control()
        self._esperar(lambda: self.window._futuro is None)
        assert self.componentes.aplicacion._pantalla == (1920, 1080)
