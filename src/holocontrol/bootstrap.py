"""Composition root for the local domain, persistence, vision and Windows actions."""

from __future__ import annotations

import sys
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from queue import Queue, Empty, Full
import pyautogui
from time import monotonic, monotonic_ns

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QComboBox, QCheckBox, QSpinBox, QGridLayout, QLabel

from holocontrol.application.services.adaptador_ejecutor_existente import (
    AdaptadorEjecutorExistente,
)
from holocontrol.application.services.coordinador_control_vision import CoordinadorControlVision
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Mano, Calibracion, AsignacionGesto
from holocontrol.domain.rules.catalogo import GESTOS, ACCIONES
from holocontrol.domain.value_objects.estado_control import EstadoControl
from holocontrol.infrastructure.persistence.conexion import BaseDatos
from holocontrol.infrastructure.persistence.repositorio_perfil import RepositorioPerfilesSQLite
from holocontrol.infrastructure.vision.configuration import (
    ConfiguracionCamara,
    ConfiguracionVision,
)
from holocontrol.infrastructure.vision.vision_worker import AdaptadorVision
from holocontrol.infrastructure.vision.camera import CamaraOpenCV
from holocontrol.infrastructure.vision.errors import ErrorCamara
from holocontrol.infrastructure.windows.windows_action_executor import WindowsActionExecutor
from holocontrol.ports.vision.models import Lateralidad, EstadoVision
from holocontrol.ports.vision.vision_provider import ProveedorVision
from holocontrol.presentation.main_window import MainWindow as DashboardWindow, button, label
from holocontrol.presentation.visuals import HandPreview


def seleccionar_camara(preferido: int, seleccion: int = -1) -> int:
    """Probe cameras without storing images; an explicit selection never falls back."""
    indices = [seleccion] if seleccion >= 0 else list(dict.fromkeys([preferido, 0, 1, 2, 3]))
    for indice in indices:
        camara = CamaraOpenCV(ConfiguracionCamara(indice=indice))
        try:
            camara.abrir()
            camara.leer()
            return indice
        except ErrorCamara:
            continue
        finally:
            camara.cerrar()
    raise ErrorCamara('No se encontró una cámara con imagen. Cierra otras aplicaciones que la usen y revisa los permisos de Windows. Puedes elegir otra cámara en Configuración.')


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

    # Add new defaults once without replacing explicit user assignments.
    for guardado in repositorio.listar():
        # Upgrade the old default click while preserving unrelated custom bindings.
        asignaciones = guardado.asignaciones
        asignaciones = tuple(
            replace(a, id_accion='desplazar_vertical')
            if a.id_gesto == 'dos_dedos' and a.id_accion == 'flechas' else a
            for a in asignaciones if a.id_gesto != 'zoom')
        if not any(a.id_gesto == 'pulgar_abajo' for a in asignaciones):
            asignaciones += (AsignacionGesto(guardado.id, 'pulgar_abajo', 'borrar'),)
        if not any(a.id_gesto == 'pulgar' for a in asignaciones):
            anterior = next((a for a in asignaciones if a.id_gesto == 'pellizco'
                             and a.id_accion == 'clic_izquierdo'), None)
            if anterior is not None:
                asignaciones = tuple(a for a in asignaciones if a is not anterior)
                asignaciones += (AsignacionGesto(guardado.id, 'pulgar', 'clic_izquierdo', anterior.activo),)
            else:
                asignaciones += (AsignacionGesto(guardado.id, 'pulgar', 'clic_izquierdo'),)
        existentes = {a.id_gesto for a in asignaciones}
        nuevas = tuple(AsignacionGesto(guardado.id, gesto, accion)
                       for gesto, accion in (("menique", "enter"), ("cuernos", "escape"), ("deslizamiento_derecha", "volumen_subir"), ("deslizamiento_izquierda", "volumen_bajar"), ("puno", "minimizar"), ("tres_dedos", "cambiar_ventana"), ("like", "dictar"), ("pellizco", "arrastrar"))
                       if gesto not in existentes)
        if nuevas or asignaciones != guardado.asignaciones:
            repositorio.actualizar(replace(guardado, asignaciones=asignaciones + nuevas))
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
        self._futuro_accion: Future | None = None
        self._parar_acciones = Event()
        self._resultados_acciones = Queue(maxsize=1)
        self._operacion_actual: str | None = None
        self._cierre_pendiente = False
        self._cerrado = False
        self._solo_vista_previa = False
        self._inicio_vista_previa = 0.0
        self._resultado_visual = None
        self._esquinas = {}
        self.quick_gesture_names = ['Índice', 'Pulgar', 'Dos dedos', 'Palma', 'Puño', 'Tres dedos']
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
        self.preview_toggle.setText('Mostrar vista de cámara en Inicio')
        self.camera_selector.clear()
        self.camera_selector.addItem('Detectar automáticamente', -1)
        for indice in range(6):
            self.camera_selector.addItem(f'Cámara {indice}', indice)
        seleccion = self.preferences.data.get('camera_selection', -1)
        self.camera_selector.setCurrentIndex(max(0, self.camera_selector.findData(seleccion)))
        self.camera_selector.setEnabled(True)
        self.camera_hint.setText('La detección automática prueba el índice del perfil y las cámaras 0 a 3. Puedes elegir un índice manual; detén y vuelve a iniciar para aplicar el cambio.')
        self.camera_selector.currentIndexChanged.connect(self._guardar_camara)
        cb = self.cal_title.parentWidget().layout()
        self.cal_preview = HandPreview()
        self.cal_preview.setMinimumSize(320, 180)
        self.cal_preview.setMaximumHeight(240)
        self.cal_preview.set_camera_frame(None)
        cb.addWidget(self.cal_preview)
        self.cal_measure_status = label('Abre la cámara en Inicio. Mide dos esquinas de tu zona cómoda con la punta del índice.', 'muted')
        cb.addWidget(self.cal_measure_status)
        cb.addWidget(button('Abrir cámara para calibrar', self._abrir_calibracion))
        cb.addWidget(button('Medir esquina superior izquierda (3 s)', lambda: self._programar_medicion('superior')))
        cb.addWidget(button('Medir esquina inferior derecha (3 s)', lambda: self._programar_medicion('inferior')))
        self.save_cal_button.setText('Guardar calibración')
        self.cal_steps[1] = ('2 · Detección', 'Inicia la cámara y muestra la mano elegida en el perfil. Verás sus 21 puntos en Inicio.')
        self.cal_steps[2] = ('3 · Zona y respuesta', 'Mide ambas esquinas con los botones inferiores. Tienes 3 segundos para colocar el índice en cada posición; puedes volver a Inicio para ver la cámara.')
        self.cal_steps[3] = ('4 · Comprobación', 'Confirma las dos mediciones. La esquina inferior debe estar a la derecha y debajo de la superior en la imagen.')
        self.cal_steps[4] = ('5 · Confirmación', 'Guarda la calibración medida. Después pulsa Iniciar para activar las acciones de Windows.')

    def _abrir_calibracion(self):
        if self._futuro is None:
            self._ejecutar_en_trabajador('preparar calibración', self.componentes.coordinador.detener_control)

    def build_settings(self):
        super().build_settings()
        for text in self.findChildren(QLabel):
            if text.text().startswith('Escucha desactivada.'):
                text.setText('Dictado: haz clic en un campo de texto, muestra un like y espera el aviso de escucha de Windows. Otro like lo detiene. Requiere internet, microfono e idioma de teclado espanol. Las frases personalizadas de esta lista solo se guardan; no activan comandos por voz.')

    def build_gestures(self):
        box = self.page('Gestos y acciones de Windows', 'Estas asignaciones pertenecen al perfil de SQLite y son las que usa el control.')
        self.gesture_fields = {}  # The standalone dashboard has a separate preference schema.
        self.core_gesture_fields = {}
        grid = QGridLayout()
        for col, title in enumerate(('Gesto reconocido', 'Acción de Windows', 'Activo')):
            grid.addWidget(label(title), 0, col)
        gestos = [g for g in GESTOS if g.id not in ('subir', 'bajar')]
        for row, gesto in enumerate(gestos, 1):
            combo = QComboBox()
            for accion in ACCIONES:
                combo.addItem(accion.nombre, accion.id)
            enabled = QCheckBox()
            combo.setAccessibleName('Acción para ' + gesto.nombre)
            enabled.setAccessibleName('Activar ' + gesto.nombre)
            grid.addWidget(label(gesto.nombre), row, 0)
            grid.addWidget(combo, row, 1)
            grid.addWidget(enabled, row, 2)
            self.core_gesture_fields[gesto.id] = (combo, enabled)
        box.addLayout(grid)
        box.addWidget(button('Guardar asignaciones', self.save_gestures, 'primary'))
        box.addWidget(button('Restaurar predeterminados', self.restore_gestures))
        box.addWidget(label('Pulgar lateral: clic; pistola (indice extendido y pulgar levantado): mantener clic y dibujar; dos dedos apuntando arriba o abajo: desplazamiento suave; solo meñique arriba: Enter; solo meñique hacia la izquierda de la pantalla: borrar un carácter, mantener 2 segundos: borrar todo el campo; like: activar/desactivar dictado; palma abierta 7 segundos: pausa; puño cerrado 2 segundos: minimizar una vez. Se usa únicamente la mano seleccionada en el perfil.', 'muted'))
        self.threshold = QSpinBox(self)
        self.threshold.hide()
        box.addStretch()

    def open_gesture(self, index):
        self.navigate(3)
        gesto = ("indice", "pulgar", "dos_dedos", "palma_abierta", "puno", "tres_dedos")[index]
        self.core_gesture_fields[gesto][0].setFocus()

    def save_gestures(self):
        if self._futuro is not None:
            return
        perfil_id = self.componentes.aplicacion.estado_actual().id_perfil_seleccionado
        datos = [(gid, combo.currentData(), enabled.isChecked()) for gid, (combo, enabled) in self.core_gesture_fields.items()]
        def guardar():
            self.componentes.coordinador.detener_control()
            perfil = self.componentes.repositorio.obtener(perfil_id)
            actuales = {a.id_gesto: a for a in perfil.asignaciones}
            for gid, accion, activo in datos:
                anterior = actuales.get(gid)
                if anterior is not None and (anterior.id_accion, anterior.activo) == (accion, activo):
                    continue
                if anterior is None and not activo:
                    continue
                self.componentes.aplicacion.configurar_gesto(perfil_id, gid, accion, activo=activo, reemplazar_existente=True)
        self._ejecutar_en_trabajador('guardar gestos', guardar)

    def restore_gestures(self):
        if self._futuro is not None or not self.confirm('Restaurar gestos', '¿Restaurar las acciones predeterminadas del perfil?'):
            return
        perfil_id = self.componentes.aplicacion.estado_actual().id_perfil_seleccionado
        def restaurar():
            self.componentes.coordinador.detener_control()
            self.componentes.aplicacion.restaurar_asignaciones(perfil_id, confirmado=True)
        self._ejecutar_en_trabajador('guardar gestos', restaurar)

    def _programar_medicion(self, esquina):
        if not self._solo_vista_previa:
            self.cal_measure_status.setText('Detén el control y abre una vista previa de calibración con Calibrar.')
            return
        perfil_id = self.componentes.aplicacion.estado_actual().id_perfil_seleccionado
        self.cal_measure_status.setText('Coloca la punta del índice en la esquina ' + esquina + '. Midiendo en 3 segundos…')
        QTimer.singleShot(3000, lambda: self._medir_esquina(esquina, perfil_id))

    def _medir_esquina(self, esquina, perfil_id):
        resultado = self._resultado_visual
        if (not self._solo_vista_previa or perfil_id != self.componentes.aplicacion.estado_actual().id_perfil_seleccionado
                or resultado is None or not resultado.es_valido
                or monotonic_ns() // 1_000_000 - resultado.instante_ms > 200):
            self.cal_measure_status.setText('No hay una mano válida y reciente. Muestra una mano y repite la medición.')
            return
        punto = resultado.mano.puntos[8]
        self._esquinas[esquina] = (punto.x, punto.y)
        self.cal_measure_status.setText(f'Esquina {esquina}: ({punto.x:.2f}, {punto.y:.2f}). Mediciones: {len(self._esquinas)}/2.')

    def update_cal_step(self):
        super().update_cal_step()
        self.save_cal_button.setEnabled(True)

    def save_calibration_preferences(self):
        if self._futuro is not None:
            return
        perfil_id = self.componentes.aplicacion.estado_actual().id_perfil_seleccionado
        perfil = self.componentes.repositorio.obtener(perfil_id)
        if not self._esquinas:
            anterior = perfil.calibracion or Calibracion(perfil_id)
            x1, x2, y1, y2 = anterior.x_min, anterior.x_max, anterior.y_min, anterior.y_max
        elif set(self._esquinas) == {'superior', 'inferior'}:
            x1, y1 = self._esquinas['superior']
            x2, y2 = self._esquinas['inferior']
        else:
            self.cal_measure_status.setText('Falta medir la otra esquina antes de guardar la zona personalizada.')
            self.cal_description.setText(self.cal_measure_status.text())
            return
        if x2 - x1 < .1 or y2 - y1 < .1:
            self.cal_measure_status.setText('La zona debe abarcar al menos el 10 % de la imagen por eje. Repite las esquinas en el orden indicado.')
            return
        perfil_id = self.componentes.aplicacion.estado_actual().id_perfil_seleccionado
        calibracion = Calibracion(perfil_id, x1, x2, y1, y2, self.cal_sensitivity.value() / 100, self.smoothing.value() / 100)
        def guardar():
            self.componentes.coordinador.detener_control()
            return self.componentes.aplicacion.calibrar_perfil(calibracion)
        self._ejecutar_en_trabajador('calibrar', guardar)

    def _guardar_camara(self):
        self.preferences.data['camera_selection'] = self.camera_selector.currentData()
        self.save('Cámara seleccionada. Se usará en el próximo inicio.')

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
            asignaciones = {a.id_gesto: a for a in seleccionado.asignaciones}
            for gid, (combo, enabled) in self.core_gesture_fields.items():
                asignacion = asignaciones.get(gid)
                combo.setCurrentIndex(combo.findData(asignacion.id_accion) if asignacion else 0)
                enabled.setChecked(asignacion is not None and asignacion.activo)
            if seleccionado.calibracion is not None:
                self.cal_sensitivity.setValue(round(seleccionado.calibracion.sensibilidad * 100))
                self.smoothing.setValue(round(seleccionado.calibracion.suavizado * 100))
        self.profile_list.blockSignals(False)
        if getattr(self, '_perfil_mediciones', None) != estado.id_perfil_seleccionado:
            self._esquinas.clear()
            self._perfil_mediciones = estado.id_perfil_seleccionado

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

    def start_control(self, checked=False, *, vista_previa=False):
        if self._solo_vista_previa and self.componentes.proveedor_vision.en_ejecucion:
            self.feedback.setText('La cámara ya está en vista previa. Detén la cámara antes de iniciar otra sesión.')
            return
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
        if estado.estado is EstadoControl.ACTIVE:
            return
        pantalla = QApplication.primaryScreen()
        if pantalla is None:
            self.feedback.setText("No se detectó una pantalla.")
            return
        # Qt reports logical pixels; mouse injection needs physical pixels.
        ancho_fisico, alto_fisico = pyautogui.size()
        seleccion_camara = self.camera_selector.currentData()

        def iniciar():
            proveedor = self.componentes.proveedor_vision
            if isinstance(proveedor, AdaptadorVision):
                proveedor.configuracion = ConfiguracionVision(
                    mano_dominante=Lateralidad(perfil.mano_dominante.value)
                )
                proveedor.camara = ConfiguracionCamara(
                    indice=seleccionar_camara(perfil.configuracion.indice_camara, seleccion_camara)
                )
            proveedor.activar_vista_previa(True)
            if perfil.calibracion is None or vista_previa:
                proveedor.iniciar()
                return
            if estado.estado is EstadoControl.PAUSED:
                return self.componentes.coordinador.reanudar_control()
            return self.componentes.coordinador.iniciar_control(
                ancho_pantalla=ancho_fisico, alto_pantalla=alto_fisico
            )

        if self._futuro is not None:
            return
        self._solo_vista_previa = perfil.calibracion is None or vista_previa
        self._inicio_vista_previa = monotonic()
        self.preview.set_camera_frame(None)
        self.feedback.setText("Abriendo cámara…" + (" Vista previa; el control necesita calibración." if self._solo_vista_previa else ""))
        self._ejecutar_en_trabajador("vista previa" if self._solo_vista_previa else "iniciar", iniciar)

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
        # One executor serializes actions and lifecycle transitions. Do not
        # display a previous action's completion after a pause/stop/restart.
        self._parar_acciones.set()
        self._futuro_accion = None
        self._sondeo.stop()
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
        self._ciclo_terminado(operacion or "operación", resultado, error)

    def _consultar_vision(self):
        proveedor = self.componentes.proveedor_vision
        fotograma = proveedor.obtener_fotograma()
        self.preview.set_camera_frame(fotograma)
        self.cal_preview.set_camera_frame(fotograma)
        snapshot = getattr(proveedor, 'obtener_resultado_visual', lambda: None)()
        self._resultado_visual = snapshot
        if snapshot is not None:
            if snapshot.es_valido and not self.preview.live_image.isNull():
                self.preview.landmarks = snapshot.mano.puntos
                self.cal_preview.landmarks = snapshot.mano.puntos
            eventos = [e for e in snapshot.eventos_actuales if e.fase.value != 'fin']
            gesto = eventos[-1].nombre if eventos else 'ninguno'
            nombre_gesto = next((g.nombre for g in GESTOS if g.id == gesto), gesto)
            self.metric_labels['Último gesto'].setText(nombre_gesto)
            self.metric_labels['Confianza'].setText(f'{eventos[-1].confianza:.0%}' if eventos else '—')
            self.metric_labels['Latencia'].setText(f'{snapshot.latencia_total_ms:.0f} ms')
            self.recognition_status_label.setText(snapshot.mensaje or ('Gesto: ' + gesto if snapshot.es_valido else snapshot.estado.value.replace('_', ' ')))
        else:
            self.metric_labels['Último gesto'].setText('Sin datos recientes')
            self.metric_labels['Confianza'].setText('—')
        if self._solo_vista_previa:
            resultado = proveedor.obtener_resultado()
            estado = proveedor.estado
            self.camera_status_label.setText('Disponible' if proveedor.camara_disponible else 'Abriendo…')
            if snapshot is None:
                self.recognition_status_label.setText('Esperando reconocimiento')
            self.control_status_label.setText('●  Vista previa · calibración pendiente')
            if estado in (EstadoVision.ERROR_CAMARA, EstadoVision.ERROR_PROCESAMIENTO, EstadoVision.DETENIDO) or (not proveedor.camara_disponible and monotonic() - self._inicio_vista_previa > 10):
                mensaje = resultado.mensaje if resultado is not None and resultado.mensaje else 'La cámara no estuvo disponible. Revisa la conexión, permisos e índice de cámara.'
                self._sondeo.stop()
                self._ejecutar_en_trabajador('error de cámara', self.componentes.coordinador.detener_control)
                self._error_vista_previa = mensaje
            return
        if self._futuro is not None:
            return
        try:
            accion, error = self._resultados_acciones.get_nowait()
        except Empty:
            accion, error = None, None
        if error is not None:
            self._error_vista_previa = f'Control detenido por error: {error}'
            self._ejecutar_en_trabajador('error de cámara', self.componentes.coordinador.detener_control)
            return
        if accion is not None and accion.ejecutado:
            nombre_accion = next((a.nombre for a in ACCIONES if a.id == accion.id_accion), accion.id_accion)
            self.feedback.setText('Acción: ' + str(nombre_accion))
        if accion is not None:
            self._actualizar_estado()
        if snapshot is not None:
            self.recognition_status_label.setText(snapshot.mensaje or ('Gesto: ' + gesto if snapshot.es_valido else snapshot.estado.value.replace('_', ' ')))

    def _procesar_acciones_continuamente(self):
        # No Qt/UI calls: continues while minimized, hidden, or Alt+Tab is open.
        while not self._parar_acciones.is_set():
            try:
                resultado = self.componentes.coordinador.consultar_vision()
                entrega = (resultado, None)
            except Exception as error:
                # Release owned keys/buttons even if the UI is not processing events.
                try:
                    self.componentes.coordinador.detener_control()
                except Exception:
                    pass
                entrega = (None, error)
            try:
                self._resultados_acciones.get_nowait()
            except Empty:
                pass
            try:
                self._resultados_acciones.put_nowait(entrega)
            except Full:
                pass
            if entrega[1] is not None or self.componentes.aplicacion.estado_actual().estado is not EstadoControl.ACTIVE:
                break
            if self._parar_acciones.wait(.01):
                break

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
        self.metric_labels['Estado'].setText(etiqueta.removeprefix('●  Control '))
        if estado.error:
            self.feedback.setText(estado.error)
        if estado.estado is not EstadoControl.ACTIVE and hasattr(self, "_sondeo"):
            self._sondeo.stop()

    def _ciclo_terminado(self, operacion: str, resultado: object, error: object):
        if error is not None:
            self.feedback.setText(f"{operacion.capitalize()} falló: {error}")
            if operacion == "cerrar":
                self._cierre_pendiente = False
        elif operacion == "vista previa":
            self.feedback.setText('Cámara en vista previa. El ratón permanece detenido hasta calibrar el perfil.')
            self._sondeo.start()
        elif operacion == "error de cámara":
            self.feedback.setText(self._error_vista_previa)
        elif operacion == "iniciar":
            self._parar_acciones.clear()
            while not self._resultados_acciones.empty():
                self._resultados_acciones.get_nowait()
            self._futuro_accion = self._ejecutor_ciclo.submit(self._procesar_acciones_continuamente)
            self.feedback.setText(
                "Control activo. Las acciones se habilitaron después de iniciar la cámara."
            )
            self._sondeo.start()
        elif operacion == 'calibrar':
            self.refresh()
            self.feedback.setText('Calibración guardada en el perfil. Pulsa Iniciar para controlar Windows.')
            self.cal_measure_status.setText('Calibración guardada. Vuelve a Inicio y pulsa Iniciar.')
            self.cal_description.setText(self.cal_measure_status.text())
        elif operacion == 'guardar gestos':
            self.refresh()
            self.feedback.setText('Asignaciones guardadas en SQLite. Pulsa Iniciar para aplicarlas.')
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
        if operacion != 'vista previa':
            self._actualizar_estado()
        if error is not None or operacion in ('preparar calibración', 'guardar gestos', 'calibrar', 'pausar', 'detener', 'cerrar', 'error de cámara', 'crear perfil', 'seleccionar perfil', 'editar perfil', 'eliminar perfil'):
            self._solo_vista_previa = False
            self.preview.set_camera_frame(None, active=False)
            self.cal_preview.set_camera_frame(None)
        self._habilitar_controles(True)
        if operacion == 'preparar calibración' and error is None:
            self._esquinas.clear()
            self.start_control(vista_previa=True)
        if error is not None or operacion == 'error de cámara':
            self._aviso_camara = QMessageBox(QMessageBox.Icon.Warning, 'No se pudo completar la operación', self.feedback.text(), parent=self)
            self._aviso_camara.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self._aviso_camara.open()
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
