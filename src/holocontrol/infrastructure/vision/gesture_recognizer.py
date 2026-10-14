from collections import deque

from holocontrol.infrastructure.vision.configuration import ConfiguracionVision
from holocontrol.infrastructure.vision.geometry import (
    coordenadas_mano,
    descriptor_postura,
    distancia,
    normalizar_muestra,
    puntuar_posturas_basicas,
)
from holocontrol.infrastructure.vision.gesture_training import similitud_plantilla
from holocontrol.ports.vision.models import (
    EventoGesto,
    FaseGesto,
    GestoBasico,
    ManoDetectada,
    PlantillaGesto,
)


class ReconocedorGestos:
    def __init__(
        self,
        configuracion: ConfiguracionVision | None = None,
        plantillas: tuple[PlantillaGesto, ...] = (),
    ) -> None:
        self.configuracion = configuracion or ConfiguracionVision()
        self.plantillas = tuple(plantillas)
        if len({plantilla.nombre for plantilla in self.plantillas}) != len(self.plantillas):
            raise ValueError("Las plantillas deben tener nombres distintos.")
        self._activo: str | None = None
        self._candidato: str | None = None
        self._inicio_candidato_ms = 0
        self._inicio_activo_ms = 0
        self._confianza_activa = 0.0
        self._ancla: tuple[float, float] | None = None
        self._trayectoria: deque = deque()
        self._discreto_consumido = False
        self._pellizco_geometrico = False
        self._requiere_soltar_pellizco = True

    def reiniciar(self, instante_ms: int) -> tuple[EventoGesto, ...]:
        eventos = self._terminar_activo(instante_ms)
        self._candidato = None
        self._ancla = None
        self._trayectoria.clear()
        self._discreto_consumido = False
        self._pellizco_geometrico = False
        # Una mano recuperada ya cerrada no debe iniciar otro clic o arrastre.
        self._requiere_soltar_pellizco = True
        return eventos

    def _terminar_activo(self, instante_ms: int) -> tuple[EventoGesto, ...]:
        if self._activo is None:
            return ()
        evento = EventoGesto(
            self._activo,
            FaseGesto.FIN,
            instante_ms,
            max(0, instante_ms - self._inicio_activo_ms),
            self._confianza_activa,
        )
        self._activo = None
        return (evento,)

    def _clasificar(
        self,
        mano: ManoDetectada,
        relacion_aspecto: float,
        en_espejo: bool,
    ) -> tuple[str | None, float]:
        puntos = coordenadas_mano(mano, relacion_aspecto)
        ancho_palma = distancia(puntos[5], puntos[17])
        if ancho_palma < 0.02:
            return None, 0.0
        proporcion_pellizco = distancia(puntos[4], puntos[8]) / ancho_palma
        umbral = (
            self.configuracion.umbral_pellizco_salida
            if self._pellizco_geometrico
            else self.configuracion.umbral_pellizco_entrada
        )
        self._pellizco_geometrico = proporcion_pellizco <= umbral
        if not self._pellizco_geometrico:
            self._requiere_soltar_pellizco = False
        elif not self._requiere_soltar_pellizco:
            confianza = 1 - 0.3 * proporcion_pellizco / self.configuracion.umbral_pellizco_salida
            return GestoBasico.PELLIZCO.value, confianza
        else:
            return None, 0.0
        posturas = puntuar_posturas_basicas(puntos)
        nombre, confianza = max(posturas, key=lambda postura: postura[1])
        if confianza >= self.configuracion.umbral_gesto:
            return nombre.value, confianza
        if self.plantillas:
            descriptor = descriptor_postura(
                normalizar_muestra(mano, relacion_aspecto, en_espejo), 1.0
            )
            coincidencias = sorted(
                (
                    (similitud_plantilla(plantilla, descriptor), plantilla)
                    for plantilla in self.plantillas
                ),
                key=lambda elemento: elemento[0],
                reverse=True,
            )
            similitud, plantilla = coincidencias[0]
            if similitud >= plantilla.umbral_similitud and (
                len(coincidencias) == 1 or similitud - coincidencias[1][0] >= 0.05
            ):
                return f"personalizado:{plantilla.nombre}", similitud
        return None, 0.0

    def procesar(
        self,
        mano: ManoDetectada,
        instante_ms: int,
        relacion_aspecto: float,
        en_espejo: bool = False,
    ) -> tuple[EventoGesto, ...]:
        nombre, confianza = self._clasificar(mano, relacion_aspecto, en_espejo)
        centro = (mano.puntos[9].x, mano.puntos[9].y)
        eventos: list[EventoGesto] = []
        if nombre != self._candidato:
            eventos.extend(self._terminar_activo(instante_ms))
            self._candidato = nombre
            self._inicio_candidato_ms = instante_ms
            self._ancla = centro
            self._trayectoria.clear()
            self._discreto_consumido = False
        if nombre is None or confianza < self.configuracion.umbral_gesto:
            eventos.extend(self._terminar_activo(instante_ms))
            self._candidato = None
            self._ancla = None
            self._trayectoria.clear()
            self._discreto_consumido = False
            return tuple(eventos)
        permanencia = nombre in (GestoBasico.PALMA_ABIERTA.value, GestoBasico.PUNO.value)
        if permanencia and not self._discreto_consumido:
            self._trayectoria.append((instante_ms, centro))
            while (
                self._trayectoria
                and instante_ms - self._trayectoria[0][0]
                > self.configuracion.ventana_deslizamiento_ms
            ):
                self._trayectoria.popleft()
            if nombre == GestoBasico.PALMA_ABIERTA.value and len(self._trayectoria) >= 2:
                inicio_trayectoria = self._trayectoria[0][1]
                delta_x = centro[0] - inicio_trayectoria[0]
                delta_y = centro[1] - inicio_trayectoria[1]
                if (
                    abs(delta_x) >= self.configuracion.desplazamiento_deslizamiento
                    and abs(delta_y) <= abs(delta_x) * 0.5
                    and instante_ms - self._inicio_candidato_ms
                    >= self.configuracion.estabilizacion_ms
                ):
                    nombre = (
                        GestoBasico.DESLIZAMIENTO_DERECHA.value
                        if delta_x > 0
                        else GestoBasico.DESLIZAMIENTO_IZQUIERDA.value
                    )
                    self._activar(nombre, confianza, instante_ms)
                    self._discreto_consumido = True
                    eventos.append(self._evento(FaseGesto.INICIO, instante_ms))
                    return tuple(eventos)
            if distancia(centro, self._ancla) > self.configuracion.tolerancia_quieto:
                self._ancla = centro
                self._inicio_candidato_ms = instante_ms
        espera_ms = (
            self.configuracion.permanencia_ms
            if permanencia
            else (self.configuracion.estabilizacion_ms)
        )
        if self._activo is None and instante_ms - self._inicio_candidato_ms >= espera_ms:
            self._activar(nombre, confianza, instante_ms)
            if permanencia:
                self._discreto_consumido = True
            eventos.append(self._evento(FaseGesto.INICIO, instante_ms))
        elif self._activo is not None:
            self._confianza_activa = confianza
            eventos.append(self._evento(FaseGesto.MANTENIMIENTO, instante_ms))
        return tuple(eventos)

    def _activar(self, nombre: str, confianza: float, instante_ms: int) -> None:
        self._activo = nombre
        self._inicio_activo_ms = instante_ms
        self._confianza_activa = confianza

    def _evento(self, fase: FaseGesto, instante_ms: int) -> EventoGesto:
        return EventoGesto(
            self._activo,
            fase,
            instante_ms,
            instante_ms - self._inicio_activo_ms,
            self._confianza_activa,
        )
