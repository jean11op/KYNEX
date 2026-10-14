from math import sqrt

from holocontrol.infrastructure.vision.geometry import (
    coordenadas_mano,
    descriptor_postura,
    distancia,
    normalizar_muestra,
    puntuar_posturas_basicas,
)
from holocontrol.ports.vision.models import (
    DeteccionManos,
    EstadoVision,
    GestoBasico,
    Lateralidad,
    MuestraPostura,
    PlantillaGesto,
)


def distancia_descriptores(primer_descriptor: tuple, segundo_descriptor: tuple) -> float:
    return sqrt(sum((a - b) ** 2 for a, b in zip(primer_descriptor, segundo_descriptor)) / 63)


def similitud_plantilla(plantilla: PlantillaGesto, descriptor: tuple[float, ...]) -> float:
    # Es una similitud geométrica; no representa una probabilidad calibrada.
    return max(0.0, 1.0 - distancia_descriptores(plantilla.descriptor, descriptor) / 0.6)


class EntrenadorGestos:
    def __init__(
        self,
        mano_dominante: Lateralidad = Lateralidad.DERECHA,
        minimo_muestras: int = 20,
        umbral_lateralidad: float = 0.6,
    ) -> None:
        if type(minimo_muestras) is not int or minimo_muestras < 20:
            raise ValueError("El entrenamiento necesita al menos 20 muestras.")
        if not isinstance(mano_dominante, Lateralidad) or not 0 < umbral_lateralidad <= 1:
            raise ValueError("Lateralidad o umbral de entrenamiento inválidos.")
        self.mano_dominante = mano_dominante
        self.minimo_muestras = minimo_muestras
        self.umbral_lateralidad = umbral_lateralidad
        self._muestras: list[MuestraPostura] = []

    @property
    def muestras(self) -> tuple[MuestraPostura, ...]:
        return tuple(self._muestras)

    def registrar(self, deteccion: DeteccionManos) -> MuestraPostura:
        if deteccion.estado is not EstadoVision.MANO_DETECTADA:
            raise ValueError("No se pueden entrenar muestras de una detección inválida.")
        if deteccion.ancho <= 0 or deteccion.alto <= 0:
            raise ValueError("La muestra necesita dimensiones de imagen válidas.")
        manos = [
            mano
            for mano in deteccion.manos
            if mano.lateralidad is self.mano_dominante
            and mano.confianza_lateralidad >= self.umbral_lateralidad
        ]
        if len(manos) != 1:
            raise ValueError("La muestra necesita una única mano dominante con lateralidad fiable.")
        if self._muestras and deteccion.instante_ms - self._muestras[-1].instante_ms < 50:
            raise ValueError(
                "Separa las muestras al menos 50 ms; no reutilices el mismo fotograma."
            )
        mano_normalizada = normalizar_muestra(
            manos[0],
            deteccion.ancho / deteccion.alto,
            deteccion.en_espejo,
        )
        muestra = MuestraPostura(deteccion.instante_ms, mano_normalizada)
        descriptor_postura(muestra.mano, 1.0)
        self._muestras.append(muestra)
        return muestra

    def finalizar(self, nombre: str, umbral_similitud: float = 0.8) -> PlantillaGesto:
        nombre = nombre.strip()
        if not nombre or len(nombre) > 80 or nombre in {gesto.value for gesto in GestoBasico}:
            raise ValueError(
                "Usa un nombre propio de hasta 80 caracteres, distinto de los básicos."
            )
        if not 0 < umbral_similitud <= 1:
            raise ValueError("El umbral de similitud debe estar entre 0 (excluido) y 1.")
        if len(self._muestras) < self.minimo_muestras:
            raise ValueError(f"Faltan muestras válidas: se necesitan {self.minimo_muestras}.")
        descriptores = tuple(descriptor_postura(muestra.mano, 1.0) for muestra in self._muestras)
        centro = tuple(sum(columna) / len(descriptores) for columna in zip(*descriptores))
        if max(distancia_descriptores(centro, descriptor) for descriptor in descriptores) > 0.20:
            raise ValueError(
                "Las muestras representan posturas diferentes. Repite el entrenamiento."
            )
        # Cada muestra se compara con las restantes para no validar contra sí misma.
        for descriptor in descriptores:
            centro_restante = tuple(
                (valor * len(descriptores) - muestra) / (len(descriptores) - 1)
                for valor, muestra in zip(centro, descriptor)
            )
            similitud = max(0.0, 1 - distancia_descriptores(centro_restante, descriptor) / 0.6)
            if similitud < umbral_similitud:
                raise ValueError("La postura no es suficientemente consistente entre muestras.")
        for muestra in self._muestras:
            puntos = coordenadas_mano(muestra.mano, 1.0)
            confianza_basica = max(puntuacion for _, puntuacion in puntuar_posturas_basicas(puntos))
            pellizco = distancia(puntos[4], puntos[8]) / distancia(puntos[5], puntos[17]) <= 0.45
            if confianza_basica >= 0.6 or pellizco:
                raise ValueError("La postura coincide con un gesto básico; elige otra postura.")
        return PlantillaGesto(nombre, self.muestras, centro, umbral_similitud)

    def reiniciar(self) -> None:
        self._muestras.clear()
