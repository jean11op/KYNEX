import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from holocontrol.application.use_cases import AplicacionControl
from holocontrol.application.services.existing_executor_adapter import AdaptadorEjecutorExistente
from holocontrol.application.dto.recognition import Reconocimiento
from holocontrol.domain.entities import Calibracion
from holocontrol.domain.value_objects.control_state import ControlState as EstadoControl
from tests.support import RelojSimulado, RepositorioPerfilesMemoria


class PruebasContratoWindowsExistente(unittest.TestCase):
    """Carga el adaptador original; sustituye solo PyAutoGUI, no su lógica."""

    def setUp(self):
        api = ModuleType("pyautogui")
        api.size = Mock(return_value=(1920, 1080))
        api.moveTo = Mock()
        api.click = Mock()
        api.scroll = Mock()
        self.api = api
        ruta = Path(__file__).resolve().parents[2] / 'src/holocontrol/infrastructure/windows/windows_action_executor.py'
        especificacion = importlib.util.spec_from_file_location("member2_windows_contract", ruta)
        modulo = importlib.util.module_from_spec(especificacion)
        with patch.dict(sys.modules, {"pyautogui": api}):
            especificacion.loader.exec_module(modulo)
        self.reloj = RelojSimulado()
        self.ejecutor = modulo.WindowsActionExecutor(click_cooldown=0)
        self.aplicacion = AplicacionControl(RepositorioPerfilesMemoria(), AdaptadorEjecutorExistente(self.ejecutor), self.reloj)
        p = self.aplicacion.crear_perfil("Contrato")
        self.aplicacion.seleccionar_perfil(p.id)
        self.aplicacion.calibrar_perfil(Calibracion(p.id, suavizado=0))
        self.aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=1920, alto_pantalla=1080)

    def enviar(self, gesto, **kwargs):
        return self.aplicacion.procesar_reconocimiento(Reconocimiento(
            self.aplicacion.estado_actual().generacion, self.reloj.avanzar(), True, gesto, 0.99, **kwargs))

    def test_adaptador_recibe_un_clic_por_gesto_mantenido(self):
        self.enviar("pellizco")
        self.enviar("pellizco")
        self.api.click.assert_called_once_with(button="left")

    def test_adaptador_recibe_coordenadas_calibradas(self):
        self.enviar("indice", x=1, y=0)
        self.api.moveTo.assert_called_once_with(1919, 0, duration=0)

    def test_adaptador_pausa_con_aplicacion(self):
        self.enviar("palma")
        self.assertEqual(self.ejecutor._state, EstadoControl.PAUSED)
        self.enviar("pellizco")
        self.api.click.assert_not_called()
