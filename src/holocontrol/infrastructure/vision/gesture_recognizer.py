from collections import deque

from holocontrol.infrastructure.vision.thumb_click import ThumbClick

from holocontrol.infrastructure.vision.configuration import ConfiguracionVision
from holocontrol.infrastructure.vision.geometry import (
    coordenadas_mano,
    angulo,
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
        self._thumb_click = ThumbClick()
        self._activo: str | None = None
        self._candidato: str | None = None
        self._inicio_candidato_ms = 0
        self._inicio_quieto_ms = 0
        self._inicio_activo_ms = 0
        self._confianza_activa = 0.0
        self._ancla: tuple[float, float] | None = None
        self._trayectoria: deque = deque()
        self._discreto_consumido = False
        self._ultimo_tres_dedos_ms = -1000
        self._ultimo_cursor_valido_ms = -1000
        self._ultimo_scroll_valido_ms = -1000

    @property
    def esperando_puno(self) -> bool:
        return self._candidato == GestoBasico.PUNO.value and self._activo is None

    def reiniciar(self, instante_ms: int) -> tuple[EventoGesto, ...]:
        self._thumb_click.reset()
        self._ultimo_scroll_valido_ms = -1000
        self._ultimo_tres_dedos_ms = -1000
        self._ultimo_cursor_valido_ms = -1000
        eventos = self._terminar_activo(instante_ms)
        self._candidato = None
        self._ancla = None
        self._trayectoria.clear()
        self._discreto_consumido = False
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
        posturas = puntuar_posturas_basicas(puntos)
        nombre, confianza = max(posturas, key=lambda postura: postura[1])
        scroll_score = dict(posturas)[GestoBasico.DOS_DEDOS]
        if (self._activo == GestoBasico.DOS_DEDOS.value
                and confianza < self.configuracion.umbral_gesto and scroll_score >= .45):
            # Once acquired, allow a slight bend while rotating the hand. A clear
            # different posture still ends scrolling immediately.
            return GestoBasico.DOS_DEDOS.value, self.configuracion.umbral_gesto
        if nombre is GestoBasico.PUNO and confianza >= self.configuracion.umbral_gesto:
            if (puntos[3][1] - puntos[4][1] > ancho_palma * .20
                    and puntos[2][1] - puntos[4][1] > ancho_palma * .5
                    and puntos[5][1] - puntos[4][1] > ancho_palma * .6
                    and puntos[2][1] - puntos[4][1] > abs(puntos[2][0] - puntos[4][0]) * 2.5
                    and angulo(puntos[2], puntos[3], puntos[4]) > 150):
                return GestoBasico.LIKE.value, confianza
            return nombre.value, confianza
        if nombre is GestoBasico.MENIQUE and confianza >= self.configuracion.umbral_gesto:
            dx = puntos[20][0] - puntos[17][0]
            dy = puntos[20][1] - puntos[17][1]
            # Screen directions, identical for either selected hand. Leave a
            # neutral diagonal region so rotating between commands cannot fire both.
            if -dx >= max(ancho_palma * .4, abs(dy) * 1.5):
                return GestoBasico.PULGAR_ABAJO.value, confianza
            if -dy >= max(ancho_palma * .4, abs(dx) * 1.5):
                return GestoBasico.MENIQUE.value, confianza
            return None, 0.0
        if nombre is GestoBasico.CUERNOS and confianza >= self.configuracion.umbral_gesto:
            return nombre.value, confianza
        # Keep the historical ID for saved drag bindings, but recognize a gun
        # posture instead of thumb/index contact. Angles work with either hand.
        if nombre is GestoBasico.INDICE and confianza >= self.configuracion.umbral_gesto:
            thumb = tuple(a-b for a,b in zip(puntos[4], puntos[2]))
            index = tuple(a-b for a,b in zip(puntos[8], puntos[5]))
            spread = angulo(thumb, (0, 0, 0), index)
            if (angulo(puntos[2], puntos[3], puntos[4]) >= 150
                    and puntos[2][1] - puntos[4][1] >= ancho_palma * .4
                    and 50 <= spread <= 140
                    and distancia(puntos[4], puntos[8]) >= ancho_palma * .6):
                return GestoBasico.PELLIZCO.value, confianza
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
        if (nombre == GestoBasico.PELLIZCO.value or self._activo == GestoBasico.PELLIZCO.value) and not self._thumb_click.held:
            # A held gun must neither freeze drawing nor click when released.
            self._thumb_click.reset()
            frozen, clicked = False, False
        else:
            frozen, clicked = self._thumb_click.update(mano, instante_ms, relacion_aspecto)
        if self._thumb_click.held:
            nombre, confianza = GestoBasico.PELLIZCO.value, 1.0
        if frozen:
            events = list(self._terminar_activo(instante_ms))
            self._candidato = None
            self._ultimo_cursor_valido_ms = -1000
            if clicked:
                events.extend(EventoGesto("pulgar", phase, instante_ms, 0, 1.0)
                              for phase in (FaseGesto.INICIO, FaseGesto.FIN))
            return tuple(events)
        if self._activo == GestoBasico.TRES_DEDOS.value and nombre is None:
            puntuacion = dict(puntuar_posturas_basicas(coordenadas_mano(mano, relacion_aspecto)))[GestoBasico.TRES_DEDOS]
            if puntuacion >= .35:
                nombre, confianza = GestoBasico.TRES_DEDOS.value, max(.6, puntuacion)
            elif instante_ms - self._ultimo_tres_dedos_ms <= 180:
                nombre, confianza = GestoBasico.TRES_DEDOS.value, self._confianza_activa
        if nombre == GestoBasico.TRES_DEDOS.value:
            # Only actual posture evidence refreshes the grace interval.
            puntuacion = dict(puntuar_posturas_basicas(coordenadas_mano(mano, relacion_aspecto)))[GestoBasico.TRES_DEDOS]
            if puntuacion >= .35:
                self._ultimo_tres_dedos_ms = instante_ms
        if nombre == GestoBasico.DOS_DEDOS.value:
            self._ultimo_scroll_valido_ms = instante_ms
        elif (nombre is None and self._activo == GestoBasico.DOS_DEDOS.value
              and instante_ms - self._ultimo_scroll_valido_ms <= 80):
            nombre, confianza = GestoBasico.DOS_DEDOS.value, self._confianza_activa
        if nombre == GestoBasico.INDICE.value:
            self._ultimo_cursor_valido_ms = instante_ms
        elif (nombre is None and self._activo == GestoBasico.INDICE.value
              and instante_ms - self._ultimo_cursor_valido_ms <= 80):
            # Brief posture ambiguity during movement should not restart cursor
            # stabilization. Lost hands are invalidated by ProcesadorVision.
            nombre, confianza = GestoBasico.INDICE.value, self._confianza_activa
        centro = (mano.puntos[9].x, mano.puntos[9].y)
        eventos: list[EventoGesto] = []
        if nombre != self._candidato:
            eventos.extend(self._terminar_activo(instante_ms))
            self._candidato = nombre
            self._inicio_candidato_ms = instante_ms
            self._inicio_quieto_ms = instante_ms
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
                # Mover la mano reinicia la quietud, pero no la estabilidad de su postura.
                self._inicio_quieto_ms = instante_ms
        espera_ms = (self.configuracion.pausa_palma_ms if nombre == GestoBasico.PALMA_ABIERTA.value
                     else 2000 if nombre == GestoBasico.PUNO.value
                     else 500 if nombre in (GestoBasico.MENIQUE.value, GestoBasico.CUERNOS.value)
                     else 250 if nombre in (GestoBasico.LIKE.value, GestoBasico.PULGAR_ABAJO.value)
                     else self.configuracion.estabilizacion_ms)
        inicio_espera_ms = self._inicio_candidato_ms
        if (nombre == GestoBasico.PALMA_ABIERTA.value and self._activo in (
                GestoBasico.DESLIZAMIENTO_IZQUIERDA.value, GestoBasico.DESLIZAMIENTO_DERECHA.value)
                and instante_ms - inicio_espera_ms >= espera_ms):
            eventos.extend(self._terminar_activo(instante_ms))
        if self._activo is None and instante_ms - inicio_espera_ms >= espera_ms:
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
