"""Flujo de cámara simulada a Windows Actions con los efectos de PyAutoGUI aislados."""

import time
from threading import Event

import numpy as np

from holocontrol.application.services.adaptador_ejecutor_existente import (
    AdaptadorEjecutorExistente,
)
from holocontrol.application.services.coordinador_control_vision import (
    CoordinadorControlVision,
)
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Calibracion
from holocontrol.infrastructure.vision.vision_worker import AdaptadorVision
from holocontrol.infrastructure.windows.windows_action_executor import WindowsActionExecutor
from holocontrol.ports.vision.models import (
    DeteccionManos,
    EstadoVision,
    Fotograma,
    Lateralidad,
    ManoDetectada,
    PuntoMano,
)
from tests.soporte import RepositorioPerfilesMemoria


def _mano(postura: str, delta_y: float = 0.0) -> ManoDetectada:
    coordenadas = [(0.5, 0.85, 0.0)] * 21
    coordenadas[1:5] = [
        (0.40, 0.74, 0.0),
        (0.32, 0.66, 0.0),
        (0.26, 0.58, 0.0),
        (0.22, 0.50, 0.0),
    ]
    extendidos = (True, True, False, False) if postura == "dos_dedos" else (True, False, False, False)
    for base, x, extendido in zip((5, 9, 13, 17), (0.42, 0.50, 0.58, 0.66), extendidos):
        coordenadas[base : base + 4] = (
            [(x, y, 0.0) for y in (0.60, 0.45, 0.30, 0.15)]
            if extendido
            else [(x, y, 0.0) for y in (0.60, 0.47, 0.57, 0.64)]
        )
    if postura == "pellizco":
        coordenadas[2:5] = [(0.32, 0.66, 0.0), (0.32, 0.46, 0.0), (0.32, 0.26, 0.0)]
        coordenadas[5:9] = [(0.42, 0.60, 0.0), (0.56, 0.52, 0.0), (0.70, 0.44, 0.0), (0.84, 0.36, 0.0)]
    coordenadas = [(x, y + delta_y, z) for x, y, z in coordenadas]
    return ManoDetectada(
        tuple(PuntoMano(i, x, y, z) for i, (x, y, z) in enumerate(coordenadas)),
        Lateralidad.DERECHA,
        0.99,
    )


class _CamaraSimulada:
    def __init__(self):
        self.cerrando = Event()
        self.instante = 0

    def abrir(self):
        pass

    def leer(self):
        time.sleep(0.035)
        self.instante = time.monotonic_ns() // 1_000_000
        return Fotograma(np.zeros((480, 640, 3), dtype=np.uint8), self.instante)

    def cerrar(self):
        self.cerrando.set()


class _DetectorSimulado:
    def __init__(self):
        self.indice = 0

    def detectar(self, fotograma):
        self.indice += 1
        if self.indice <= 5:
            postura, delta_y = "indice", 0.0
        elif self.indice <= 11:
            postura, delta_y = "pellizco", 0.0
        else:
            postura = "dos_dedos"
            delta_y = max(0, min((self.indice - 16) * 0.035, 0.14))
        return DeteccionManos(
            fotograma.instante_ms,
            (_mano(postura, delta_y),),
            EstadoVision.MANO_DETECTADA,
            640,
            480,
            en_espejo=fotograma.en_espejo,
        )

    def cerrar(self):
        pass


def test_flujo_vision_dominio_windows_con_dispositivos_simulados(monkeypatch):
    import holocontrol.infrastructure.windows.windows_action_executor as windows_module
    import holocontrol.infrastructure.windows.window_context as window_context

    clic = []
    botones = []
    monkeypatch.setattr(windows_module.pyautogui, "mouseDown", lambda **kw: botones.append("down"))
    monkeypatch.setattr(windows_module.pyautogui, "mouseUp", lambda **kw: botones.append("up"))
    monkeypatch.setattr(windows_module.pyautogui, "position", lambda: (320,240))
    movimientos = []
    desplazamientos = []
    monkeypatch.setattr(windows_module.pyautogui, "click", lambda **kw: clic.append(kw))
    monkeypatch.setattr(
        windows_module.pyautogui,
        "moveTo",
        lambda x, y, **kw: movimientos.append((x, y, kw)),
    )
    monkeypatch.setattr(window_context, 'canva_canvas_point', lambda: None)
    monkeypatch.setattr(windows_module.pyautogui, 'scroll', lambda amount, **kw: desplazamientos.append(amount))
    monkeypatch.setattr(windows_module.pyautogui, "size", lambda: (640, 480))
    ejecucion = WindowsActionExecutor(click_cooldown=0)
    aplicacion = AplicacionControl(
        RepositorioPerfilesMemoria(), AdaptadorEjecutorExistente(ejecucion)
    )
    perfil = aplicacion.crear_perfil("Integración visión")
    aplicacion.configurar_gesto(perfil.id, "dos_dedos", "desplazar_vertical", reemplazar_existente=True)
    aplicacion.seleccionar_perfil(perfil.id)
    aplicacion.calibrar_perfil(Calibracion(perfil.id, suavizado=0.5))

    proveedor = AdaptadorVision(
        crear_camara=_CamaraSimulada,
        crear_detector=_DetectorSimulado,
    )
    coordinador = CoordinadorControlVision(aplicacion, proveedor)
    coordinador.iniciar_control(ancho_pantalla=640, alto_pantalla=480)
    try:
        limite = time.monotonic() + 3
        while (len(botones) < 2 or not desplazamientos) and time.monotonic() < limite:
            coordinador.consultar_vision()
            time.sleep(0.005)
        assert clic == []
        assert botones == ["down", "up"]
        assert movimientos
        assert desplazamientos and all(cantidad > 0 for cantidad in desplazamientos)
    finally:
        coordinador.detener_control()
