from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from holocontrol.ports.vision.models import Lateralidad


@dataclass(frozen=True, slots=True)
class ConfiguracionCamara:
    indice: int = 0
    ancho: int = 640
    alto: int = 480
    fps: int = 30
    espejo: bool = True

    def __post_init__(self) -> None:
        if type(self.indice) is not int or self.indice < 0:
            raise ValueError("El índice de cámara debe ser un entero no negativo.")
        for nombre in ("ancho", "alto", "fps"):
            valor = getattr(self, nombre)
            if type(valor) is not int or valor <= 0:
                raise ValueError(f"{nombre} debe ser un entero positivo.")
        if type(self.espejo) is not bool:
            raise ValueError("espejo debe ser un booleano.")


@dataclass(frozen=True, slots=True)
class ConfiguracionVision:
    mano_dominante: Lateralidad = Lateralidad.DERECHA
    umbral_deteccion: float = 0.6
    umbral_presencia: float = 0.6
    umbral_seguimiento: float = 0.6
    umbral_lateralidad: float = 0.6
    umbral_gesto: float = 0.6
    estabilizacion_ms: int = 100
    permanencia_ms: int = 800
    pausa_palma_ms: int = 7000
    vigencia_ms: int = 200
    factor_suavizado: float = 0.35
    umbral_pellizco_entrada: float = 0.30
    umbral_pellizco_salida: float = 0.45
    desplazamiento_deslizamiento: float = 0.20
    ventana_deslizamiento_ms: int = 500
    tolerancia_quieto: float = 0.035
    salto_maximo_mano: float = 0.25
    ruta_modelo: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mano_dominante, Lateralidad):
            raise TypeError("Selecciona una lateralidad válida.")
        for nombre in (
            "umbral_deteccion",
            "umbral_presencia",
            "umbral_seguimiento",
            "umbral_lateralidad",
            "umbral_gesto",
            "factor_suavizado",
            "umbral_pellizco_entrada",
            "umbral_pellizco_salida",
            "desplazamiento_deslizamiento",
            "tolerancia_quieto",
            "salto_maximo_mano",
        ):
            valor = getattr(self, nombre)
            if not isfinite(valor) or not 0 < valor <= 1:
                raise ValueError(f"{nombre} debe estar entre 0 (excluido) y 1.")
        for nombre in (
            "estabilizacion_ms",
            "permanencia_ms",
            "pausa_palma_ms",
            "vigencia_ms",
            "ventana_deslizamiento_ms",
        ):
            valor = getattr(self, nombre)
            if type(valor) is not int or valor <= 0:
                raise ValueError(f"{nombre} debe ser un entero positivo.")
        if self.umbral_pellizco_entrada >= self.umbral_pellizco_salida:
            raise ValueError("La salida del pellizco debe superar el umbral de entrada.")
        if self.permanencia_ms < self.estabilizacion_ms:
            raise ValueError("La permanencia no puede ser menor que la estabilización.")
        if self.ruta_modelo is not None:
            object.__setattr__(self, "ruta_modelo", Path(self.ruta_modelo))
