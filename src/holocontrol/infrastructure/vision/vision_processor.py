from dataclasses import replace
from time import monotonic_ns, perf_counter_ns

from holocontrol.infrastructure.vision.configuration import ConfiguracionVision
from holocontrol.infrastructure.vision.geometry import coordenadas_mano, distancia
from holocontrol.infrastructure.vision.gesture_recognizer import ReconocedorGestos
from holocontrol.ports.vision.models import (
    DeteccionManos,
    EstadoVision,
    Fotograma,
    PlantillaGesto,
    ResultadoVision,
)
from holocontrol.ports.vision.vision_provider import DetectorManos


class ProcesadorVision:
    def __init__(
        self,
        configuracion: ConfiguracionVision | None = None,
        plantillas: tuple[PlantillaGesto, ...] = (),
    ) -> None:
        self.configuracion = configuracion or ConfiguracionVision()
        self._reconocedor = ReconocedorGestos(self.configuracion, plantillas)
        self._posicion: tuple[float, float] | None = None
        self._centro_mano: tuple[float, float] | None = None
        self._ultimo_instante_ms = -1
        self._ultimo_seguimiento_ms = -1000

    def procesar(self, fotograma: Fotograma, detector: DetectorManos) -> ResultadoVision:
        inicio_ns = perf_counter_ns()
        deteccion = detector.detectar(fotograma)
        resultado = self.interpretar(deteccion)
        return replace(
            resultado,
            latencia_procesamiento_ms=(perf_counter_ns() - inicio_ns) / 1_000_000,
            latencia_total_ms=max(0.0, monotonic_ns() / 1_000_000 - fotograma.instante_ms),
        )

    def interpretar(self, deteccion: DeteccionManos) -> ResultadoVision:
        instante_ms = deteccion.instante_ms
        if (
            type(instante_ms) is not int
            or instante_ms < 0
            or instante_ms <= self._ultimo_instante_ms
        ):
            raise ValueError(
                "Los instantes deben ser enteros no negativos y aumentar estrictamente."
            )
        intervalo_ms = instante_ms - self._ultimo_instante_ms
        habia_datos = self._centro_mano is not None
        self._ultimo_instante_ms = instante_ms
        if deteccion.ancho <= 0 or deteccion.alto <= 0:
            raise ValueError("Las dimensiones de imagen deben ser positivas.")
        if deteccion.estado is not EstadoVision.MANO_DETECTADA:
            estado = deteccion.estado
            if estado is EstadoVision.SIN_MANO and habia_datos:
                estado = EstadoVision.MANO_PERDIDA
            return self.invalidar(instante_ms, estado, deteccion.mensaje)
        # Only the profile-selected hand can control the application.
        candidatas = tuple(m for m in deteccion.manos
                           if m.lateralidad is self.configuracion.mano_dominante)
        # Closing the hand can briefly confuse handedness. Preserve only the
        # pending fist timer, never publish coordinates/actions for the other hand.
        if (len(deteccion.manos) == 1 and self._reconocedor.esperando_puno
                and self._centro_mano is not None
                and instante_ms - self._ultimo_seguimiento_ms <= 150):
            observada = deteccion.manos[0]
            centro_observado = (observada.puntos[9].x, observada.puntos[9].y)
            if ((not candidatas or observada.confianza_lateralidad < self.configuracion.umbral_lateralidad)
                    and distancia(centro_observado, self._centro_mano) <= .04):
                return ResultadoVision(
                    instante_ms, EstadoVision.BAJA_CONFIANZA,
                    mensaje="Confirmando la mano seleccionada; mantén el puño.")
        if not candidatas:
            return self.invalidar(
                instante_ms, EstadoVision.MANO_PERDIDA if habia_datos else EstadoVision.SIN_MANO,
                "Presenta la mano seleccionada en el perfil.")
        if len(candidatas) != 1:
            return self.invalidar(
                instante_ms,
                EstadoVision.BAJA_CONFIANZA,
                "Se detectaron varias manos con la misma lateralidad; muestra una sola.",
            )
        mano = candidatas[0]
        if mano.confianza_lateralidad < self.configuracion.umbral_lateralidad:
            return self.invalidar(
                instante_ms,
                EstadoVision.BAJA_CONFIANZA,
                "No se identifica bien la lateralidad.",
            )
        relacion_aspecto = deteccion.ancho / deteccion.alto
        puntos = coordenadas_mano(mano, relacion_aspecto)
        if distancia(puntos[0], puntos[9]) < 0.02 or distancia(puntos[5], puntos[17]) < 0.02:
            return self.invalidar(
                instante_ms,
                EstadoVision.BAJA_CONFIANZA,
                "La palma es demasiado pequeña o inválida.",
            )
        centro = (mano.puntos[9].x, mano.puntos[9].y)
        if habia_datos and intervalo_ms > self.configuracion.vigencia_ms:
            return self.invalidar(
                instante_ms,
                EstadoVision.MANO_PERDIDA,
                "Se interrumpió el seguimiento; vuelve a presentar un gesto neutro.",
            )
        # A fast, valid hand is not a lost hand. Reset position smoothing on a
        # large displacement without cancelling the recognized gesture.
        if habia_datos and distancia(centro, self._centro_mano) > self.configuracion.salto_maximo_mano:
            self._posicion = None
        posicion_cruda = (mano.puntos[8].x, mano.puntos[8].y)
        desplazamiento = (0.0, 0.0)
        if self._posicion is None:
            posicion = posicion_cruda
        else:
            factor = 1 - (1 - self.configuracion.factor_suavizado) ** (intervalo_ms / (1000 / 30))
            posicion = tuple(a + factor * (b - a) for a, b in zip(self._posicion, posicion_cruda))
            desplazamiento = tuple(b - a for a, b in zip(self._posicion, posicion))
        eventos = self._reconocedor.procesar(
            mano, instante_ms, relacion_aspecto, deteccion.en_espejo
        )
        self._posicion = posicion
        self._centro_mano = centro
        self._ultimo_seguimiento_ms = instante_ms
        return ResultadoVision(
            instante_ms,
            EstadoVision.MANO_DETECTADA,
            mano,
            posicion,
            desplazamiento,
            eventos,
        )

    def invalidar(
        self, instante_ms: int, estado: EstadoVision, mensaje: str = ""
    ) -> ResultadoVision:
        eventos = self._reconocedor.reiniciar(instante_ms)
        self._posicion = None
        self._centro_mano = None
        self._ultimo_seguimiento_ms = -1000
        return ResultadoVision(instante_ms, estado, eventos=eventos, mensaje=mensaje)
