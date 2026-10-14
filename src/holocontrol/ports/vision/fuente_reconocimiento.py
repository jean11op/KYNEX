from typing import Callable, Protocol
from holocontrol.application.dto.reconocimiento import Reconocimiento


class FuenteReconocimiento(Protocol):
    """Puerto para I3, coordinado por el punto de ensamblaje de I1/I5.

    iniciar inicia un trabajador y retorna sin bloquear la UI. al_reconocer recibe
    incluso fotogramas sin mano. Nunca repetir resultados viejos. al_fallar
    debe llamar a aplicacion.informar_perdida_camara(). detener debe detener el trabajador.
    La generación es la entregada por iniciar_control/reanudar_control.
    """

    def iniciar(self, generacion: int, al_reconocer: Callable[[Reconocimiento], None],
              al_fallar: Callable[[str], None]) -> None: ...
    def detener(self) -> None: ...
