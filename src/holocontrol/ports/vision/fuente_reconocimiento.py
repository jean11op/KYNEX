from typing import Callable, Protocol
from holocontrol.application.dto.reconocimiento import Reconocimiento


class FuenteReconocimiento(Protocol):
    """Contrato anterior por callbacks, conservado por compatibilidad.

    Para feature/vision-gestures se usa ProveedorVision y
    AplicacionControl.consultar_vision(proveedor, generacion=generacion_del_trabajador).

    iniciar inicia un trabajador y retorna sin bloquear la UI. al_reconocer recibe
    incluso fotogramas sin mano. Nunca repetir resultados viejos. al_fallar
    debe llamar a aplicacion.informar_perdida_camara(). detener debe detener el trabajador.
    La generación es la entregada por iniciar_control/reanudar_control.
    """

    def iniciar(self, generacion: int, al_reconocer: Callable[[Reconocimiento], None],
              al_fallar: Callable[[str], None]) -> None: ...
    def detener(self) -> None: ...
