from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any


class Lateralidad(StrEnum):
    DERECHA = "derecha"
    IZQUIERDA = "izquierda"


class EstadoVision(StrEnum):
    INICIANDO = "iniciando"
    CAMARA_DISPONIBLE = "camara_disponible"
    MANO_DETECTADA = "mano_detectada"
    SIN_MANO = "sin_mano"
    MANO_PERDIDA = "mano_perdida"
    MANO_NO_SELECCIONADA = "mano_no_seleccionada"
    BAJA_CONFIANZA = "baja_confianza"
    ERROR_CAMARA = "error_camara"
    ERROR_PROCESAMIENTO = "error_procesamiento"
    DETENIENDO = "deteniendo"
    DETENIDO = "detenido"


class GestoBasico(StrEnum):
    INDICE = "indice"
    PELLIZCO = "pellizco"
    DOS_DEDOS = "dos_dedos"
    PALMA_ABIERTA = "palma_abierta"
    PUNO = "puno"
    DESLIZAMIENTO_IZQUIERDA = "deslizamiento_izquierda"
    DESLIZAMIENTO_DERECHA = "deslizamiento_derecha"


class FaseGesto(StrEnum):
    INICIO = "inicio"
    MANTENIMIENTO = "mantenimiento"
    FIN = "fin"


@dataclass(frozen=True, slots=True)
class PuntoMano:
    indice: int
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        if type(self.indice) is not int or not 0 <= self.indice <= 20:
            raise ValueError("El índice del punto debe estar entre 0 y 20.")
        if not all(isfinite(valor) for valor in (self.x, self.y, self.z)):
            raise ValueError("Los puntos deben contener coordenadas finitas.")
        if not (0 <= self.x <= 1 and 0 <= self.y <= 1):
            raise ValueError("Las coordenadas x e y deben estar entre 0 y 1.")


@dataclass(frozen=True, slots=True)
class ManoDetectada:
    puntos: tuple[PuntoMano, ...]
    lateralidad: Lateralidad
    confianza_lateralidad: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "puntos", tuple(self.puntos))
        if len(self.puntos) != 21 or tuple(p.indice for p in self.puntos) != tuple(range(21)):
            raise ValueError("La mano necesita los 21 puntos ordenados por índice.")
        if not isinstance(self.lateralidad, Lateralidad):
            raise TypeError("La lateralidad debe ser derecha o izquierda.")
        if not isfinite(self.confianza_lateralidad) or not 0 <= self.confianza_lateralidad <= 1:
            raise ValueError("La confianza de lateralidad debe estar entre 0 y 1.")


@dataclass(frozen=True, slots=True)
class Fotograma:
    # El adaptador de cámara entrega uint8 BGR; el contrato no importa NumPy.
    imagen: Any
    instante_ms: int
    en_espejo: bool = False

    def __post_init__(self) -> None:
        validar_instante(self.instante_ms)
        if type(self.en_espejo) is not bool:
            raise ValueError("en_espejo debe indicar si la imagen se reflejó horizontalmente.")


@dataclass(frozen=True, slots=True)
class DeteccionManos:
    instante_ms: int
    manos: tuple[ManoDetectada, ...]
    estado: EstadoVision
    ancho: int
    alto: int
    mensaje: str = ""
    en_espejo: bool = False

    def __post_init__(self) -> None:
        validar_instante(self.instante_ms)
        object.__setattr__(self, "manos", tuple(self.manos))
        if not isinstance(self.estado, EstadoVision):
            raise TypeError("El estado de visión debe ser un EstadoVision.")
        if any(type(valor) is not int or valor <= 0 for valor in (self.ancho, self.alto)):
            raise ValueError("La imagen necesita dimensiones enteras positivas.")
        if type(self.en_espejo) is not bool:
            raise ValueError("en_espejo debe ser un booleano.")


@dataclass(frozen=True, slots=True)
class EventoGesto:
    nombre: str
    fase: FaseGesto
    instante_ms: int
    duracion_ms: int
    confianza: float

    def __post_init__(self) -> None:
        validar_instante(self.instante_ms)
        if not self.nombre.strip() or not isinstance(self.fase, FaseGesto):
            raise ValueError("El evento necesita nombre y fase válidos.")
        if type(self.duracion_ms) is not int or self.duracion_ms < 0:
            raise ValueError("La duración debe ser un entero no negativo.")
        if not isfinite(self.confianza) or not 0 <= self.confianza <= 1:
            raise ValueError("La confianza del gesto debe estar entre 0 y 1.")


@dataclass(frozen=True, slots=True)
class ResultadoVision:
    """Estado reciente y eventos pendientes; el historial no autoriza acciones."""

    instante_ms: int
    estado: EstadoVision
    mano: ManoDetectada | None = None
    posicion_indice: tuple[float, float] | None = None
    desplazamiento_indice: tuple[float, float] | None = None
    eventos: tuple[EventoGesto, ...] = ()
    latencia_procesamiento_ms: float = 0.0
    latencia_total_ms: float = 0.0
    mensaje: str = ""

    def __post_init__(self) -> None:
        validar_instante(self.instante_ms)
        object.__setattr__(self, "eventos", tuple(self.eventos))
        if not isinstance(self.estado, EstadoVision):
            raise TypeError("El estado de visión debe ser un EstadoVision.")
        if any(
            not isfinite(valor) or valor < 0
            for valor in (
                self.latencia_procesamiento_ms,
                self.latencia_total_ms,
            )
        ):
            raise ValueError("Las latencias deben ser finitas y no negativas.")
        if self.estado is not EstadoVision.MANO_DETECTADA and (
            self.mano is not None
            or self.posicion_indice is not None
            or self.desplazamiento_indice is not None
        ):
            raise ValueError("Un resultado inválido no puede conservar datos de una mano.")
        if self.posicion_indice is not None and (
            len(self.posicion_indice) != 2
            or any(not isfinite(valor) or not 0 <= valor <= 1 for valor in self.posicion_indice)
        ):
            raise ValueError("La posición del índice necesita dos coordenadas entre 0 y 1.")
        if self.desplazamiento_indice is not None and (
            len(self.desplazamiento_indice) != 2
            or any(not isfinite(valor) for valor in self.desplazamiento_indice)
        ):
            raise ValueError("El desplazamiento necesita dos valores finitos.")
        if any(evento.instante_ms > self.instante_ms for evento in self.eventos) or any(
            anterior.instante_ms > siguiente.instante_ms
            for anterior, siguiente in zip(self.eventos, self.eventos[1:])
        ):
            raise ValueError("Los eventos deben estar ordenados y no ser posteriores al resultado.")

    @property
    def es_valido(self) -> bool:
        return self.estado is EstadoVision.MANO_DETECTADA and self.mano is not None

    @property
    def mano_detectada(self) -> bool:
        return self.es_valido

    @property
    def camara_disponible(self) -> bool:
        return self.estado in (
            EstadoVision.CAMARA_DISPONIBLE,
            EstadoVision.MANO_DETECTADA,
            EstadoVision.SIN_MANO,
            EstadoVision.MANO_PERDIDA,
            EstadoVision.MANO_NO_SELECCIONADA,
            EstadoVision.BAJA_CONFIANZA,
        )

    @property
    def desplazamiento_vertical(self) -> float | None:
        return self.desplazamiento_indice[1] if self.desplazamiento_indice is not None else None

    @property
    def eventos_actuales(self) -> tuple[EventoGesto, ...]:
        """Eventos del último fotograma; sin mano válida solo expone su fin."""
        return tuple(
            evento
            for evento in self.eventos
            if evento.instante_ms == self.instante_ms
            and (self.es_valido or evento.fase is FaseGesto.FIN)
        )


def validar_instante(instante_ms: int) -> None:
    if type(instante_ms) is not int or instante_ms < 0:
        raise ValueError("El instante debe ser un entero no negativo en milisegundos.")


@dataclass(frozen=True, slots=True)
class MuestraPostura:
    """Los puntos de entrenamiento se entregan en un cuadro isotrópico sin espejo."""

    instante_ms: int
    mano: ManoDetectada

    def __post_init__(self) -> None:
        validar_instante(self.instante_ms)


@dataclass(frozen=True, slots=True)
class PlantillaGesto:
    nombre: str
    muestras: tuple[MuestraPostura, ...]
    descriptor: tuple[float, ...]
    umbral_similitud: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "muestras", tuple(self.muestras))
        object.__setattr__(self, "descriptor", tuple(self.descriptor))
        if not self.nombre.strip() or len(self.muestras) < 20:
            raise ValueError("La plantilla necesita un nombre y al menos 20 muestras.")
        if len(self.descriptor) != 63 or not all(isfinite(valor) for valor in self.descriptor):
            raise ValueError("El descriptor necesita 63 valores finitos.")
        if not isfinite(self.umbral_similitud) or not 0 < self.umbral_similitud <= 1:
            raise ValueError("El umbral de similitud debe estar entre 0 (excluido) y 1.")
