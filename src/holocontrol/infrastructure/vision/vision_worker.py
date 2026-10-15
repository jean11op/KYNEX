import logging
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from math import isfinite
from threading import Condition, Event, Lock, Thread
from time import monotonic, monotonic_ns
from typing import Self

from holocontrol.infrastructure.vision.camera import CamaraOpenCV
from holocontrol.infrastructure.vision.configuration import ConfiguracionCamara, ConfiguracionVision
from holocontrol.infrastructure.vision.errors import ErrorCamara
from holocontrol.infrastructure.vision.hand_detector import DetectorMediaPipe
from holocontrol.infrastructure.vision.vision_processor import ProcesadorVision
from holocontrol.ports.vision.models import (
    EstadoVision,
    EventoGesto,
    Fotograma,
    PlantillaGesto,
    ResultadoVision,
)
from holocontrol.ports.vision.vision_provider import DetectorManos, FuenteCamara

registro = logging.getLogger(__name__)


class AdaptadorVision:
    """Posee cámara y detector en un solo hilo; la interfaz consulta resultados sin bloquear."""

    def __init__(
        self,
        configuracion: ConfiguracionVision | None = None,
        camara: ConfiguracionCamara | None = None,
        plantillas: tuple[PlantillaGesto, ...] = (),
        crear_camara: Callable[[], FuenteCamara] | None = None,
        crear_detector: Callable[[], DetectorManos] | None = None,
    ) -> None:
        self.configuracion = configuracion or ConfiguracionVision()
        self.camara = camara or ConfiguracionCamara()
        self.plantillas = tuple(plantillas)
        self._crear_camara = crear_camara or (lambda: CamaraOpenCV(self.camara))
        self._crear_detector = crear_detector or (lambda: DetectorMediaPipe(self.configuracion))
        self._condicion = Condition()
        self._ciclo = Lock()
        self._parada = Event()
        self._hilo: Thread | None = None
        self._ultimo: ResultadoVision | None = None
        self._pendientes: deque[EventoGesto] = deque()
        self._desplazamiento_pendiente: tuple[float, float] | None = None
        self._camara_disponible = False
        self._version = 0
        self._version_consumida = 0
        self._caducidad_informada = False
        self._vista_previa_activa = False
        self._fotograma_previo: Fotograma | None = None

    @property
    def en_ejecucion(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    @property
    def estado(self) -> EstadoVision:
        with self._condicion:
            if self._ultimo is None:
                return EstadoVision.DETENIDO
            if (
                self._ultimo.es_valido
                and monotonic_ns() // 1_000_000 - self._ultimo.instante_ms
                > self.configuracion.vigencia_ms
            ):
                return EstadoVision.MANO_PERDIDA
            return self._ultimo.estado

    @property
    def camara_disponible(self) -> bool:
        with self._condicion:
            return self._camara_disponible and not self._parada.is_set()

    def iniciar(self) -> None:
        with self._ciclo:
            if self.en_ejecucion:
                if self._parada.is_set():
                    raise RuntimeError("El hilo anterior todavía está cerrando la cámara.")
                return
            with self._condicion:
                self._caducidad_informada = False
                self._camara_disponible = False
                # Un trabajador nuevo pertenece a otra sesión: no hereda gestos
                # pendientes ni desplazamiento acumulado del ciclo anterior.
                self._pendientes.clear()
                self._desplazamiento_pendiente = None
                self._fotograma_previo = None
                self._parada.clear()
                self._publicar(ResultadoVision(monotonic_ns() // 1_000_000, EstadoVision.INICIANDO))
            self._hilo = Thread(target=self._ejecutar, name="kinex-vision", daemon=True)
            self._hilo.start()

    def activar_vista_previa(self, activa: bool) -> None:
        if type(activa) is not bool:
            raise ValueError("La vista previa necesita un booleano.")
        with self._condicion:
            self._vista_previa_activa = activa
            if not activa:
                self._fotograma_previo = None

    def obtener_fotograma(self) -> Fotograma | None:
        with self._condicion:
            fotograma = self._fotograma_previo
            if (
                fotograma is None
                or self._parada.is_set()
                or monotonic_ns() // 1_000_000 - fotograma.instante_ms
                > self.configuracion.vigencia_ms
            ):
                return None
            return Fotograma(fotograma.imagen.copy(), fotograma.instante_ms, fotograma.en_espejo)

    def _publicar(self, resultado: ResultadoVision) -> None:
        with self._condicion:
            if self._parada.is_set() and resultado.estado not in (
                EstadoVision.DETENIENDO,
                EstadoVision.DETENIDO,
                EstadoVision.ERROR_CAMARA,
                EstadoVision.ERROR_PROCESAMIENTO,
            ):
                # Conserva eventos calculados durante el cierre, sin reactivar coordenadas.
                resultado = ResultadoVision(
                    max(monotonic_ns() // 1_000_000, resultado.instante_ms),
                    EstadoVision.DETENIENDO,
                    eventos=resultado.eventos,
                )
            self._pendientes.extend(resultado.eventos)
            if resultado.es_valido and resultado.desplazamiento_indice is not None:
                anterior = self._desplazamiento_pendiente or (0.0, 0.0)
                self._desplazamiento_pendiente = tuple(
                    a + b for a, b in zip(anterior, resultado.desplazamiento_indice)
                )
            elif not resultado.es_valido:
                self._desplazamiento_pendiente = None
            self._ultimo = resultado
            self._version += 1
            self._caducidad_informada = False
            self._condicion.notify_all()

    def obtener_resultado(self, espera_s: float = 0.0) -> ResultadoVision | None:
        if not isfinite(espera_s) or espera_s < 0:
            raise ValueError("La espera debe ser finita y no negativa.")
        with self._condicion:
            limite = monotonic() + espera_s
            while self._version == self._version_consumida:
                if (
                    self._ultimo is not None
                    and self._ultimo.es_valido
                    and not self._caducidad_informada
                ):
                    edad_ms = monotonic_ns() // 1_000_000 - self._ultimo.instante_ms
                    if edad_ms > self.configuracion.vigencia_ms:
                        break
                restante = limite - monotonic()
                if restante <= 0:
                    return None
                self._condicion.wait(min(restante, self.configuracion.vigencia_ms / 1000))
            resultado = self._ultimo
            self._version_consumida = self._version
            ahora_ms = monotonic_ns() // 1_000_000
            eventos = tuple(self._pendientes)
            self._pendientes.clear()
            desplazamiento = self._desplazamiento_pendiente
            self._desplazamiento_pendiente = None
            if (
                resultado.es_valido
                and ahora_ms - resultado.instante_ms > self.configuracion.vigencia_ms
            ):
                self._caducidad_informada = True
                return ResultadoVision(
                    ahora_ms,
                    EstadoVision.MANO_PERDIDA,
                    eventos=eventos,
                    mensaje="No llegaron datos de cámara recientes. Suspende las acciones gestuales.",
                )
            return replace(
                resultado,
                eventos=eventos,
                desplazamiento_indice=desplazamiento if resultado.es_valido else None,
            )

    def detener(self, espera_s: float = 2.0) -> bool:
        if not isfinite(espera_s) or espera_s < 0:
            raise ValueError("La espera debe ser finita y no negativa.")
        with self._ciclo:
            hilo = self._hilo
            with self._condicion:
                self._parada.set()
                self._camara_disponible = False
                if hilo is not None and hilo.is_alive():
                    if self.estado not in (
                        EstadoVision.DETENIDO,
                        EstadoVision.ERROR_CAMARA,
                        EstadoVision.ERROR_PROCESAMIENTO,
                    ):
                        self._publicar(
                            ResultadoVision(monotonic_ns() // 1_000_000, EstadoVision.DETENIENDO)
                        )
                elif self._ultimo is None or self.estado not in (
                    EstadoVision.DETENIDO,
                    EstadoVision.ERROR_CAMARA,
                    EstadoVision.ERROR_PROCESAMIENTO,
                ):
                    self._publicar(
                        ResultadoVision(monotonic_ns() // 1_000_000, EstadoVision.DETENIDO)
                    )
            if hilo is not None:
                hilo.join(espera_s)
            finalizado = hilo is None or not hilo.is_alive()
            if not finalizado:
                self._publicar(
                    ResultadoVision(
                        monotonic_ns() // 1_000_000,
                        EstadoVision.ERROR_CAMARA,
                        mensaje="El controlador de cámara no terminó a tiempo; el control debe seguir detenido.",
                    )
                )
            return finalizado

    def _ejecutar(self) -> None:
        camara = detector = None
        procesador = None
        estado_final = EstadoVision.DETENIDO
        mensaje = ""
        try:
            procesador = ProcesadorVision(self.configuracion, self.plantillas)
            camara = self._crear_camara()
            detector = self._crear_detector()
            camara.abrir()
            with self._condicion:
                self._camara_disponible = not self._parada.is_set()
                if self._camara_disponible:
                    self._publicar(
                        ResultadoVision(monotonic_ns() // 1_000_000, EstadoVision.CAMARA_DISPONIBLE)
                    )
            while not self._parada.is_set():
                fotograma = camara.leer()
                if self._parada.is_set():
                    break
                with self._condicion:
                    if self._vista_previa_activa:
                        self._fotograma_previo = Fotograma(
                            fotograma.imagen.copy(),
                            fotograma.instante_ms,
                            fotograma.en_espejo,
                        )
                resultado = procesador.procesar(fotograma, detector)
                self._publicar(resultado)
        except ErrorCamara as error:
            estado_final, mensaje = EstadoVision.ERROR_CAMARA, str(error)
            registro.warning("Error de cámara: %s", error)
        except Exception as error:  # noqa: BLE001 - El límite del hilo invalida cualquier fallo.
            estado_final = EstadoVision.ERROR_PROCESAMIENTO
            mensaje = f"Falló el módulo de visión: {error}"
            registro.exception("Error en el procesamiento de visión")
        finally:
            with self._condicion:
                self._camara_disponible = False
                self._fotograma_previo = None
                if estado_final is not EstadoVision.DETENIDO:
                    self._parada.set()
                    instante_ms = monotonic_ns() // 1_000_000
                    resultado_error = (
                        procesador.invalidar(instante_ms, estado_final, mensaje)
                        if procesador is not None
                        else ResultadoVision(instante_ms, estado_final, mensaje=mensaje)
                    )
                    # Comunica el fallo antes de cerrar recursos nativos que pueden bloquear.
                    self._publicar(resultado_error)
            for recurso in (detector, camara):
                if recurso is not None:
                    try:
                        recurso.cerrar()
                    except Exception:  # noqa: BLE001 - Se intenta cerrar también el otro recurso.
                        estado_final = EstadoVision.ERROR_PROCESAMIENTO
                        mensaje = "No se pudo liberar uno de los recursos de visión."
                        registro.exception("Error al cerrar un recurso de visión")
            instante_ms = monotonic_ns() // 1_000_000
            resultado_final = (
                procesador.invalidar(instante_ms, estado_final, mensaje)
                if procesador is not None
                else ResultadoVision(instante_ms, estado_final, mensaje=mensaje)
            )
            self._publicar(resultado_final)

    def __enter__(self) -> Self:
        self.iniciar()
        return self

    def __exit__(self, *_argumentos) -> None:
        if not self.detener():
            raise ErrorCamara("La cámara no respondió al cierre dentro del plazo.")
