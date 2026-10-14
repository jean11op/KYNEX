"""Pruebas de UI sin cámara, red, registro del usuario ni acciones del SO."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton
from holocontrol.presentation.main_window import MainWindow
from holocontrol.presentation.preferences import Preferences


class DashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        for font in ['segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'seguisym.ttf']:
            QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)
        self.settings = QSettings(str(self.path / 'ui.ini'), QSettings.Format.IniFormat)
        self.window = MainWindow(self.settings, enable_tray=False)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_navigation_and_unavailable_engine(self):
        for index, item in enumerate(self.window.nav_buttons.values()):
            item.click()
            self.assertEqual(self.window.stack.currentIndex(), index)
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.preview.image.isNull())
        self.window.pause_control()
        self.assertIn('no hay un motor', self.window.feedback.text())

    def test_profile_form_and_reload(self):
        def fill():
            dialog = QApplication.activeModalWidget()
            dialog.findChild(QLineEdit).setText('Ana')
            dialog.findChild(QComboBox).setCurrentText('Izquierda')
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Guardar').click()
        QTimer.singleShot(0, fill)
        self.window.create_profile()
        self.assertEqual(self.window.profile['name'], 'Ana')
        self.window.sensitivity.setValue(160)
        self.window.save()
        restored = Preferences(self.settings)
        self.assertEqual(restored.profile['hand'], 'Izquierda')
        self.assertEqual(restored.profile['sensitivity'], 160)
        with self.assertRaises(ValueError):
            restored.add(' ana ', 'Derecha')

    def test_profile_isolation_and_delete_confirmation(self):
        original_id = self.window.profile['id']
        with patch.object(self.window, 'profile_dialog', return_value=('Ana', 'Izquierda')):
            self.window.create_profile()
        combo, enabled, key = self.window.gesture_fields['Pellizco']
        combo.setCurrentText('Clic derecho')
        self.window.save_gestures()
        self.window.profile_list.setCurrentRow(0)
        self.window.select_profile()
        self.assertEqual(self.window.profile['id'], original_id)
        self.assertEqual(self.window.gesture_fields['Pellizco'][0].currentText(), 'Clic izquierdo')
        self.window.profile_list.setCurrentRow(1)
        with patch.object(self.window, 'confirm', return_value=False):
            self.window.delete_profile()
        self.assertEqual(len(self.window.preferences.data['profiles']), 2)
        with patch.object(self.window, 'confirm', return_value=True):
            self.window.delete_profile()
        self.assertEqual(len(self.window.preferences.data['profiles']), 1)
        self.window.delete_profile()
        self.assertEqual(len(self.window.preferences.data['profiles']), 1)

    def test_shortcut_conflict_blocks_save(self):
        combo, enabled, key = self.window.gesture_fields['Pellizco']
        combo.setCurrentText('Atajo de teclado')
        key.setKeySequence(QKeySequence('Ctrl+Shift+P'))
        self.window.save_gestures()
        self.assertIn('pausa', self.window.gesture_error.text())
        self.assertEqual(self.window.profile['gestures']['Pellizco']['action'], 'Clic izquierdo')
        key.setKeySequence(QKeySequence('Ctrl+K'))
        self.window.save_gestures()
        self.assertEqual(self.window.profile['gestures']['Pellizco']['shortcut'], 'Ctrl+K')

    def test_calibration_never_marks_fake_measurement(self):
        for _ in range(4):
            self.window.cal_next.click()
        self.assertTrue(self.window.save_cal_button.isEnabled())
        self.window.cal_sensitivity.setValue(125)
        self.window.save_cal_button.click()
        self.assertEqual(self.window.profile['sensitivity'], 125)
        self.assertIsNone(self.window.profile['calibration'])

    def test_voice_preferences_and_duplicate_validation(self):
        self.window.voice_phrase.setText('Pausar')
        self.window.add_voice_command()
        self.window.voice_phrase.setText('pausar')
        self.window.add_voice_command()
        self.assertEqual(len(self.window.profile['voice']), 1)
        self.assertEqual(Preferences(self.settings).profile['voice'][0]['phrase'], 'Pausar')

    def test_canvas_mouse_export_undo(self):
        self.window.show()
        self.window.navigate(4)
        self.app.processEvents()
        canvas = self.window.canvas
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
        QTest.mouseMove(canvas, QPoint(80, 80))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(80, 80))
        self.assertEqual(len(canvas.strokes), 1)
        output = self.path / 'drawing.png'
        self.assertTrue(canvas.export(output))
        image = QImage(str(output))
        self.assertFalse(image.isNull())
        self.assertNotEqual(image.pixelColor(30, 30).name(), '#f5f7fa')
        canvas.undo()
        self.assertEqual(canvas.strokes, [])

    def test_themes_and_preview_preference(self):
        for theme in ['Claro', 'Sistema', 'Alto contraste', 'Oscuro']:
            self.window.theme.setCurrentText(theme)
            self.window.save_settings()
            self.assertEqual(Preferences(self.settings).data['theme'], theme)
        self.window.preview_toggle.setChecked(False)
        self.window.save_settings()
        self.assertFalse(self.window.preview.show_image)

    def test_corrupt_settings_recover(self):
        self.settings.setValue('ui_state', '{invalid json')
        restored = Preferences(self.settings)
        self.assertTrue(restored.load_error)
        self.assertEqual(len(restored.data['profiles']), 1)

    def test_transition_finishes_and_rapid_navigation_is_safe(self):
        self.window.show()
        self.app.processEvents()
        self.window.navigate(1)
        self.assertIsNotNone(self.window.stack.overlay)
        self.window.navigate(3)
        self.window.navigate(2)
        QTest.qWait(330)
        self.assertEqual(self.window.stack.currentIndex(), 2)
        self.assertIsNone(self.window.stack.overlay)
        self.assertIsNone(self.window.stack.transition)

    def test_reduced_motion_is_persisted_and_disables_transitions(self):
        self.window.show()
        self.app.processEvents()
        self.window.reduce_motion.setChecked(True)
        self.window.save_settings()
        self.window.navigate(1)
        self.assertIsNone(self.window.stack.overlay)
        self.assertTrue(Preferences(self.settings).data['reduce_motion'])
        self.window.dial.value = 150
        self.assertEqual(self.window.dial.get_display_value(), 150)

    def test_dial_animates_to_exact_preference_without_changing_profile(self):
        self.window.show()
        self.app.processEvents()
        self.window.apply_sensitivity_preset(160)
        self.assertEqual(self.window.profile['sensitivity'], 160)
        QTest.qWait(380)
        self.assertEqual(self.window.dial.get_display_value(), 160)
        self.assertEqual(Preferences(self.settings).profile['sensitivity'], 160)

    def test_sidebar_collapses_and_keeps_accessible_names(self):
        self.window.show()
        self.window.resize(1050, 740)
        self.app.processEvents()
        self.assertEqual(self.window.rail.width(), 84)
        self.assertEqual(self.window.nav_buttons['Perfiles'].accessibleName(), 'Perfiles')
        self.window.resize(1440, 940)
        self.app.processEvents()
        self.assertIn('Perfiles', self.window.nav_buttons['Perfiles'].text())


if __name__ == '__main__':
    unittest.main()
