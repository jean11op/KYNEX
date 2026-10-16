"""Coordina una sesión de visión con la generación autorizada por la aplicación."""

from collections.abc import Callable
from math import isfinite
from threading import RLock
from time import monotonic, sleep

from holocontrol.application.dto.resultados import EstadoActualControl, ResultadoGesto
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.errores import ErrorControl
from holocontrol.ports.vision.models import EstadoVision
from holocontrol.ports.vision.vision_provider import ProveedorVision


class CoordinadorControlVision:
    """Posee el ciclo de vida del proveedor y fija la generación por trabajador.

    Debe componerse junto a AplicacionControl cuando se conecte el bootstrap. Los
    consumidores consultan este coordinador, nunca etiquetan resultados directamente.
    """

    _ESTADOS_TERMINALES = frozenset({
        EstadoVision.ERROR_CAMARA,
        EstadoVision.ERROR_PROCESAMIENTO,
        EstadoVision.DETENIDO,
    })

    def __init__(
        self,
        aplicacion: AplicacionControl,
        proveedor: ProveedorVision,
        *,
        espera_inicio_s: float = 2.0,
        reloj: Callable[[], float] = monotonic,
        dormir: Callable[[float], None] = sleep,
    ) -> None:
        if not isfinite(espera_inicio_s) or espera_inicio_s <= 0:
            raise ValueError("La espera de inicio debe ser finita y positiva.")
        self._aplicacion = aplicacion
        self._proveedor = proveedor
        self._espera_inicio_s = espera_inicio_s
        self._reloj = reloj
        self._dormir = dormir
        self._bloqueo = RLock()
        self._generacion_trabajador: int | None = None

    def iniciar_control(self, *, ancho_pantalla: int, alto_pantalla: int) -> EstadoActualControl:
        with self._bloqueo:
            self._generacion_trabajador = None
            try:
                self._iniciar_proveedor()
                estado = self._aplicacion.iniciar_control(
                    camara_disponible=True,
                    ancho_pantalla=ancho_pantalla,
                    alto_pantalla=alto_pantalla,
                )
            except Exception:
                self._detener_proveedor()
                raise
            self._generacion_trabajador = estado.generacion
            return estado

    def reanudar_control(self) -> EstadoActualControl:
        with self._bloqueo:
            self._generacion_trabajador = None
            try:
                self._iniciar_proveedor()
                estado = self._aplicacion.reanudar_control(camara_disponible=True)
            except Exception:
                self._detener_proveedor()
                raise
            self._generacion_trabajador = estado.generacion
            return estado

    def pausar_control(self) -> EstadoActualControl:
        with self._bloqueo:
            self._generacion_trabajador = None
            try:
                estado = self._aplicacion.pausar_control()
            finally:
                self._detener_proveedor()
            return estado

    def detener_control(self) -> EstadoActualControl:
        with self._bloqueo:
            self._generacion_trabajador = None
            try:
                estado = self._aplicacion.detener_control()
            finally:
                self._detener_proveedor()
            return estado

    def consultar_vision(self) -> ResultadoGesto:
        with self._bloqueo:
            generacion = self._generacion_trabajador
        if generacion is None:
            return ResultadoGesto(False, "trabajador_no_iniciado")
        resultado = self._aplicacion.consultar_vision(self._proveedor, generacion=generacion)
        with self._bloqueo:
            if (
                self._generacion_trabajador == generacion
                and self._aplicacion.estado_actual().generacion != generacion
            ):
                self._generacion_trabajador = None
                self._detener_proveedor()
        return resultado

    def _iniciar_proveedor(self) -> None:
        # El vaciado explícito protege también proveedores que no limpien su cola
        # internamente al reiniciar.
        self._detener_proveedor()
        self._proveedor.iniciar()
        limite = self._reloj() + self._espera_inicio_s
        while not self._proveedor.camara_disponible:
            estado = self._proveedor.estado
            if estado in self._ESTADOS_TERMINALES:
                raise ErrorControl(f"La cámara no pudo iniciarse: {estado.value}.")
            if self._reloj() >= limite:
                raise ErrorControl("La cámara no estuvo disponible dentro del plazo.")
            self._dormir(min(0.01, max(0.0, limite - self._reloj())))

    def _detener_proveedor(self) -> None:
        if not self._proveedor.detener():
            raise ErrorControl("El trabajador de visión no terminó; no se puede iniciar otra sesión.")
        while self._proveedor.obtener_resultado() is not None:
            pass
