from dataclasses import replace
from threading import RLock
from time import monotonic
from typing import Callable
from uuid import uuid4

from holocontrol.application.dto.reconocimiento import Reconocimiento
from holocontrol.application.dto.resultados import EstadoActualControl, ResultadoGesto
from holocontrol.domain.entities import (
    TipoAccion, Calibracion, Gesto, AsignacionGesto, Mano, Perfil, Configuracion,
)
from holocontrol.domain.errores import ErrorConflicto, ErrorControl, ErrorDominio, ErrorNoEncontrado
from holocontrol.domain.rules.catalogo import ACCIONES, GESTOS, asignaciones_predeterminadas
from holocontrol.domain.rules.validacion import validar_entero, validar_texto
from holocontrol.domain.value_objects.estado_control import EstadoControl
from holocontrol.ports.repositories.repositorio_perfil import RepositorioPerfiles
from holocontrol.ports.system_actions.ejecutor_control import EjecutorControl


class AplicacionControl:
    """Casos de uso del MVP local. No importa UI, cámara, SQLite ni PyAutoGUI.

    Serializa las operaciones de control con RLock. El repositorio y el ejecutor
    deben ser rápidos. Ejecutar este servicio en un trabajador si el adaptador
    puede bloquear. En UI usar estado_actual(), sin acceder a atributos privados.
    """

    def __init__(self, repositorio: RepositorioPerfiles, ejecutor: EjecutorControl,
                 reloj: Callable[[], float] = monotonic):
        self._repositorio = repositorio
        self._ejecutor = ejecutor
        self._reloj = reloj
        self._bloqueo = RLock()
        self._seleccionado: str | None = None
        self._perfil_activo: Perfil | None = None
        self._estado = EstadoControl.STOPPED
        self._generacion = 0
        self._mano = False
        self._camara = False
        self._error: str | None = None
        self._ultimo_fotograma = float('-inf')
        self._ultima_accion = float('-inf')
        self._gesto_mantenido: str | None = None
        self._posicion: tuple[float, float] | None = None
        self._pantalla = (1, 1)
        self._acciones = {a.id: a for a in ACCIONES}
        self._gestos = {g.id: g for g in GESTOS}

    def estado_actual(self) -> EstadoActualControl:
        with self._bloqueo:
            return EstadoActualControl(self._estado, self._seleccionado, self._generacion,
                                 self._mano, self._camara, self._error)

    def _obtener_perfil(self, id_perfil: str) -> Perfil:
        perfil = self._repositorio.obtener(id_perfil)
        if perfil is None:
            raise ErrorNoEncontrado("El perfil no existe.")
        return perfil

    def _obtener_perfil_seleccionado(self) -> Perfil:
        if self._seleccionado is None:
            raise ErrorControl("Seleccione un perfil primero.")
        return self._obtener_perfil(self._seleccionado)

    def _nombre_unico(self, nombre: str, excluir: str | None = None) -> str:
        nombre = validar_texto(nombre, "Nombre del perfil")
        if any(p.id != excluir and p.nombre.casefold() == nombre.casefold()
               for p in self._repositorio.listar()):
            raise ErrorConflicto("Ya existe un perfil con ese nombre.")
        return nombre

    def listar_perfiles(self) -> tuple[Perfil, ...]:
        with self._bloqueo:
            return tuple(sorted(self._repositorio.listar(), key=lambda p: p.nombre.casefold()))

    def crear_perfil(self, nombre: str, mano_dominante: Mano = Mano.DERECHA,
                       tiempo_espera_gesto_ms: int = 400, limite_dictado: int = 250) -> Perfil:
        with self._bloqueo:
            identificador = str(uuid4())
            perfil = Perfil(identificador, self._nombre_unico(nombre), mano_dominante,
                              tiempo_espera_gesto_ms, limite_dictado,
                              asignaciones=asignaciones_predeterminadas(identificador))
            self._repositorio.crear(perfil)
            return perfil

    def _guardar_cambios(self, perfil: Perfil) -> Perfil:
        if self._seleccionado == perfil.id and self._estado is EstadoControl.ACTIVE:
            self.pausar_control()
        self._repositorio.guardar(perfil)
        return perfil

    def editar_perfil(self, id_perfil: str, *, nombre: str | None = None,
                     mano_dominante: Mano | None = None, tiempo_espera_gesto_ms: int | None = None,
                     limite_dictado: int | None = None) -> Perfil:
        with self._bloqueo:
            anterior = self._obtener_perfil(id_perfil)
            mano = anterior.mano_dominante if mano_dominante is None else mano_dominante
            return self._guardar_cambios(replace(
                anterior, nombre=anterior.nombre if nombre is None else self._nombre_unico(nombre, id_perfil),
                mano_dominante=mano,
                tiempo_espera_gesto_ms=anterior.tiempo_espera_gesto_ms if tiempo_espera_gesto_ms is None else tiempo_espera_gesto_ms,
                limite_dictado=anterior.limite_dictado if limite_dictado is None else limite_dictado,
                calibracion=anterior.calibracion if mano == anterior.mano_dominante else None,
            ))

    def seleccionar_perfil(self, id_perfil: str) -> Perfil:
        with self._bloqueo:
            perfil = self._obtener_perfil(id_perfil)
            if self._seleccionado != id_perfil:
                self.detener_control()
                self._seleccionado = id_perfil
            return perfil

    def eliminar_perfil(self, id_perfil: str, *, confirmado: bool = False) -> None:
        with self._bloqueo:
            self._obtener_perfil(id_perfil)
            if confirmado is not True:
                raise ErrorConflicto("Confirme la eliminación del perfil.")
            if self._seleccionado == id_perfil:
                self.detener_control()
            self._repositorio.eliminar(id_perfil)
            if self._seleccionado == id_perfil:
                self._seleccionado = None

    def calibrar_perfil(self, calibracion: Calibracion) -> Perfil:
        with self._bloqueo:
            return self._guardar_cambios(replace(self._obtener_perfil(calibracion.id_perfil),
                                              calibracion=calibracion))

    def cambiar_configuracion(self, id_perfil: str, configuracion: Configuracion) -> Perfil:
        with self._bloqueo:
            return self._guardar_cambios(replace(self._obtener_perfil(id_perfil), configuracion=configuracion))

    def listar_acciones(self):
        return ACCIONES

    def listar_gestos(self, id_perfil: str) -> tuple[Gesto, ...]:
        with self._bloqueo:
            return GESTOS + self._obtener_perfil(id_perfil).gestos

    def guardar_gesto(self, id_perfil: str, nombre: str, umbral_confianza: float = 0.8,
                     id_gesto: str | None = None) -> Gesto:
        with self._bloqueo:
            perfil = self._obtener_perfil(id_perfil)
            if id_gesto in self._gestos:
                raise ErrorConflicto("Los gestos predefinidos no se pueden modificar.")
            if id_gesto is not None and not any(g.id == id_gesto for g in perfil.gestos):
                raise ErrorNoEncontrado("El gesto no pertenece a este perfil.")
            gesto = Gesto(id_gesto or str(uuid4()), nombre, id_perfil, umbral_confianza)
            if any(g.id != gesto.id and g.nombre.casefold() == gesto.nombre.casefold()
                   for g in self.listar_gestos(id_perfil)):
                raise ErrorConflicto("Ya existe un gesto con ese nombre.")
            self._guardar_cambios(replace(perfil, gestos=tuple(
                g for g in perfil.gestos if g.id != gesto.id) + (gesto,)))
            return gesto

    def eliminar_gesto(self, id_perfil: str, id_gesto: str) -> None:
        with self._bloqueo:
            if id_gesto in self._gestos:
                raise ErrorConflicto("Los gestos predefinidos no se pueden eliminar.")
            perfil = self._obtener_perfil(id_perfil)
            if not any(g.id == id_gesto for g in perfil.gestos):
                raise ErrorNoEncontrado("El gesto no pertenece a este perfil.")
            self._guardar_cambios(replace(
                perfil, gestos=tuple(g for g in perfil.gestos if g.id != id_gesto),
                asignaciones=tuple(a for a in perfil.asignaciones if a.id_gesto != id_gesto),
            ))

    def configurar_gesto(self, id_perfil: str, id_gesto: str, id_accion: str,
                          *, activo: bool = True, reemplazar_existente: bool = False) -> Perfil:
        with self._bloqueo:
            perfil = self._obtener_perfil(id_perfil)
            if not any(g.id == id_gesto for g in self.listar_gestos(id_perfil)):
                raise ErrorDominio("El gesto no está disponible para este perfil.")
            if id_accion not in self._acciones:
                raise ErrorDominio("Acción no permitida.")
            asignacion = AsignacionGesto(id_perfil, id_gesto, id_accion, activo)
            actual = next((a for a in perfil.asignaciones if a.id_gesto == id_gesto), None)
            if actual is not None and actual.id_accion != id_accion and not reemplazar_existente:
                raise ErrorConflicto("El gesto ya tiene otra acción; confirme su reemplazo.")
            return self._guardar_cambios(replace(perfil, asignaciones=tuple(
                a for a in perfil.asignaciones if a.id_gesto != id_gesto) + (asignacion,)))

    def restaurar_asignaciones(self, id_perfil: str, *, confirmado: bool = False) -> Perfil:
        with self._bloqueo:
            perfil = self._obtener_perfil(id_perfil)
            if confirmado is not True:
                raise ErrorConflicto("Confirme la restauración de asignaciones.")
            return self._guardar_cambios(replace(perfil, asignaciones=asignaciones_predeterminadas(id_perfil)))

    def _reiniciar_deteccion(self) -> None:
        self._mano = False
        self._perfil_activo = None
        self._gesto_mantenido = None
        self._posicion = None
        self._ultimo_fotograma = float('-inf')
        self._ultima_accion = float('-inf')

    def _fallo_adaptador(self, causa: Exception) -> None:
        self._estado = EstadoControl.PAUSED
        self._generacion += 1
        self._reiniciar_deteccion()
        self._error = f"Falló el control: {causa}"
        try:
            self._ejecutor.detener()
        except Exception as error_detencion:
            self._error += f"; no se pudo detener el adaptador: {error_detencion}"

    def iniciar_control(self, *, camara_disponible: bool, ancho_pantalla: int,
                      alto_pantalla: int) -> EstadoActualControl:
        with self._bloqueo:
            perfil = self._obtener_perfil_seleccionado()
            if self._estado is not EstadoControl.STOPPED:
                raise ErrorControl("Detenga el control o use reanudar si está pausado.")
            return self._activar(perfil, camara_disponible, ancho_pantalla, alto_pantalla)

    def _activar(self, perfil, camara_disponible, ancho_pantalla, alto_pantalla):
        if camara_disponible is not True:
            raise ErrorControl("La cámara no está disponible.")
        if perfil.calibracion is None:
            raise ErrorControl("Calibre el perfil antes de iniciar.")
        validar_entero(ancho_pantalla, "Ancho de pantalla", 1, 100000)
        validar_entero(alto_pantalla, "Alto de pantalla", 1, 100000)
        self._validar_configuracion(perfil)
        self._generacion += 1
        self._reiniciar_deteccion()
        self._pantalla = (ancho_pantalla, alto_pantalla)
        try:
            self._ejecutor.establecer_mano_detectada(False)
            self._ejecutor.activar()
        except Exception as exc:
            self._fallo_adaptador(exc)
            raise ErrorControl(self._error) from exc
        self._estado = EstadoControl.ACTIVE
        self._perfil_activo = perfil
        self._camara = True
        self._pantalla = (ancho_pantalla, alto_pantalla)
        self._error = None
        return self.estado_actual()

    def _validar_configuracion(self, perfil: Perfil) -> None:
        gestos = {g.id for g in GESTOS + perfil.gestos}
        if any(g.id in self._gestos for g in perfil.gestos):
            raise ErrorDominio("Un gesto personalizado usa un identificador reservado.")
        if any(a.id_accion not in self._acciones or a.id_gesto not in gestos
               for a in perfil.asignaciones):
            raise ErrorDominio("El perfil contiene una asignación inválida.")

    def pausar_control(self) -> EstadoActualControl:
        with self._bloqueo:
            if self._estado is EstadoControl.STOPPED:
                return self.estado_actual()
            self._estado = EstadoControl.PAUSED
            self._generacion += 1
            self._reiniciar_deteccion()
            try:
                self._ejecutor.pausar()
                self._ejecutor.establecer_mano_detectada(False)
            except Exception as exc:
                self._fallo_adaptador(exc)
                raise ErrorControl(self._error) from exc
            return self.estado_actual()

    def reanudar_control(self, *, camara_disponible: bool) -> EstadoActualControl:
        with self._bloqueo:
            if self._estado is not EstadoControl.PAUSED:
                raise ErrorControl("El control no está pausado.")
            return self._activar(self._obtener_perfil_seleccionado(), camara_disponible, *self._pantalla)

    def detener_control(self) -> EstadoActualControl:
        with self._bloqueo:
            self._estado = EstadoControl.STOPPED
            self._generacion += 1
            self._reiniciar_deteccion()
            self._camara = False
            try:
                self._ejecutor.detener()
            except Exception as exc:
                self._error = f"No se pudo detener el adaptador: {exc}"
                raise ErrorControl(self._error) from exc
            self._error = None
            return self.estado_actual()

    def finalizar_sesion(self) -> EstadoActualControl:
        with self._bloqueo:
            self.detener_control()
            self._seleccionado = None
            return self.estado_actual()

    def informar_perdida_camara(self, mensaje: str = "Se perdió la cámara.") -> EstadoActualControl:
        with self._bloqueo:
            try:
                self.pausar_control()
            finally:
                self._camara = False
                self._error = str(mensaje)
            return self.estado_actual()

    def _posicion_cursor(self, fotograma: Reconocimiento, calibracion: Calibracion) -> tuple[int, int]:
        if fotograma.x is None or fotograma.y is None:
            raise ErrorDominio("El gesto de cursor necesita ambas coordenadas.")
        x = (fotograma.x - calibracion.x_min) / (calibracion.x_max - calibracion.x_min)
        y = (fotograma.y - calibracion.y_min) / (calibracion.y_max - calibracion.y_min)
        x = max(0, min(1, (x - 0.5) * calibracion.sensibilidad + 0.5))
        y = max(0, min(1, (y - 0.5) * calibracion.sensibilidad + 0.5))
        if self._posicion is not None:
            peso = 1 - 0.95 * calibracion.suavizado
            x = self._posicion[0] + peso * (x - self._posicion[0])
            y = self._posicion[1] + peso * (y - self._posicion[1])
        self._posicion = (x, y)
        return round(x * (self._pantalla[0] - 1)), round(y * (self._pantalla[1] - 1))

    def procesar_reconocimiento(self, fotograma: Reconocimiento) -> ResultadoGesto:
        with self._bloqueo:
            if self._estado is not EstadoControl.ACTIVE:
                return ResultadoGesto(False, "control_inactivo")
            if fotograma.generacion != self._generacion:
                return ResultadoGesto(False, "generacion_anterior")
            ahora = self._reloj()
            if fotograma.instante_captura <= self._ultimo_fotograma:
                return ResultadoGesto(False, "fotograma_fuera_de_orden")
            if fotograma.instante_captura > ahora or ahora - fotograma.instante_captura > 0.25:
                return ResultadoGesto(False, "fotograma_vencido")
            self._ultimo_fotograma = fotograma.instante_captura
            try:
                self._ejecutor.establecer_mano_detectada(fotograma.mano_detectada)
                self._mano = fotograma.mano_detectada
                if not fotograma.mano_detectada:
                    self._gesto_mantenido = None
                    self._posicion = None
                    return ResultadoGesto(False, "sin_mano")
                perfil = self._perfil_activo
                if perfil is None:
                    raise ErrorControl("No hay una configuración activa.")
                gesto = next((g for g in GESTOS + perfil.gestos
                                if g.id == fotograma.id_gesto), None)
                if gesto is None:
                    if fotograma.id_gesto is None:
                        self._gesto_mantenido = None
                    return ResultadoGesto(False, "sin_gesto_valido")
                if fotograma.confianza < gesto.umbral_confianza:
                    return ResultadoGesto(False, "confianza_insuficiente")
                asignacion = next((a for a in perfil.asignaciones
                                   if a.id_gesto == gesto.id and a.activo), None)
                if asignacion is None:
                    return ResultadoGesto(False, "sin_asignacion_activa")
                accion = self._acciones.get(asignacion.id_accion)
                if accion is None:
                    return ResultadoGesto(False, "accion_no_permitida")
                continuo = accion.tipo is TipoAccion.MOVER_CURSOR
                if not continuo and self._gesto_mantenido == gesto.id:
                    return ResultadoGesto(False, "gesto_mantenido", accion.id)
                if not continuo and accion.tipo is not TipoAccion.PAUSAR:
                    if ahora - self._ultima_accion < perfil.tiempo_espera_gesto_ms / 1000:
                        self._gesto_mantenido = gesto.id
                        return ResultadoGesto(False, "tiempo_espera", accion.id)
                if accion.tipo is TipoAccion.MOVER_CURSOR:
                    if perfil.calibracion is None or fotograma.x is None:
                        return ResultadoGesto(False, "sin_coordenadas_o_calibracion", accion.id)
                    self._ejecutor.mover_cursor(*self._posicion_cursor(fotograma, perfil.calibracion))
                elif accion.tipo is TipoAccion.CLIC_IZQUIERDO:
                    self._ejecutor.clic_izquierdo()
                elif accion.tipo is TipoAccion.CLIC_DERECHO:
                    self._ejecutor.clic_derecho()
                elif accion.tipo is TipoAccion.DESPLAZAR:
                    self._ejecutor.desplazar(accion.cantidad)
                elif accion.tipo is TipoAccion.PAUSAR:
                    self.pausar_control()
                if self._estado is EstadoControl.ACTIVE:
                    self._gesto_mantenido = gesto.id
                    if not continuo:
                        self._ultima_accion = ahora
                return ResultadoGesto(True, "accion_enviada", accion.id)
            except Exception as exc:
                self._fallo_adaptador(exc)
                raise ErrorControl(self._error) from exc
