from pathlib import Path
from typing import Self

from holocontrol.infrastructure.vision.configuration import ConfiguracionVision
from holocontrol.infrastructure.vision.errors import ErrorModelo
from holocontrol.ports.vision.models import (
    DeteccionManos,
    EstadoVision,
    Fotograma,
    Lateralidad,
    ManoDetectada,
    PuntoMano,
)


class DetectorMediaPipe:
    """Acepta uint8 BGR y entrega puntos sin exponer tipos de MediaPipe."""

    def __init__(self, configuracion: ConfiguracionVision | None = None) -> None:
        self.configuracion = configuracion or ConfiguracionVision()
        self._detector = None
        self._ultimo_instante_ms = -1

    def _abrir(self) -> None:
        if self._detector is not None:
            return
        import mediapipe as mp
        from mediapipe.tasks.python import vision

        ruta_modelo = self.configuracion.ruta_modelo or (
            Path(__file__).parent / "models" / "hand_landmarker.task"
        )
        if not ruta_modelo.is_file():
            raise ErrorModelo(f"Falta el modelo local de manos: {ruta_modelo}")
        opciones = vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(ruta_modelo)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=self.configuracion.umbral_deteccion,
            min_hand_presence_confidence=self.configuracion.umbral_presencia,
            min_tracking_confidence=self.configuracion.umbral_seguimiento,
        )
        try:
            self._detector = vision.HandLandmarker.create_from_options(opciones)
        except Exception as error:
            raise ErrorModelo("No se pudo inicializar MediaPipe con el modelo local.") from error

    def detectar(self, fotograma: Fotograma) -> DeteccionManos:
        import cv2
        import mediapipe as mp
        import numpy as np

        imagen = fotograma.imagen
        if (
            not isinstance(imagen, np.ndarray)
            or imagen.dtype != np.uint8
            or imagen.ndim != 3
            or imagen.shape[2] != 3
            or imagen.size == 0
        ):
            raise ValueError("Se requiere una imagen uint8 BGR de tres canales y tamaño no vacío.")
        if type(fotograma.instante_ms) is not int or fotograma.instante_ms < 0:
            raise ValueError("El instante debe ser un entero no negativo en milisegundos.")
        if fotograma.instante_ms <= self._ultimo_instante_ms:
            raise ValueError("Los instantes de los fotogramas deben aumentar estrictamente.")
        if self._detector is None:
            self._abrir()
        imagen_rgb = np.ascontiguousarray(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
        imagen_mp = mp.Image(image_format=mp.ImageFormat.SRGB, data=imagen_rgb)
        try:
            resultado = self._detector.detect_for_video(imagen_mp, fotograma.instante_ms)
        except Exception as error:
            raise ErrorModelo("Falló el procesamiento local de la imagen en MediaPipe.") from error
        self._ultimo_instante_ms = fotograma.instante_ms
        alto, ancho = imagen.shape[:2]
        manos = []
        hay_datos_invalidos = False
        if len(resultado.hand_landmarks) != len(resultado.handedness):
            raise ErrorModelo("MediaPipe entregó puntos sin lateralidad correspondiente.")
        for puntos_mp, categorias in zip(resultado.hand_landmarks, resultado.handedness):
            try:
                categoria = max(categorias, key=lambda elemento: elemento.score)
                lateralidad = {"Left": Lateralidad.IZQUIERDA, "Right": Lateralidad.DERECHA}[
                    categoria.category_name
                ]
                # Reflejar la imagen invierte la etiqueta del modelo, no la mano física.
                if fotograma.en_espejo:
                    lateralidad = (
                        Lateralidad.DERECHA
                        if lateralidad is Lateralidad.IZQUIERDA
                        else Lateralidad.IZQUIERDA
                    )
                puntos = tuple(
                    PuntoMano(indice, punto.x, punto.y, punto.z)
                    for indice, punto in enumerate(puntos_mp)
                )
                manos.append(ManoDetectada(puntos, lateralidad, categoria.score))
            except (ValueError, KeyError, TypeError):
                hay_datos_invalidos = True
        estado = EstadoVision.MANO_DETECTADA if manos else EstadoVision.SIN_MANO
        if not manos and hay_datos_invalidos:
            estado = EstadoVision.BAJA_CONFIANZA
        return DeteccionManos(
            fotograma.instante_ms,
            tuple(manos),
            estado,
            ancho,
            alto,
            "Puntos incompletos, fuera de imagen o lateralidad inválida."
            if hay_datos_invalidos
            else "",
            en_espejo=fotograma.en_espejo,
        )

    def cerrar(self) -> None:
        if self._detector is not None:
            detector, self._detector = self._detector, None
            detector.close()
        self._ultimo_instante_ms = -1

    def __enter__(self) -> Self:
        self._abrir()
        return self

    def __exit__(self, *_argumentos) -> None:
        self.cerrar()
