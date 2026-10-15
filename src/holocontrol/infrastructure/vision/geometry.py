from math import acos, degrees, sqrt

from holocontrol.ports.vision.models import GestoBasico, ManoDetectada, PuntoMano


def coordenadas_mano(mano: ManoDetectada, relacion_aspecto: float) -> tuple:
    # x y z usan la escala del ancho; y se convierte para medir distancias isotrópicas.
    return tuple((p.x * relacion_aspecto, p.y, p.z * relacion_aspecto) for p in mano.puntos)


def distancia(primer_punto: tuple, segundo_punto: tuple) -> float:
    return sqrt(sum((a - b) ** 2 for a, b in zip(primer_punto, segundo_punto)))


def angulo(primer_punto: tuple, vertice: tuple, tercer_punto: tuple) -> float:
    primer_vector = tuple(a - b for a, b in zip(primer_punto, vertice))
    segundo_vector = tuple(a - b for a, b in zip(tercer_punto, vertice))
    norma = distancia(primer_vector, (0, 0, 0)) * distancia(segundo_vector, (0, 0, 0))
    if norma < 1e-9:
        return 0.0
    coseno = sum(a * b for a, b in zip(primer_vector, segundo_vector)) / norma
    return degrees(acos(max(-1.0, min(1.0, coseno))))


def puntuaciones_dedos(puntos: tuple) -> tuple[float, ...]:
    puntuaciones = []
    for base in (5, 9, 13, 17):
        rectitud = min(
            angulo(puntos[base], puntos[base + 1], puntos[base + 2]),
            angulo(puntos[base + 1], puntos[base + 2], puntos[base + 3]),
        )
        puntuacion = max(0.0, min(1.0, (rectitud - 120.0) / 50.0))
        if distancia(puntos[base + 3], puntos[0]) <= distancia(puntos[base + 1], puntos[0]):
            puntuacion = 0.0
        puntuaciones.append(puntuacion)
    return tuple(puntuaciones)


def descriptor_postura(mano: ManoDetectada, relacion_aspecto: float) -> tuple[float, ...]:
    puntos = coordenadas_mano(mano, relacion_aspecto)
    origen = puntos[0]
    escala = distancia(origen, puntos[9])
    eje_y = tuple((b - a) / escala for a, b in zip(origen, puntos[9])) if escala else ()
    lateral = tuple(b - a for a, b in zip(puntos[17], puntos[5]))
    if escala < 0.02:
        raise ValueError("La palma es demasiado pequeña o sus puntos son degenerados.")
    proyeccion = sum(a * b for a, b in zip(lateral, eje_y))
    eje_x = tuple(a - proyeccion * b for a, b in zip(lateral, eje_y))
    norma_x = distancia(eje_x, (0, 0, 0))
    if norma_x < 0.01:
        raise ValueError("No se puede determinar la orientación de la palma.")
    eje_x = tuple(valor / norma_x for valor in eje_x)
    eje_z = (
        eje_x[1] * eje_y[2] - eje_x[2] * eje_y[1],
        eje_x[2] * eje_y[0] - eje_x[0] * eje_y[2],
        eje_x[0] * eje_y[1] - eje_x[1] * eje_y[0],
    )
    descriptor = []
    for punto in puntos:
        relativo = tuple((valor - base) / escala for valor, base in zip(punto, origen))
        descriptor.extend(
            sum(a * b for a, b in zip(relativo, eje)) for eje in (eje_x, eje_y, eje_z)
        )
    return tuple(descriptor)


def puntuar_posturas_basicas(puntos: tuple) -> tuple:
    indice, medio, anular, menique = puntuaciones_dedos(puntos)
    return (
        (GestoBasico.MENIQUE, min(1 - indice, 1 - medio, 1 - anular, menique)),
        (GestoBasico.CUERNOS, min(indice, 1 - medio, 1 - anular, menique)),
        (GestoBasico.TRES_DEDOS, min(indice, medio, anular, 1 - menique)),
        (GestoBasico.INDICE, min(indice, 1 - medio, 1 - anular, 1 - menique)),
        (GestoBasico.DOS_DEDOS, min(indice, medio, 1 - anular, 1 - menique)),
        (GestoBasico.PALMA_ABIERTA, min(indice, medio, anular, menique)),
        (GestoBasico.PUNO, min(1 - indice, 1 - medio, 1 - anular, 1 - menique)),
    )


def normalizar_muestra(
    mano: ManoDetectada,
    relacion_aspecto: float,
    en_espejo: bool = False,
) -> ManoDetectada:
    # Coordenadas isotrópicas y sin espejo permiten persistir solo los 21 puntos.
    escala = max(1.0, relacion_aspecto)
    puntos = tuple(
        PuntoMano(
            punto.indice,
            (((1 - punto.x) if en_espejo else punto.x) - 0.5) * relacion_aspecto / escala + 0.5,
            (punto.y - 0.5) / escala + 0.5,
            punto.z * relacion_aspecto / escala,
        )
        for punto in mano.puntos
    )
    return ManoDetectada(puntos, mano.lateralidad, mano.confianza_lateralidad)
