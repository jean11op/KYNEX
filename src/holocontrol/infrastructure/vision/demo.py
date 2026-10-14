import argparse
from math import ceil, isfinite
from statistics import mean
from time import monotonic, perf_counter_ns

from holocontrol.infrastructure.vision import (
    CamaraOpenCV,
    ConfiguracionCamara,
    ConfiguracionVision,
    DetectorMediaPipe,
    EntrenadorGestos,
    ProcesadorVision,
)
from holocontrol.infrastructure.vision.errors import ErrorVision
from holocontrol.ports.vision.models import FaseGesto, Lateralidad


def percentil_95(valores: list[float]) -> float:
    return sorted(valores)[max(0, ceil(len(valores) * 0.95) - 1)]


def main(argumentos: list[str] | None = None) -> int:
    import cv2

    parser = argparse.ArgumentParser(
        description="Diagnóstico local de visión de Kinex. No ejecuta acciones de Windows ni graba video.",
    )
    parser.add_argument(
        "--camara", type=int, default=0, help="Índice de la webcam (por defecto: 0)."
    )
    parser.add_argument("--mano", choices=[mano.value for mano in Lateralidad], default="derecha")
    parser.add_argument(
        "--duracion", type=float, default=15, help="Duración de la prueba en segundos."
    )
    parser.add_argument(
        "--sin-vista", action="store_true", help="Prueba por consola, sin ventana de video."
    )
    parser.add_argument("--sin-espejo", action="store_true")
    parser.add_argument(
        "--entrenar", metavar="NOMBRE", help="Entrena y prueba una postura propia en memoria."
    )
    opciones = parser.parse_args(argumentos)
    if not isfinite(opciones.duracion) or opciones.duracion <= 0:
        parser.error("La duración debe ser positiva.")
    try:
        configuracion_camara = ConfiguracionCamara(
            indice=opciones.camara,
            espejo=not opciones.sin_espejo,
        )
        configuracion = ConfiguracionVision(mano_dominante=Lateralidad(opciones.mano))
    except ValueError as error:
        parser.error(str(error))
    procesador = ProcesadorVision(configuracion)
    entrenador = (
        EntrenadorGestos(
            configuracion.mano_dominante, umbral_lateralidad=configuracion.umbral_lateralidad
        )
        if opciones.entrenar
        else None
    )
    latencias: list[float] = []
    ultimo_estado = None
    print(
        "Presenta primero el índice abierto; después prueba el pellizco. Salida: Esc, Q o Ctrl+C."
    )
    if entrenador is not None:
        print(
            "Mantén tu postura propia: se necesitan 20 muestras coherentes, distintas de los gestos básicos."
        )
    inicio = monotonic()
    try:
        with (
            CamaraOpenCV(configuracion_camara) as camara,
            DetectorMediaPipe(configuracion) as detector,
        ):
            while monotonic() - inicio < opciones.duracion:
                fotograma = camara.leer()
                inicio_procesamiento_ns = perf_counter_ns()
                deteccion = detector.detectar(fotograma)
                resultado = procesador.interpretar(deteccion)
                latencias.append((perf_counter_ns() - inicio_procesamiento_ns) / 1_000_000)
                if entrenador is not None and (
                    not entrenador.muestras
                    or fotograma.instante_ms - entrenador.muestras[-1].instante_ms >= 50
                ):
                    try:
                        entrenador.registrar(deteccion)
                    except ValueError:
                        pass
                    else:
                        print(f"Muestras: {len(entrenador.muestras)}/20")
                        if len(entrenador.muestras) >= 20:
                            try:
                                plantilla = entrenador.finalizar(opciones.entrenar)
                            except ValueError as error:
                                raise ErrorVision(str(error)) from error
                            procesador = ProcesadorVision(configuracion, plantillas=(plantilla,))
                            entrenador = None
                            print("Postura validada. Ahora cambia de postura y vuelve a probarla.")
                if resultado.estado != ultimo_estado:
                    print(f"Estado: {resultado.estado.value}. {resultado.mensaje}")
                    ultimo_estado = resultado.estado
                for evento in resultado.eventos:
                    if evento.fase is not FaseGesto.MANTENIMIENTO:
                        print(
                            f"Gesto: {evento.nombre}, {evento.fase.value}; "
                            f"duración {evento.duracion_ms} ms; puntuación {evento.confianza:.2f}"
                        )
                if not opciones.sin_vista:
                    imagen = fotograma.imagen.copy()
                    alto, ancho = imagen.shape[:2]
                    if resultado.mano is not None:
                        for punto in resultado.mano.puntos:
                            cv2.circle(
                                imagen,
                                (round(punto.x * ancho), round(punto.y * alto)),
                                3,
                                (60, 230, 100),
                                -1,
                            )
                    cv2.putText(
                        imagen,
                        resultado.estado.value,
                        (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                    )
                    cv2.imshow("Kinex - prueba de vision", imagen)
                    if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                        break
                    if cv2.getWindowProperty("Kinex - prueba de vision", cv2.WND_PROP_VISIBLE) < 1:
                        break
    except (ErrorVision, cv2.error) as error:
        print(f"No se pudo completar la prueba: {error}")
        return 1
    except KeyboardInterrupt:
        print("Prueba detenida por el usuario.")
    finally:
        if not opciones.sin_vista:
            cv2.destroyAllWindows()
    duracion = monotonic() - inicio
    if entrenador is not None:
        print(
            "El entrenamiento no alcanzó 20 muestras válidas. Repite con buena iluminación y una sola mano."
        )
        return 1
    if latencias:
        print(
            f"Fotogramas: {len(latencias)}; FPS observados: {len(latencias) / duracion:.1f}; "
            f"procesamiento medio: {mean(latencias):.1f} ms; p95: {percentil_95(latencias):.1f} ms."
        )
        print(
            "Estos tiempos excluyen la espera de intención y la ejecución de acciones del sistema."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
