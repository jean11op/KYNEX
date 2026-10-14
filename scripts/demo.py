"""Ejemplo sin cámara, interfaz, Windows ni escritura persistente."""
import sys
from pathlib import Path
raiz = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(raiz / "src"), str(raiz)]

from holocontrol.application.use_cases import AplicacionControl
from holocontrol.application.dto.reconocimiento import Reconocimiento
from holocontrol.domain.entities import Calibracion
from tests.soporte import RelojSimulado, RepositorioPerfilesMemoria, EjecutorRegistro


def principal():
    reloj = RelojSimulado()
    repositorio = RepositorioPerfilesMemoria()
    ejecutor = EjecutorRegistro()
    aplicacion = AplicacionControl(repositorio, ejecutor, reloj)
    perfil = aplicacion.crear_perfil("Perfil de prueba")
    aplicacion.seleccionar_perfil(perfil.id)
    aplicacion.calibrar_perfil(Calibracion(perfil.id, suavizado=0))
    estado_actual = aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=1920, alto_pantalla=1080)
    print("Perfil creado y calibrado:", perfil.nombre)
    print("Control:", {"STOPPED": "DETENIDO", "PAUSED": "PAUSADO", "ACTIVE": "ACTIVO"}[estado_actual.estado.name])
    for gesto, x, y in [("indice", 0.5, 0.5), ("pellizco", None, None),
                           ("pellizco", None, None), (None, None, None),
                           ("pellizco", None, None), ("palma", None, None)]:
        fotograma = Reconocimiento(estado_actual.generacion, reloj.avanzar(), True, gesto, 0.95, x, y)
        resultado = aplicacion.procesar_reconocimiento(fotograma)
        print(f"{(gesto or 'Sin gesto'):12} -> {resultado.motivo}")
    print("Órdenes registradas:", ejecutor.llamadas)
    print("Control:", {"STOPPED": "DETENIDO", "PAUSED": "PAUSADO", "ACTIVE": "ACTIVO"}[aplicacion.estado_actual().estado.name])
    aplicacion.finalizar_sesion()
    print("Sesión finalizada:", {"STOPPED": "DETENIDO", "PAUSED": "PAUSADO", "ACTIVE": "ACTIVO"}[aplicacion.estado_actual().estado.name])


if __name__ == "__main__":
    principal()
