import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from holocontrol.application.dto.reconocimiento import Reconocimiento
from holocontrol.application.services.adaptador_ejecutor_existente import AdaptadorEjecutorExistente
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Calibracion
from holocontrol.ports.vision.models import EventoGesto, FaseGesto
from tests.soporte import RelojSimulado, RepositorioPerfilesMemoria


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
        self.aplicacion.configurar_gesto(p.id, 'dos_dedos', 'desplazar_vertical', reemplazar_existente=True)
        self.aplicacion.seleccionar_perfil(p.id)
        self.aplicacion.calibrar_perfil(Calibracion(p.id, suavizado=0))
        self.aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=1920, alto_pantalla=1080)

    def enviar(self, gesto, **kwargs):
        return self.aplicacion.procesar_reconocimiento(Reconocimiento(
            self.aplicacion.estado_actual().generacion, self.reloj.avanzar(), True, gesto, 0.99, **kwargs))

    def test_adaptador_recibe_un_clic_por_gesto_mantenido(self):
        self.enviar("pulgar")
        self.enviar("pulgar")
        self.api.click.assert_called_once_with(button="left", _pause=False)

    def test_adaptador_recibe_coordenadas_calibradas(self):
        self.enviar("indice", x=1, y=0)
        self.api.moveTo.assert_called_once_with(1918, 1, duration=0, _pause=False)

    def test_adaptador_pausa_con_aplicacion(self):
        self.enviar("palma_abierta")
        self.assertEqual(self.aplicacion.estado_actual().estado.name, "PAUSED")
        self.enviar("pulgar")
        self.api.click.assert_not_called()

    def test_evento_scroll_llega_a_windows_por_el_adaptador(self):
        instante = self.reloj.avanzar()
        self.aplicacion.procesar_reconocimiento(Reconocimiento(
            self.aplicacion.estado_actual().generacion, instante, True,
            eventos=(EventoGesto("dos_dedos", FaseGesto.MANTENIMIENTO,
                                 round(instante * 1000), 100, 0.99),),
            desplazamiento_vertical=0.1,
        ))
        self.api.scroll.assert_called_once_with(-360, _pause=False)
        self.api.click.assert_not_called()
