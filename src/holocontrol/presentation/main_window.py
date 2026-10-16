"""Interfaz Kinex. Sin captura, reconocimiento ni acciones de Windows."""
from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from holocontrol.presentation.motion import (
    AnimatedStack,
    MotionButton,
    MotionCard,
    SmoothScrollArea,
    Toast,
)
from holocontrol.presentation.preferences import ACTIONS, DEFAULT_GESTURES, Preferences
from holocontrol.presentation.theme import stylesheet
from holocontrol.presentation.visuals import DrawingCanvas, HandMap, HandPreview, SensitivityDial
from holocontrol.presentation.widgets import icon


def label(value, kind=''):
    item = QLabel(value)
    item.setWordWrap(True)
    item.setObjectName(kind)
    return item


def button(value, callback=None, kind=''):
    item = MotionButton(value)
    item.setObjectName(kind)
    item.setMinimumHeight(40)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        item.clicked.connect(callback)
    return item


def panel(title=''):
    frame = MotionCard()
    frame.setObjectName('panel')
    box = QVBoxLayout(frame)
    box.setContentsMargins(20, 18, 20, 18)
    box.setSpacing(12)
    if title:
        box.addWidget(label(title, 'cardTitle'))
    return frame, box


class MainWindow(QMainWindow):
    def __init__(self, settings=None, enable_tray=True):
        super().__init__()
        self.preferences = Preferences(settings)
        QApplication.instance().setProperty('kinexMotion', not self.preferences.data.get('reduce_motion', False))
        self.mode = 'Cursor'
        self.tray = None
        self.setWindowTitle('Kinex · Control por gestos')
        self.setWindowIcon(icon('dashboard'))
        self.resize(1440, 940)
        self.setMinimumSize(1000, 700)
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 24, 0)
        shell.setSpacing(24)
        rail = QFrame()
        rail.setObjectName('rail')
        self.rail = rail
        rail.setFixedWidth(206)
        nav = QVBoxLayout(rail)
        nav.setContentsMargins(16, 30, 16, 22)
        nav.setSpacing(7)
        brand = label('kinex<span style="color:#69bdff">.</span>', 'brand')
        brand.setAlignment(Qt.AlignmentFlag.AlignLeft)
        nav.addWidget(brand)
        self.brand_caption = label('TU MOVIMIENTO, TU CONTROL', 'eyebrow')
        nav.addWidget(self.brand_caption)
        nav.addSpacing(32)
        self.nav_caption = label('TU ESPACIO', 'eyebrow')
        nav.addWidget(self.nav_caption)
        nav.addSpacing(6)
        self.names = ['Inicio', 'Perfiles', 'Calibración', 'Gestos', 'Dibujo', 'Diagnóstico', 'Configuración', 'Acerca de']
        symbols = ['home', 'profile', 'target', 'dashboard', 'image', 'chart', 'settings', 'info']
        self.nav_buttons = {}
        for index, (name, symbol) in enumerate(zip(self.names, symbols)):
            item = button('  ' + name, lambda checked=False, i=index: self.navigate(i), 'nav')
            item.setIcon(icon(symbol))
            item.setIconSize(QSize(23, 23))
            item.setMinimumHeight(46)
            item.setCheckable(True)
            item.setToolTip(name)
            item.setAccessibleName(name)
            nav.addWidget(item)
            self.nav_buttons[name] = item
        nav.addStretch()
        self.sidebar_note = label('Hecho para adaptarse a ti.\nVersión 0.2 · Escritorio', 'muted')
        nav.addWidget(self.sidebar_note)
        nav.addSpacing(16)
        self.utility_buttons = []
        for title, symbol, callback in [('Minimizar a la bandeja', 'minimize', self.minimize_to_tray), ('Salir de Kinex', 'power', self.close)]:
            item = button('  ' + ('Minimizar' if symbol == 'minimize' else 'Salir'), callback, 'nav')
            item.setIcon(icon(symbol))
            item.setToolTip(title)
            item.setAccessibleName(title)
            nav.addWidget(item)
            self.utility_buttons.append(item)
        shell.addWidget(rail)
        content = QVBoxLayout()
        content.setSpacing(8)
        content.setContentsMargins(0, 16, 0, 12)
        header = QHBoxLayout()
        self.breadcrumb = label('ESPACIO PERSONAL  /  INICIO', 'eyebrow')
        self.breadcrumb.setWordWrap(False)
        header.addWidget(self.breadcrumb)
        header.addStretch()
        header.addWidget(label('●  Modo local', 'statusPill'))
        header.addSpacing(10)
        self.header_profile = button('General', lambda: self.navigate(1), 'profileChip')
        self.header_profile.setIcon(icon('profile'))
        header.addWidget(self.header_profile)
        content.addLayout(header)
        content.addSpacing(12)
        self.stack = AnimatedStack()
        content.addWidget(self.stack, 1)
        self.feedback = label('Control detenido · configura tu perfil para preparar Kinex.', 'muted')
        self.feedback.setAccessibleName('Mensajes de estado')
        content.addWidget(self.feedback)
        shell.addLayout(content, 1)
        self.build_dashboard()
        self.build_profiles()
        self.build_calibration()
        self.build_gestures()
        self.build_drawing()
        self.build_diagnostics()
        self.build_settings()
        self.build_about()
        content.insertWidget(content.count() - 1, self.control_panel)
        self.toast = Toast(self)
        self.shortcut = QShortcut(QKeySequence(self.preferences.data['pause_shortcut']), self)
        self.shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.shortcut.activated.connect(self.pause_control)
        self.refresh()
        self.navigate(0)
        self.apply_theme()
        if enable_tray:
            self.setup_tray()
        if self.preferences.load_error:
            self.feedback.setText('No se pudieron leer las preferencias anteriores. Se abrió un perfil nuevo.')
        if self.preferences.data['start_minimized'] and self.tray:
            QTimer.singleShot(0, self.minimize_to_tray)

    @property
    def profile(self):
        return self.preferences.profile

    def save(self, message='Preferencias guardadas.', notify=True):
        try:
            self.preferences.save()
            self.feedback.setText(message)
            if notify and hasattr(self, 'toast') and self.isVisible() and self.preferences.data['notifications']:
                self.toast.show_message(message)
            return True
        except OSError as error:
            self.feedback.setText(str(error))
            return False

    def page(self, title=None, subtitle=None, *, scrollable=True):
        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName('page')
        box = QVBoxLayout(body)
        box.setContentsMargins(0, 0, 8, 8)
        box.setSpacing(16)
        if title:
            box.addWidget(label(title, 'heading'))
        if subtitle:
            box.addWidget(label(subtitle, 'muted'))
        scroll.setWidget(body)
        if scrollable:
            self.stack.addWidget(scroll)
        else:
            scroll.takeWidget()
            scroll.deleteLater()
            self.stack.addWidget(body)
        return box

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        self.breadcrumb.setText('ESPACIO PERSONAL  /  ' + self.names[index].upper())
        for i, item in enumerate(self.nav_buttons.values()):
            item.setChecked(i == index)
        if index == 4:
            self.set_mode('Dibujo')

    def build_dashboard(self):
        box = self.page(scrollable=False)
        box.setSpacing(6)
        intro = QHBoxLayout()
        words = QVBoxLayout()
        words.setSpacing(4)
        words.addWidget(label('Tu espacio. A tu ritmo.', 'heroTitle'))
        words.addWidget(label('Pequeños gestos, nuevas posibilidades. Prepara tu experiencia.', 'muted'))
        intro.addLayout(words, 1)
        prepare = button('Preparar mi perfil', lambda: self.navigate(2), 'primary')
        prepare.setIcon(icon('sparkle', '#ffffff'))
        intro.addWidget(prepare, alignment=Qt.AlignmentFlag.AlignVCenter)
        box.addLayout(intro)
        box.addSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(16)
        self.preview = HandPreview()
        top.addWidget(self.preview, 60)
        state, sb = panel('Estado de tu espacio')
        sb.setContentsMargins(12, 8, 12, 8)
        sb.setSpacing(2)
        state.setMinimumWidth(265)
        self.camera_status_label = label('No conectada', 'muted')
        self.recognition_status_label = label('No conectado', 'muted')
        for title, value, status_widget in (
            ('Cámara', 'No conectada', self.camera_status_label),
            ('Reconocimiento', 'No conectado', self.recognition_status_label),
        ):
            row = QHBoxLayout()
            row.addWidget(label(title))
            row.addStretch()
            row.addWidget(status_widget)
            sb.addLayout(row)
            sb.addWidget(self.separator())
        row = QHBoxLayout()
        row.addWidget(label('Perfil activo'))
        self.profile_badge = button('General', lambda: self.navigate(1), 'link')
        self.profile_badge.setMinimumHeight(30)
        row.addWidget(self.profile_badge)
        sb.addLayout(row)
        sb.addWidget(self.separator())
        for name, unit in [('Precisión', 'Sin datos'), ('Latencia', 'Sin datos')]:
            row = QHBoxLayout()
            row.addWidget(label(name, 'small'))
            row.addStretch()
            row.addWidget(label(unit, 'muted'))
            sb.addLayout(row)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            sb.addWidget(bar)
        sb.addStretch()
        sb.addWidget(label('01  /  Prepara tu movimiento', 'accent'))
        sb.addWidget(button('Ir a calibración  →', lambda: self.navigate(2), 'secondary'))
        top.addWidget(state, 40)
        box.addLayout(top, 6)
        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        quick, qb = panel('Gestos rápidos')
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, title in enumerate(getattr(self, 'quick_gesture_names', ['Seleccionar', 'Clic', 'Arrastrar', 'Desplazar', 'Pausar', 'Pestañas'])):
            item = button('', lambda checked=False, index=i: self.open_gesture(index), 'gesture')
            item.setStyleSheet('QPushButton#gesture { padding: 2px; }')
            tile = QVBoxLayout(item)
            tile.setContentsMargins(2, 4, 2, 4)
            tile.setSpacing(6)
            glyph = QLabel()
            glyph.setPixmap(icon(['cursor', 'click', 'drag', 'scroll', 'pause', 'tabs'][i]).pixmap(24, 24))
            glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caption = label(title, 'tileCaption')
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for child in (glyph, caption):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                tile.addWidget(child)
            item.setAccessibleName(title)
            item.setMinimumHeight(56)
            item.setToolTip('Configurar: ' + title)
            grid.addWidget(item, i // 3, i % 3)
        qb.addLayout(grid)
        bottom.addWidget(quick, 28)
        stats, st = panel('Datos de interacción')
        self.metric_labels = {}
        tabs = QTabWidget()
        for name, rows in [('Sesión', [('Gestos detectados', '—'), ('Tiempo de sesión', '—'), ('Gestos por minuto', '—')]), ('Gestos', [('Último gesto', 'Sin datos'), ('Confianza', '—'), ('Falsos positivos', '—')]), ('Rendimiento', [('Fotogramas / s', '—'), ('Latencia', '—'), ('Estado', 'Detenido')])]:
            page = QWidget()
            column = QVBoxLayout(page)
            column.setSpacing(4)
            column.setContentsMargins(0, 10, 0, 0)
            for title, value in rows:
                metric_row = QHBoxLayout()
                metric_row.addWidget(label(title, 'muted'), 1)
                metric = label(value, 'metric')
                self.metric_labels[title] = metric
                metric_row.addWidget(metric)
                column.addLayout(metric_row)
            column.addStretch()
            tabs.addTab(page, name)
        st.addWidget(tabs)
        st.addWidget(button('Ver diagnóstico', lambda: self.navigate(5), 'link'))
        bottom.addWidget(stats, 30)
        sensitivity, se = panel('Sensibilidad')
        presets = QHBoxLayout()
        for title, value in [('Baja', 60), ('Media', 100), ('Alta', 160)]:
            presets.addWidget(button(title, lambda checked=False, v=value: self.apply_sensitivity_preset(v), 'chip'))
        se.addLayout(presets)
        self.dial = SensitivityDial()
        self.dial.setMinimumSize(90, 60)
        se.addWidget(self.dial, 1)
        self.sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity.setRange(25, 200)
        self.sensitivity.setAccessibleName('Sensibilidad del perfil')
        self.sensitivity.valueChanged.connect(self.set_sensitivity)
        self.sensitivity.sliderReleased.connect(lambda: self.save('Sensibilidad guardada.'))
        se.addWidget(self.sensitivity)
        se.addWidget(label('Preferencia del perfil', 'muted'))
        bottom.addWidget(sensitivity, 24)
        hand, hb = panel('Mapa de mano')
        hand_map = HandMap()
        hand_map.setMinimumSize(90, 90)
        hb.addWidget(hand_map, 1)
        hb.addWidget(label('21 puntos de referencia\nIlustración, sin señal', 'muted'))
        bottom.addWidget(hand, 18)
        for card in (quick, stats, sensitivity, hand):
            card.layout().setContentsMargins(12, 8, 12, 8)
            card.layout().setSpacing(4)
        box.addLayout(bottom, 4)
        actions, ab = panel()
        ab.setContentsMargins(12, 8, 12, 8)
        row = QHBoxLayout()
        self.control_status_label = label('●  Control detenido', 'accent')
        row.addWidget(self.control_status_label)
        row.addStretch()
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(['Cursor', 'Dibujo'])
        self.mode_selector.setAccessibleName('Modo de interacción')
        self.mode_selector.currentTextChanged.connect(self.set_mode)
        row.addWidget(self.mode_selector)
        self.start_button = button('Iniciar', kind='primary')
        self.start_button.setEnabled(False)
        self.start_button.setToolTip('Se habilitará al integrar el reconocimiento.')
        self.start_button.setIcon(icon('play'))
        row.addWidget(self.start_button)
        self.pause_button = button('Pausar', self.pause_control)
        self.stop_button = button('Detener', self.stop_control)
        row.addWidget(self.pause_button)
        row.addWidget(self.stop_button)
        row.addWidget(button('Calibrar', lambda: self.navigate(2)))
        ab.addLayout(row)
        self.control_panel = actions

    def separator(self):
        line = QFrame()
        line.setObjectName('separator')
        line.setFixedHeight(1)
        return line

    def set_sensitivity(self, value):
        self.profile['sensitivity'] = value
        self.dial.value = value
        self.dial.update()
        if hasattr(self, 'cal_sensitivity'):
            self.cal_sensitivity.setValue(value)

    def apply_sensitivity_preset(self, value):
        self.sensitivity.setValue(value)
        self.save('Sensibilidad guardada.')

    def set_mode(self, value):
        self.mode = value
        self.mode_selector.blockSignals(True)
        self.mode_selector.setCurrentText(value)
        self.mode_selector.blockSignals(False)
        self.feedback.setText(f'Modo {value.lower()} seleccionado · control detenido.')

    def pause_control(self):
        self.feedback.setText('Control detenido: no hay un motor activo que pausar.')

    def stop_control(self):
        self.feedback.setText('Control detenido. No se ejecutan acciones del sistema.')

    def build_profiles(self):
        box = self.page('Tus perfiles', 'Una experiencia para cada persona. Los perfiles se guardan en este equipo.')
        card, cb = panel('Perfiles locales')
        self.profile_list = QListWidget()
        self.profile_list.setMinimumHeight(230)
        cb.addWidget(self.profile_list)
        row = QHBoxLayout()
        for title, callback, kind in [('Crear perfil', self.create_profile, 'primary'), ('Usar perfil', self.select_profile, ''), ('Editar', self.edit_profile, ''), ('Eliminar', self.delete_profile, '')]:
            row.addWidget(button(title, callback, kind))
        cb.addLayout(row)
        box.addWidget(card)
        box.addWidget(label('La calibración seguirá pendiente hasta recibir una medición válida del módulo de visión.', 'muted'))
        box.addStretch()

    def profile_dialog(self, profile=None):
        dialog = QDialog(self)
        dialog.setWindowTitle('Editar perfil' if profile else 'Crear perfil')
        dialog.setMinimumWidth(400)
        form = QFormLayout(dialog)
        name = QLineEdit(profile['name'] if profile else '')
        name.setMaxLength(40)
        name.setPlaceholderText('Nombre del perfil')
        hand = QComboBox()
        hand.addItems(['Derecha', 'Izquierda'])
        hand.setCurrentText(profile['hand'] if profile else 'Derecha')
        form.addRow('Nombre', name)
        form.addRow('Mano dominante', hand)
        error = label('', 'error')
        form.addRow(error)
        actions = QDialogButtonBox()
        accept = actions.addButton('Guardar', QDialogButtonBox.ButtonRole.AcceptRole)
        actions.addButton('Cancelar', QDialogButtonBox.ButtonRole.RejectRole)
        accept.setEnabled(bool(name.text().strip()))
        name.textChanged.connect(lambda value: accept.setEnabled(bool(value.strip())))
        def validate():
            try:
                self.preferences.validate_name(name.text(), profile['id'] if profile else None)
            except ValueError as problem:
                error.setText(str(problem))
                return
            dialog.accept()
        actions.accepted.connect(validate)
        actions.rejected.connect(dialog.reject)
        form.addRow(actions)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return name.text().strip(), hand.currentText()
        return None

    def create_profile(self):
        result = self.profile_dialog()
        if result:
            self.preferences.add(*result)
            self.save('Perfil creado y seleccionado.')
            self.refresh()

    def selected_profile(self):
        item = self.profile_list.currentItem()
        if item:
            return next(p for p in self.preferences.data['profiles'] if p['id'] == item.data(Qt.ItemDataRole.UserRole))
        return None

    def select_profile(self):
        selected = self.selected_profile()
        if selected:
            self.preferences.data['active'] = selected['id']
            self.refresh()
            self.save('Perfil seleccionado: ' + selected['name'])

    def edit_profile(self):
        selected = self.selected_profile()
        if selected:
            result = self.profile_dialog(selected)
            if result:
                selected['name'], selected['hand'] = result
                self.save('Perfil actualizado.')
                self.refresh()

    def confirm(self, title, message):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        accept = dialog.addButton('Confirmar', QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton('Cancelar', QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        return dialog.clickedButton() is accept

    def delete_profile(self):
        selected = self.selected_profile()
        if not selected:
            return
        if len(self.preferences.data['profiles']) == 1:
            self.feedback.setText('Conserva al menos un perfil. Puedes editar el actual.')
            return
        if self.confirm('Eliminar perfil', f"¿Eliminar «{selected['name']}» y sus preferencias?"):
            self.preferences.remove(selected['id'])
            self.save('Perfil eliminado.')
            self.refresh()

    def build_calibration(self):
        box = self.page('Calibración individual', 'Prepara tu espacio y ajusta las preferencias del perfil activo.')
        self.cal_step = 0
        self.cal_steps = [
            ('1 · Preparación', 'Siéntate en una posición cómoda. Evita luces intensas detrás de ti y deja espacio para mover la mano.'),
            ('2 · Detección', 'Al integrar la cámara, aquí se comprobará la mano. Por ahora no hay señal ni detección disponible.'),
            ('3 · Zona y respuesta', 'Define la sensibilidad y el suavizado. La zona de trabajo se medirá con el módulo de visión.'),
            ('4 · Prueba', 'El cursor podrá probarse cuando estén conectados el reconocimiento y las acciones de Windows.'),
            ('5 · Confirmación', 'Guarda las preferencias de respuesta. La calibración seguirá pendiente hasta realizar una medición real.'),
        ]
        card, cb = panel('Asistente de calibración')
        self.cal_title = label('', 'cardTitle')
        self.cal_description = label('')
        cb.addWidget(self.cal_title)
        cb.addWidget(self.cal_description)
        cb.addWidget(label('○  Cámara no conectada · no se ha detectado una mano', 'accent'))
        form = QFormLayout()
        self.cal_sensitivity = QSpinBox()
        self.cal_sensitivity.setRange(25, 200)
        self.cal_sensitivity.setSuffix(' %')
        self.smoothing = QSpinBox()
        self.smoothing.setRange(0, 100)
        self.smoothing.setSuffix(' %')
        form.addRow('Sensibilidad', self.cal_sensitivity)
        form.addRow('Suavizado', self.smoothing)
        cb.addLayout(form)
        row = QHBoxLayout()
        self.cal_previous = button('Anterior', lambda: self.cal_move(-1))
        self.cal_next = button('Siguiente', lambda: self.cal_move(1), 'primary')
        row.addWidget(self.cal_previous)
        row.addWidget(self.cal_next)
        row.addWidget(button('Repetir', self.cal_restart))
        cb.addLayout(row)
        self.save_cal_button = button('Guardar preferencias', self.save_calibration_preferences)
        cb.addWidget(self.save_cal_button)
        box.addWidget(card)
        box.addStretch()
        self.update_cal_step()

    def cal_move(self, delta):
        self.cal_step = max(0, min(4, self.cal_step + delta))
        self.update_cal_step()

    def cal_restart(self):
        self.cal_step = 0
        self.update_cal_step()

    def update_cal_step(self):
        title, description = self.cal_steps[self.cal_step]
        self.cal_title.setText(title)
        self.cal_description.setText(description)
        self.cal_previous.setEnabled(self.cal_step > 0)
        self.cal_next.setEnabled(self.cal_step < 4)
        self.save_cal_button.setEnabled(self.cal_step == 4)

    def save_calibration_preferences(self):
        self.profile['sensitivity'] = self.cal_sensitivity.value()
        self.profile['smoothing'] = self.smoothing.value()
        self.refresh()
        self.save('Preferencias guardadas. Calibración pendiente de una medición real.')

    def build_gestures(self):
        box = self.page('Gestos y acciones', 'Configura las asignaciones del perfil. Guarda los cambios antes de cambiar de perfil.')
        card, cb = panel('Asignaciones del perfil')
        grid = QGridLayout()
        for col, name in enumerate(['Gesto', 'Acción', 'Activo', 'Atajo opcional']):
            grid.addWidget(label(name, 'muted'), 0, col)
        self.gesture_fields = {}
        for row, gesture in enumerate(DEFAULT_GESTURES, 1):
            combo = QComboBox()
            combo.addItems(ACTIONS)
            combo.setAccessibleName('Acción para ' + gesture)
            enabled = QCheckBox()
            enabled.setAccessibleName('Activar ' + gesture)
            shortcut = QKeySequenceEdit()
            shortcut.findChild(QLineEdit).setPlaceholderText('Pulsa el atajo')
            shortcut.setAccessibleName('Atajo para ' + gesture)
            combo.currentTextChanged.connect(lambda value, field=shortcut: field.setEnabled(value == 'Atajo de teclado'))
            grid.addWidget(label(gesture), row, 0)
            grid.addWidget(combo, row, 1)
            grid.addWidget(enabled, row, 2)
            grid.addWidget(shortcut, row, 3)
            self.gesture_fields[gesture] = (combo, enabled, shortcut)
        cb.addLayout(grid)
        self.gesture_error = label('', 'error')
        cb.addWidget(self.gesture_error)
        row = QHBoxLayout()
        row.addWidget(button('Guardar asignaciones', self.save_gestures, 'primary'))
        row.addWidget(button('Restaurar predeterminados', self.restore_gestures))
        test = button('Probar gesto')
        test.setEnabled(False)
        test.setToolTip('Requiere reconocimiento de gestos.')
        row.addWidget(test)
        cb.addLayout(row)
        box.addWidget(card)
        advanced, ab = panel('Reconocimiento personalizado')
        form = QFormLayout()
        self.threshold = QSpinBox()
        self.threshold.setRange(50, 100)
        self.threshold.setSuffix(' %')
        form.addRow('Umbral de confianza', self.threshold)
        ab.addLayout(form)
        train = button('Capturar muestras de un gesto propio')
        train.setEnabled(False)
        ab.addWidget(train)
        ab.addWidget(label('La captura y prueba de gestos requieren el módulo de visión artificial.', 'muted'))
        box.addWidget(advanced)
        box.addStretch()

    def open_gesture(self, index):
        self.navigate(3)
        list(self.gesture_fields.values())[index][0].setFocus()

    def save_gestures(self):
        assignments = {}
        shortcuts = set()
        for gesture, (combo, enabled, shortcut) in self.gesture_fields.items():
            key = shortcut.keySequence().toString()
            if enabled.isChecked() and combo.currentText() == 'Atajo de teclado':
                if not key:
                    self.gesture_error.setText('Especifica un atajo para ' + gesture + '.')
                    return
                if key in shortcuts or key == self.preferences.data['pause_shortcut']:
                    self.gesture_error.setText('El atajo está duplicado o coincide con la pausa de Kinex.')
                    return
                shortcuts.add(key)
            assignments[gesture] = {'action': combo.currentText(), 'enabled': enabled.isChecked(), 'shortcut': key}
        self.profile['gestures'] = assignments
        self.profile['threshold'] = self.threshold.value()
        self.gesture_error.clear()
        self.save('Asignaciones guardadas. No se ejecutan acciones sin el motor.')

    def restore_gestures(self):
        if self.confirm('Restaurar gestos', '¿Reemplazar las asignaciones por las predeterminadas?'):
            self.preferences.reset_gestures()
            self.refresh()
            self.save('Asignaciones predeterminadas restauradas.')

    def build_drawing(self):
        box = self.page('Tu lienzo', 'Dibuja con el mouse para probar la interfaz. El dibujo con gestos se conectará después.')
        card, cb = panel()
        tools = QHBoxLayout()
        tools.addWidget(button('Color', self.choose_color))
        self.stroke_width = QSpinBox()
        self.stroke_width.setRange(1, 30)
        self.stroke_width.setValue(4)
        self.stroke_width.setSuffix(' px')
        self.stroke_width.setAccessibleName('Grosor del trazo')
        tools.addWidget(self.stroke_width)
        self.canvas = DrawingCanvas()
        self.stroke_width.valueChanged.connect(lambda value: setattr(self.canvas, 'width_value', value))
        tools.addWidget(button('Deshacer', self.canvas.undo))
        tools.addWidget(button('Borrar lienzo', self.clear_canvas))
        tools.addStretch()
        tools.addWidget(button('Guardar PNG', self.save_drawing, 'primary'))
        cb.addLayout(tools)
        cb.addWidget(self.canvas, 1)
        box.addWidget(card, 1)

    def choose_color(self):
        color = QColorDialog.getColor(self.canvas.color, self, 'Color del trazo')
        if color.isValid():
            self.canvas.color = color

    def clear_canvas(self):
        if self.canvas.strokes and self.confirm('Borrar lienzo', '¿Borrar todos los trazos?'):
            self.canvas.clear()

    def save_drawing(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Guardar dibujo', 'kinex-dibujo.png', 'Imagen PNG (*.png)')
        if path:
            if not path.lower().endswith('.png'):
                path += '.png'
            self.feedback.setText('Dibujo guardado.' if self.canvas.export(path) else 'No se pudo guardar. Revisa la carpeta de destino.')

    def build_diagnostics(self):
        box = self.page('Diagnóstico', 'Estado de los módulos y datos de la sesión.')
        card, cb = panel('Conexiones del sistema')
        for title in ['Captura de cámara', 'Reconocimiento de mano', 'Acciones de Windows', 'Comandos de voz']:
            row = QHBoxLayout()
            row.addWidget(label(title))
            row.addStretch()
            row.addWidget(label('Pendiente de integración', 'muted'))
            cb.addLayout(row)
            cb.addWidget(self.separator())
        cb.addWidget(label('Sin sesiones ni métricas registradas. FPS, confianza, latencia y uso de recursos aparecerán cuando exista una fuente real de datos.', 'muted'))
        box.addWidget(card)
        box.addStretch()

    def build_settings(self):
        box = self.page('Configuración', 'Apariencia, comportamiento de la ventana y preferencias de voz.')
        card, cb = panel('Apariencia y accesibilidad')
        form = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItems(['Oscuro', 'Claro', 'Sistema', 'Alto contraste'])
        self.theme.setCurrentText(self.preferences.data['theme'])
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 18)
        self.font_size.setValue(self.preferences.data['font_size'])
        self.font_size.setSuffix(' px')
        self.preview_toggle = QCheckBox('Mostrar imagen ilustrativa en Inicio')
        self.preview_toggle.setChecked(self.preferences.data['preview'])
        self.reduce_motion = QCheckBox('Reducir movimiento y transiciones')
        self.reduce_motion.setChecked(self.preferences.data.get('reduce_motion', False))
        form.addRow('Tema', self.theme)
        form.addRow('Tamaño del texto', self.font_size)
        form.addRow(self.preview_toggle)
        form.addRow(self.reduce_motion)
        cb.addLayout(form)
        box.addWidget(card)
        behavior, bb = panel('Ventana y acceso rápido')
        form = QFormLayout()
        self.minimize_toggle = QCheckBox('Enviar a la bandeja al minimizar')
        self.minimize_toggle.setChecked(self.preferences.data['minimize_tray'])
        self.start_minimized = QCheckBox('Abrir minimizado en la bandeja')
        self.start_minimized.setChecked(self.preferences.data['start_minimized'])
        self.notifications = QCheckBox('Mostrar avisos al minimizar')
        self.notifications.setChecked(self.preferences.data['notifications'])
        self.pause_key = QKeySequenceEdit(QKeySequence(self.preferences.data['pause_shortcut']))
        self.pause_key.findChild(QLineEdit).setPlaceholderText('Pulsa el atajo')
        form.addRow(self.minimize_toggle)
        form.addRow(self.start_minimized)
        form.addRow(self.notifications)
        form.addRow('Atajo de pausa en Kinex', self.pause_key)
        bb.addLayout(form)
        bb.addWidget(label('El atajo funciona mientras Kinex tiene el foco. El atajo global se integrará con el módulo de Windows.', 'muted'))
        box.addWidget(behavior)
        camera, cam = panel('Dispositivos')
        selector = QComboBox()
        self.camera_selector = selector
        selector.addItem('Sin proveedor de cámaras conectado')
        selector.setEnabled(False)
        cam.addWidget(selector)
        self.camera_hint = label('La lista de cámaras y la vista en directo dependen del módulo de visión artificial.', 'muted')
        cam.addWidget(self.camera_hint)
        box.addWidget(camera)
        voice, vb = panel('Voz y dictado')
        form = QFormLayout()
        self.voice_phrase = QLineEdit()
        self.voice_phrase.setPlaceholderText('Por ejemplo: pausar control')
        self.voice_action = QComboBox()
        self.voice_action.addItems([a for a in ACTIONS if a not in ['Sin asignar', 'Atajo de teclado']])
        self.dictation_limit = QSpinBox()
        self.dictation_limit.setRange(20, 2000)
        form.addRow('Frase', self.voice_phrase)
        form.addRow('Acción', self.voice_action)
        form.addRow('Límite de dictado', self.dictation_limit)
        vb.addLayout(form)
        self.voice_list = QListWidget()
        self.voice_list.setMinimumHeight(100)
        vb.addWidget(self.voice_list)
        row = QHBoxLayout()
        row.addWidget(button('Añadir comando', self.add_voice_command))
        row.addWidget(button('Eliminar seleccionado', self.remove_voice_command))
        vb.addLayout(row)
        vb.addWidget(label('Escucha desactivada. Las frases se guardan como preferencias; el reconocimiento y la confirmación de dictado requieren el motor de audio.', 'muted'))
        box.addWidget(voice)
        box.addWidget(button('Guardar configuración', self.save_settings, 'primary'), alignment=Qt.AlignmentFlag.AlignLeft)
        box.addStretch()

    def add_voice_command(self):
        phrase = self.voice_phrase.text().strip()
        commands = self.profile['voice']
        if not phrase or any(c['phrase'].casefold() == phrase.casefold() for c in commands):
            self.feedback.setText('Escribe una frase no vacía y diferente de las existentes.')
            return
        commands.append({'phrase': phrase, 'action': self.voice_action.currentText()})
        self.voice_phrase.clear()
        self.refresh_voice()
        self.save('Comando guardado en el perfil. Escucha desactivada.')

    def remove_voice_command(self):
        index = self.voice_list.currentRow()
        if index >= 0:
            self.profile['voice'].pop(index)
            self.refresh_voice()
            self.save('Comando eliminado.')

    def refresh_voice(self):
        self.voice_list.clear()
        for command in self.profile['voice']:
            self.voice_list.addItem(command['phrase'] + ' → ' + command['action'])

    def save_settings(self):
        key = self.pause_key.keySequence().toString()
        if not key:
            self.feedback.setText('Elige un atajo de pausa antes de guardar.')
            return
        for value in self.profile['gestures'].values():
            if value['enabled'] and value['action'] == 'Atajo de teclado' and value['shortcut'] == key:
                self.feedback.setText('El atajo de pausa coincide con una asignación de gesto.')
                return
        self.preferences.data.update(theme=self.theme.currentText(), font_size=self.font_size.value(), preview=self.preview_toggle.isChecked(), minimize_tray=self.minimize_toggle.isChecked(), start_minimized=self.start_minimized.isChecked(), notifications=self.notifications.isChecked(), pause_shortcut=key)
        self.profile['dictation_limit'] = self.dictation_limit.value()
        self.preferences.data['reduce_motion'] = self.reduce_motion.isChecked()
        QApplication.instance().setProperty('kinexMotion', not self.reduce_motion.isChecked())
        if self.reduce_motion.isChecked():
            self.stack.finish_transition()
            self.dial.animation.stop()
            self.dial.set_display_value(self.dial.value)
            for control in self.findChildren(MotionButton):
                control.hover_animation.stop()
                control.ripple_animation.stop()
                control.set_ripple(1.0)
            for card in self.findChildren(MotionCard):
                card.animation.stop()
            for scroll in self.findChildren(SmoothScrollArea):
                scroll.wheel_animation.stop()
        self.shortcut.setKey(QKeySequence(key))
        self.preview.show_image = self.preview_toggle.isChecked()
        self.preview.update()
        self.apply_theme()
        self.save('Configuración guardada.')

    def build_about(self):
        box = self.page('Acerca de Kinex', 'Tu movimiento, tu control.')
        card, cb = panel('Una experiencia de interacción accesible')
        cb.addWidget(label('Kinex permite preparar perfiles y preferencias para controlar Windows con gestos. Esta entrega corresponde a la interfaz de escritorio.'))
        cb.addWidget(label('Versión 0.2 · Python + PySide6', 'accent'))
        cb.addWidget(label('Disponible: navegación, perfiles locales, asignaciones, preferencias, lienzo manual y bandeja del sistema.'))
        cb.addWidget(label('Pendiente de integración: cámara, reconocimiento, calibración real, acciones de Windows, voz y métricas.', 'muted'))
        cb.addWidget(label('Cuentas y sincronización: el documento contempla una API posterior. Este modo local no inicia sesión ni envía datos a un servidor.', 'muted'))
        box.addWidget(card)
        box.addStretch()

    def refresh(self):
        self.profile_list.clear()
        for profile in self.preferences.data['profiles']:
            active = profile['id'] == self.preferences.data['active']
            self.profile_list.addItem(profile['name'] + ('  ·  En uso' if active else '') + '  ·  Mano ' + profile['hand'].lower() + '  ·  Calibración pendiente')
            item = self.profile_list.item(self.profile_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, profile['id'])
            if active:
                self.profile_list.setCurrentItem(item)
        self.profile_badge.setText(self.profile['name'])
        self.header_profile.setText(self.profile['name'])
        self.sensitivity.blockSignals(True)
        self.sensitivity.setValue(self.profile['sensitivity'])
        self.sensitivity.blockSignals(False)
        self.dial.value = self.profile['sensitivity']
        self.dial.update()
        self.cal_sensitivity.setValue(self.profile['sensitivity'])
        self.smoothing.setValue(self.profile['smoothing'])
        self.threshold.setValue(self.profile['threshold'])
        self.dictation_limit.setValue(self.profile['dictation_limit'])
        for gesture, (combo, enabled, shortcut) in self.gesture_fields.items():
            value = self.profile['gestures'][gesture]
            combo.setCurrentText(value['action'])
            enabled.setChecked(value['enabled'])
            shortcut.setKeySequence(QKeySequence(value['shortcut']))
            shortcut.setEnabled(value['action'] == 'Atajo de teclado')
        self.refresh_voice()
        self.preview.show_image = self.preferences.data['preview']
        self.preview.update()
        self.cal_restart()

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(icon('dashboard'), self)
        self.tray.setToolTip('Kinex · Control detenido · cámara no conectada')
        menu = QMenu(self)
        menu.addAction('Abrir Kinex', self.restore_window)
        menu.addAction('Pausar control', self.pause_control)
        resume = menu.addAction('Reanudar control')
        resume.setEnabled(False)
        menu.addSeparator()
        menu.addAction('Salir', self.close)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.restore_window() if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.tray.show()

    def minimize_to_tray(self):
        if self.tray and self.tray.isVisible():
            self.hide()
            if self.preferences.data['notifications']:
                self.tray.showMessage('Kinex', 'Kinex sigue abierto. Usa el icono de la bandeja para volver.')
        else:
            self.showMinimized()
            self.feedback.setText('Bandeja no disponible; ventana minimizada en la barra de tareas.')

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized() and hasattr(self, 'preferences') and self.preferences.data['minimize_tray'] and self.tray:
            QTimer.singleShot(0, self.minimize_to_tray)
        super().changeEvent(event)

    def closeEvent(self, event):
        if not self.save('Preferencias guardadas.', notify=False):
            event.ignore()
            return
        if self.tray:
            self.tray.hide()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'rail'):
            return
        compact = self.width() < 1250
        self.rail.setFixedWidth(84 if compact else 206)
        for title, item in self.nav_buttons.items():
            item.setText('' if compact else '  ' + title)
        for item, title in zip(self.utility_buttons, ['Minimizar', 'Salir']):
            item.setText('' if compact else '  ' + title)
        for item in [self.brand_caption, self.nav_caption, self.sidebar_note]:
            item.setVisible(not compact)
        if hasattr(self, 'toast'):
            self.toast.hide()

    def apply_theme(self):
        from pathlib import Path
        theme = self.preferences.data['theme']
        if theme == 'Sistema':
            theme = 'Claro' if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Light else 'Oscuro'
        style = stylesheet(theme, self.preferences.data['font_size'])
        assets = Path(__file__).parent / 'assets'
        style = style.replace('{CHEVRON}', (assets / 'chevron.svg').as_posix())
        style = style.replace('{CHECK}', (assets / 'check.svg').as_posix())
        self.setStyleSheet(style)
