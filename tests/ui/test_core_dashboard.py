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
