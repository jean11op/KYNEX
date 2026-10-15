import subprocess
import sys


def test_contrato_y_proveedor_no_importan_ui_vision_nativa_ni_acciones_del_sistema():
    codigo = """
import builtins
import sys

importacion_original = builtins.__import__
prohibidos = ('cv2', 'numpy', 'mediapipe', 'PySide6', 'pyautogui', 'pynput',
              'holocontrol.infrastructure.windows', 'holocontrol.application')

def importar(nombre, *argumentos, **opciones):
    if any(nombre == p or nombre.startswith(p + '.') for p in prohibidos):
        raise AssertionError('Dependencia fuera de visión: ' + nombre)
    return importacion_original(nombre, *argumentos, **opciones)

builtins.__import__ = importar
from holocontrol.ports.vision import ProveedorVision, ResultadoVision
from holocontrol.infrastructure.vision import AdaptadorVision

proveedor = AdaptadorVision()
assert isinstance(proveedor, ProveedorVision)
assert proveedor.detener()
assert isinstance(proveedor.obtener_resultado(), ResultadoVision)
assert not any(nombre == p or nombre.startswith(p + '.')
               for nombre in sys.modules for p in prohibidos)
"""
    proceso = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, timeout=10, check=False
    )
    assert proceso.returncode == 0, proceso.stderr
