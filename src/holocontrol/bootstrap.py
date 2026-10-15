"""Composition root for the local domain, persistence, vision and Windows actions."""

from __future__ import annotations

import sys
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from holocontrol.application.services.adaptador_ejecutor_existente import (
    AdaptadorEjecutorExistente,
)
from holocontrol.application.services.coordinador_control_vision import CoordinadorControlVision
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Mano
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
from holocontrol.presentation.main_window import MainWindow as DashboardWindow


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


class MainWindow(DashboardWindow):
    """Conecta el dashboard existente con SQLite, el coordinador y la cámara."""

    def __init__(
        self,
        componentes: ComponentesNucleo | None = None,
        *,
        settings=None,
        enable_tray: bool = True,
    ):
        self.componentes = componentes or crear_nucleo(
            Path.home() / ".holocontrol" / "holocontrol.sqlite3"
        )
        self._ejecutor_ciclo = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="holocontrol-ui"
        )
        self._futuro: Future | None = None
        self._operacion_actual: str | None = None
        self._cierre_pendiente = False
        self._cerrado = False
        super().__init__(settings=settings, enable_tray=enable_tray)
        self.setWindowTitle("HoloControl Access")
        self.start_button.setEnabled(True)
        self.start_button.setToolTip("Inicia después de que la cámara esté disponible.")
        self.start_button.clicked.connect(self.start_control)
        self._sondeo = QTimer(self)
        self._sondeo.setInterval(20)
        self._sondeo.timeout.connect(self._consultar_vision)
        self._sondeo_trabajo = QTimer(self)
        self._sondeo_trabajo.setInterval(20)
        self._sondeo_trabajo.timeout.connect(self._revisar_trabajo)
        self._actualizar_estado()

    def refresh(self):
        super().refresh()
        if not hasattr(self, "profile_list") or not hasattr(self, "componentes"):
            return
        estado = self.componentes.aplicacion.estado_actual()
        perfiles = self.componentes.aplicacion.listar_perfiles()
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for perfil in perfiles:
            calibracion = "calibrado" if perfil.calibracion is not None else "calibración pendiente"
            self.profile_list.addItem(
                f"{perfil.nombre} · Mano {perfil.mano_dominante.value} · {calibracion}"
            )
            item = self.profile_list.item(self.profile_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, perfil.id)
            if perfil.id == estado.id_perfil_seleccionado:
                self.profile_list.setCurrentItem(item)
        seleccionado = next(
            (perfil for perfil in perfiles if perfil.id == estado.id_perfil_seleccionado),
            None,
        )
        if seleccionado is not None:
            self.profile_badge.setText(seleccionado.nombre)
            self.header_profile.setText(seleccionado.nombre)
        self.profile_list.blockSignals(False)

    def selected_profile(self):
        item = self.profile_list.currentItem()
        if item is None:
            return None
        return next(
            (
                perfil
                for perfil in self.componentes.aplicacion.listar_perfiles()
                if perfil.id == item.data(Qt.ItemDataRole.UserRole)
            ),
            None,
        )

    def create_profile(self):
        result = self.profile_dialog()
        if result is None:
            return
        nombre, mano = result

        def crear():
            self.componentes.coordinador.detener_control()
            perfil = self.componentes.aplicacion.crear_perfil(nombre, Mano(mano.lower()))
            return self.componentes.aplicacion.seleccionar_perfil(perfil.id)

        self._ejecutar_en_trabajador("crear perfil", crear)

    def select_profile(self):
        perfil = self.selected_profile()
        if perfil is None:
            return
        if self.componentes.aplicacion.estado_actual().id_perfil_seleccionado == perfil.id:
            return

        def seleccionar():
            self.componentes.coordinador.detener_control()
            return self.componentes.aplicacion.seleccionar_perfil(perfil.id)

        self._ejecutar_en_trabajador("seleccionar perfil", seleccionar)

    def edit_profile(self):
        perfil = self.selected_profile()
        if perfil is None:
            return
        resultado = self.profile_dialog(
            {
                "id": perfil.id,
                "name": perfil.nombre,
                "hand": perfil.mano_dominante.value.title(),
            }
        )
        if resultado is None:
            return
        nombre, mano = resultado

        def editar():
            self.componentes.coordinador.detener_control()
            return self.componentes.aplicacion.editar_perfil(
                perfil.id, nombre=nombre, mano_dominante=Mano(mano.lower())
            )

        self._ejecutar_en_trabajador("editar perfil", editar)

    def delete_profile(self):
        perfil = self.selected_profile()
        if perfil is None:
            return
        if len(self.componentes.aplicacion.listar_perfiles()) < 2:
            self.feedback.setText("Debe conservarse al menos un perfil.")
            return
        if not self.confirm("Eliminar perfil", f"¿Eliminar «{perfil.nombre}» y sus datos?"):
            return

        def eliminar():
            self.componentes.coordinador.detener_control()
            self.componentes.aplicacion.eliminar_perfil(perfil.id, confirmado=True)

        self._ejecutar_en_trabajador("eliminar perfil", eliminar)

    def start_control(self):
        estado = self.componentes.aplicacion.estado_actual()
        perfil = next(
            (
                perfil
                for perfil in self.componentes.aplicacion.listar_perfiles()
                if perfil.id == estado.id_perfil_seleccionado
            ),
            None,
        )
        if perfil is None:
            self.feedback.setText("Selecciona un perfil antes de iniciar.")
            return
        if perfil.calibracion is None:
            self.feedback.setText("El perfil necesita una calibración real antes de iniciar.")
            return
        if estado.estado is EstadoControl.ACTIVE:
            return
        pantalla = QApplication.primaryScreen()
        if pantalla is None:
            self.feedback.setText("No se detectó una pantalla.")
            return
        tamano = pantalla.size()

        def iniciar():
            proveedor = self.componentes.proveedor_vision
            if isinstance(proveedor, AdaptadorVision):
                proveedor.configuracion = ConfiguracionVision(
                    mano_dominante=Lateralidad(perfil.mano_dominante.value)
                )
                proveedor.camara = ConfiguracionCamara(
                    indice=perfil.configuracion.indice_camara
                )
            if estado.estado is EstadoControl.PAUSED:
                return self.componentes.coordinador.reanudar_control()
            return self.componentes.coordinador.iniciar_control(
                ancho_pantalla=tamano.width(), alto_pantalla=tamano.height()
            )

        self.feedback.setText("Esperando a que la cámara esté disponible…")
        self._ejecutar_en_trabajador("iniciar", iniciar)

    def pause_control(self):
        self._sondeo.stop()
        self.feedback.setText("Pausando el control y cerrando la cámara…")
        self._ejecutar_en_trabajador(
            "pausar", self.componentes.coordinador.pausar_control
        )

    def stop_control(self):
        self._sondeo.stop()
        self.feedback.setText("Deteniendo el control y cerrando la cámara…")
        self._ejecutar_en_trabajador(
            "detener", self.componentes.coordinador.detener_control
        )

    def _ejecutar_en_trabajador(self, operacion: str, ejecutar: Callable[[], object]):
        if self._futuro is not None:
            return
        self._habilitar_controles(False)
        self._operacion_actual = operacion
        self._futuro = self._ejecutor_ciclo.submit(ejecutar)
        self._sondeo_trabajo.start()

    def _revisar_trabajo(self):
        futuro = self._futuro
        if futuro is None or not futuro.done():
            return
        self._sondeo_trabajo.stop()
        operacion, self._operacion_actual = self._operacion_actual, None
        self._futuro = None
        try:
            resultado, error = futuro.result(), None
        except Exception as fallo:  # noqa: BLE001 - se muestra el error de infraestructura.
            resultado, error = None, fallo
        self._ciclo_terminado(operacion or "operaci?n", resultado, error)

    def _consultar_vision(self):
        try:
            self.componentes.coordinador.consultar_vision()
        except Exception as error:  # noqa: BLE001 - muestra el fallo y detiene el sondeo.
            self.feedback.setText(f"Control detenido por error: {error}")
            self._sondeo.stop()
        self._actualizar_estado()

    def _actualizar_estado(self):
        estado = self.componentes.aplicacion.estado_actual()
        self.camera_status_label.setText(
            "Disponible" if estado.camara_disponible else "No conectada"
        )
        if estado.mano_detectada:
            self.recognition_status_label.setText("Mano detectada")
        elif estado.camara_disponible and estado.estado is EstadoControl.ACTIVE:
            self.recognition_status_label.setText("Esperando la mano")
        else:
            self.recognition_status_label.setText("Detenido")
        etiqueta = {
            EstadoControl.ACTIVE: "●  Control activo",
            EstadoControl.PAUSED: "●  Control pausado",
            EstadoControl.STOPPED: "●  Control detenido",
        }[estado.estado]
        self.control_status_label.setText(etiqueta)
        if estado.error:
            self.feedback.setText(estado.error)
        if estado.estado is not EstadoControl.ACTIVE and hasattr(self, "_sondeo"):
            self._sondeo.stop()

    def _ciclo_terminado(self, operacion: str, resultado: object, error: object):
        if error is not None:
            self.feedback.setText(f"{operacion.capitalize()} fall?: {error}")
            if operacion == "cerrar":
                self._cierre_pendiente = False
        elif operacion == "iniciar":
            self.feedback.setText(
                "Control activo. Las acciones se habilitaron despu?s de iniciar la c?mara."
            )
            self._sondeo.start()
        elif operacion == "pausar":
            self.feedback.setText("Control pausado.")
        elif operacion == "detener":
            self.feedback.setText("Control detenido.")
        elif operacion == "cerrar":
            self._cerrado = True
        elif operacion in (
            "crear perfil",
            "seleccionar perfil",
            "editar perfil",
            "eliminar perfil",
        ):
            self.feedback.setText("Perfil actualizado en SQLite.")
            self.refresh()
        self._actualizar_estado()
        self._habilitar_controles(error is None or operacion == "cerrar")
        if self._cierre_pendiente:
            if operacion == "cerrar" and self._cerrado:
                self._cierre_pendiente = False
                QTimer.singleShot(0, self.close)
            elif operacion != "cerrar":
                QTimer.singleShot(
                    0,
                    lambda: self._ejecutar_en_trabajador(
                        "cerrar", self.componentes.coordinador.detener_control
                    ),
                )

    def _habilitar_controles(self, habilitados: bool):
        for boton in (self.start_button, self.pause_button, self.stop_button):
            boton.setEnabled(habilitados)

    def closeEvent(self, event):
        if self._cerrado:
            self._ejecutor_ciclo.shutdown(wait=False)
            super().closeEvent(event)
            return
        event.ignore()
        self._cierre_pendiente = True
        self._sondeo.stop()
        if self._futuro is None:
            self._ejecutar_en_trabajador(
                "cerrar", self.componentes.coordinador.detener_control
            )


def main() -> None:
    app = QApplication(sys.argv)
    componentes = crear_nucleo(Path.home() / ".holocontrol" / "holocontrol.sqlite3")
    window = MainWindow(componentes)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
