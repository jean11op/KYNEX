"""Composition root for the local domain, persistence, vision and Windows actions."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from holocontrol.application.services.adaptador_ejecutor_existente import (
    AdaptadorEjecutorExistente,
)
from holocontrol.application.services.coordinador_control_vision import CoordinadorControlVision
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Calibracion, Mano
from holocontrol.domain.value_objects.estado_control import EstadoControl
from holocontrol.infrastructure.persistence.conexion import BaseDatos
from holocontrol.infrastructure.persistence.repositorio_perfil import RepositorioPerfilesSQLite
from holocontrol.infrastructure.vision.configuration import (
    ConfiguracionCamara,
    ConfiguracionVision,
)
from holocontrol.infrastructure.vision.vision_worker import AdaptadorVision
from holocontrol.infrastructure.windows.windows_action_executor import WindowsActionExecutor
from holocontrol.ports.vision.models import Lateralidad
from holocontrol.ports.vision.vision_provider import ProveedorVision


@dataclass(frozen=True)
class ComponentesNucleo:
    base_datos: BaseDatos
    repositorio: RepositorioPerfilesSQLite
    aplicacion: AplicacionControl
    proveedor_vision: ProveedorVision
    coordinador: CoordinadorControlVision
    id_perfil: str


def crear_nucleo(
    ruta_base_datos: str | Path,
    *,
    ejecutor_existente=None,
    proveedor_vision: ProveedorVision | None = None,
) -> ComponentesNucleo:
    """Construye el núcleo sin abrir la cámara ni activar acciones de Windows."""
    base = BaseDatos(ruta_base_datos)
    base.inicializar()
    repositorio = RepositorioPerfilesSQLite(base)
    ejecutor = (
        ejecutor_existente if ejecutor_existente is not None else WindowsActionExecutor()
    )
    aplicacion = AplicacionControl(repositorio, AdaptadorEjecutorExistente(ejecutor))

    perfiles = aplicacion.listar_perfiles()
    if not perfiles:
        perfil = aplicacion.crear_perfil("Perfil predeterminado", Mano.DERECHA)
        aplicacion.calibrar_perfil(Calibracion(id_perfil=perfil.id))
        perfil = repositorio.obtener(perfil.id)
    else:
        perfil = perfiles[0]
    aplicacion.seleccionar_perfil(perfil.id)

    proveedor = proveedor_vision or AdaptadorVision(
        configuracion=ConfiguracionVision(
            mano_dominante=Lateralidad(perfil.mano_dominante.value),
        ),
        camara=ConfiguracionCamara(indice=perfil.configuracion.indice_camara),
    )
    coordinador = CoordinadorControlVision(aplicacion, proveedor)
    return ComponentesNucleo(base, repositorio, aplicacion, proveedor, coordinador, perfil.id)


class _TrabajoCicloVida(QObject):
    terminado = Signal(str, object, object)

    def __init__(self, operacion: str, ejecutar: Callable[[], object]) -> None:
        super().__init__()
        self._operacion = operacion
        self._ejecutar = ejecutar

    @Slot()
    def run(self) -> None:
        try:
            self.terminado.emit(self._operacion, self._ejecutar(), None)
        except Exception as error:  # noqa: BLE001 - El fallo se comunica a la ventana.
            self.terminado.emit(self._operacion, None, error)


class MainWindow(QMainWindow):
    def __init__(self, componentes: ComponentesNucleo | None = None):
        super().__init__()
        ruta_bd = Path.home() / ".holocontrol" / "holocontrol.sqlite3"
        self.componentes = componentes or crear_nucleo(ruta_bd)
        self.setWindowTitle("HoloControl Access")
        self.resize(800, 500)

        self.title_label = QLabel("HoloControl Access")
        self.title_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.description_label = QLabel(
            "Control accesible de Windows mediante gestos de las manos."
        )
        self.status_label = QLabel("Estado: preparado; cámara detenida")
        self.start_button = QPushButton("Iniciar / reanudar control")
        self.pause_button = QPushButton("Pausar control")
        self.stop_button = QPushButton("Detener control")
        self.start_button.clicked.connect(self.start_control)
        self.pause_button.clicked.connect(self.pause_control)
        self.stop_button.clicked.connect(self.stop_control)

        layout = QVBoxLayout()
        for widget in (
            self.title_label,
            self.description_label,
            self.status_label,
            self.start_button,
            self.pause_button,
            self.stop_button,
        ):
            layout.addWidget(widget)
        layout.addStretch()
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self._trabajo: QThread | None = None
        self._trabajador: _TrabajoCicloVida | None = None
        self._operacion_actual: str | None = None
        self._cerrar_pendiente = False
        self._cerrando = False
        self._cerrado = False
        self._cierre_correcto = False
        self._sondeo = QTimer(self)
        self._sondeo.setInterval(20)
        self._sondeo.timeout.connect(self._consultar_vision)

    def _ejecutar_en_trabajador(self, operacion: str, ejecutar: Callable[[], object]) -> None:
        if self._trabajo is not None:
            return
        self._habilitar_controles(False)
        thread = QThread(self)
        worker = _TrabajoCicloVida(operacion, ejecutar)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.terminado.connect(self._ciclo_terminado)
        worker.terminado.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._limpiar_trabajador(thread))
        self._trabajo, self._trabajador = thread, worker
        self._operacion_actual = operacion
        thread.start()

    @Slot()
    def start_control(self) -> None:
        estado = self.componentes.aplicacion.estado_actual().estado
        if estado is EstadoControl.ACTIVE:
            return
        if estado is EstadoControl.PAUSED:
            iniciar = self.componentes.coordinador.reanudar_control
        else:
            pantalla = QApplication.primaryScreen()
            if pantalla is None:
                self.status_label.setText("Estado: no se detectó una pantalla")
                return
            tamano = pantalla.size()
            ancho, alto = tamano.width(), tamano.height()
            iniciar = partial(
                self.componentes.coordinador.iniciar_control,
                ancho_pantalla=ancho,
                alto_pantalla=alto,
            )
        self.status_label.setText("Estado: esperando a que la cámara esté lista…")
        self._ejecutar_en_trabajador("iniciar", iniciar)

    @Slot()
    def pause_control(self) -> None:
        self._sondeo.stop()
        self.status_label.setText("Estado: pausando y cerrando la cámara…")
        self._ejecutar_en_trabajador("pausar", self.componentes.coordinador.pausar_control)

    @Slot()
    def stop_control(self) -> None:
        self._sondeo.stop()
        self.status_label.setText("Estado: deteniendo y cerrando la cámara…")
        self._ejecutar_en_trabajador("detener", self.componentes.coordinador.detener_control)

    @Slot()
    def _consultar_vision(self) -> None:
        try:
            resultado = self.componentes.coordinador.consultar_vision()
            estado = self.componentes.aplicacion.estado_actual()
            if estado.estado is not EstadoControl.ACTIVE:
                self._sondeo.stop()
                self.status_label.setText(
                    f"Estado: control pausado ({resultado.motivo})"
                )
        except Exception as error:  # noqa: BLE001 - Un fallo invalida el sondeo gestual.
            self._sondeo.stop()
            self.status_label.setText(f"Estado: control detenido por error ({error})")

    @Slot(str, object, object)
    def _ciclo_terminado(self, operacion: str, resultado: object, error: object) -> None:
        if error is not None:
            self.status_label.setText(f"Estado: {operacion} falló ({error})")
        elif operacion == "iniciar" and not self._cerrar_pendiente:
            self.status_label.setText("Estado: control activo")
            self._sondeo.start()
        elif operacion == "pausar":
            self.status_label.setText("Estado: control pausado")
        elif operacion in ("detener", "cerrar"):
            self.status_label.setText("Estado: control detenido")

        if self._cerrar_pendiente and operacion in ("detener", "cerrar"):
            if error is None:
                self._cierre_correcto = True
            else:
                self._cerrar_pendiente = False
                self._cerrando = False
                self._cierre_correcto = False
                self._habilitar_controles(True)
        elif not self._cerrar_pendiente:
            self._habilitar_controles(True)

    def _limpiar_trabajador(self, thread: QThread) -> None:
        if self._trabajo is thread:
            self._trabajo = None
            self._trabajador = None
            operacion, self._operacion_actual = self._operacion_actual, None
            if self._cerrar_pendiente and operacion in ("detener", "cerrar"):
                if self._cierre_correcto:
                    self._cerrado = True
                    self.close()
            elif self._cerrar_pendiente:
                self._cerrando = False
                self._detener_para_cerrar()
        thread.deleteLater()

    def _detener_para_cerrar(self) -> None:
        if self._cerrando:
            return
        self._cerrando = True
        self._sondeo.stop()
        self._ejecutar_en_trabajador(
            "cerrar", self.componentes.coordinador.detener_control
        )

    def _habilitar_controles(self, habilitados: bool) -> None:
        for boton in (self.start_button, self.pause_button, self.stop_button):
            boton.setEnabled(habilitados)

    def closeEvent(self, event) -> None:
        if self._cerrado:
            event.accept()
            return
        self._cerrar_pendiente = True
        event.ignore()
        if self._trabajo is None:
            estado = self.componentes.aplicacion.estado_actual().estado
            if estado is EstadoControl.STOPPED:
                self._cerrado = True
                self.close()
            else:
                self._detener_para_cerrar()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
