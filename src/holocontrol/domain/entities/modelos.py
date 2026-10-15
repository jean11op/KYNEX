from dataclasses import dataclass, field
from enum import Enum

from holocontrol.domain.errores import ErrorDominio
from holocontrol.domain.rules.validacion import validar_entero, validar_numero, validar_texto

# Definimos los tipos de datos que se manejan en el dominio, como acciones, gestos, perfiles, etc.

class Mano(str, Enum):
    DERECHA = "derecha"
    IZQUIERDA = "izquierda"


class TipoAccion(str, Enum):
    MOVER_CURSOR = "mover_cursor"
    CLIC_IZQUIERDO = "clic_izquierdo"
    CLIC_DERECHO = "clic_derecho"
    DESPLAZAR = "desplazar"
    PAUSAR = "pausar"
    MINIMIZAR = "minimizar"
    CAMBIAR_VENTANA = "cambiar_ventana"


@dataclass(frozen=True)
class Calibracion:
    id_perfil: str
    x_min: float = 0.0
    x_max: float = 1.0
    y_min: float = 0.0
    y_max: float = 1.0
    sensibilidad: float = 1.0
    suavizado: float = 0.5

    def __post_init__(self):
        validar_texto(self.id_perfil, "Perfil")
        for nombre in ("x_min", "x_max", "y_min", "y_max"):
            validar_numero(getattr(self, nombre), nombre, 0, 1)
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ErrorDominio("Los mínimos de la zona deben ser menores que los máximos.")
        validar_numero(self.sensibilidad, "Sensibilidad", 0.1, 5.0)
        validar_numero(self.suavizado, "Suavizado", 0, 1)


@dataclass(frozen=True)
class Gesto:
    id: str
    nombre: str
    id_perfil: str | None = None
    umbral_confianza: float = 0.8

    def __post_init__(self):
        validar_texto(self.id, "Identificador de gesto")
        object.__setattr__(self, "nombre", validar_texto(self.nombre, "Nombre del gesto"))
        if self.id_perfil is not None:
            validar_texto(self.id_perfil, "Perfil")
        validar_numero(self.umbral_confianza, "Confianza", 0, 1)

    @property
    def predefinido(self) -> bool:
        return self.id_perfil is None


@dataclass(frozen=True)
class Accion:
    id: str
    nombre: str
    tipo: TipoAccion
    cantidad: int = 0

    def __post_init__(self):
        validar_texto(self.id, "Identificador de acción")
        object.__setattr__(self, "nombre", validar_texto(self.nombre, "Nombre de la acción"))
        if not isinstance(self.tipo, TipoAccion):
            raise ErrorDominio("Acción no admitida.")
        validar_entero(self.cantidad, "Desplazamiento", -10, 10)
        if self.tipo is TipoAccion.DESPLAZAR and self.cantidad == 0:
            raise ErrorDominio("El desplazamiento no puede ser cero.")
        if self.tipo is not TipoAccion.DESPLAZAR and self.cantidad != 0:
            raise ErrorDominio("Solo desplazar admite un desplazamiento.")


@dataclass(frozen=True)
class AsignacionGesto:
    id_perfil: str
    id_gesto: str
    id_accion: str
    activo: bool = True

    def __post_init__(self):
        for valor in (self.id_perfil, self.id_gesto, self.id_accion):
            validar_texto(valor, "Identificador de asignación")
        if type(self.activo) is not bool:
            raise ErrorDominio("El estado de la asignación debe ser booleano.")


@dataclass(frozen=True)
class Configuracion:
    indice_camara: int = 0
    tema: str = "sistema"
    escala_interfaz: float = 1.0
    alto_contraste: bool = False
    minimizar_bandeja: bool = True
    mostrar_avisos: bool = True
    atajo_pausa: str = "ctrl+alt+p"

    def __post_init__(self):
        validar_entero(self.indice_camara, "Cámara", 0, 100)
        if self.tema not in ("claro", "oscuro", "sistema"):
            raise ErrorDominio("Tema no admitido.")
        validar_numero(self.escala_interfaz, "Escala visual", 1, 2)
        if self.atajo_pausa not in ("ctrl+alt+p", "ctrl+shift+p", "f8"):
            raise ErrorDominio("Atajo de pausa no admitido.")
        for valor in (self.alto_contraste, self.minimizar_bandeja, self.mostrar_avisos):
            if type(valor) is not bool:
                raise ErrorDominio("Las preferencias deben ser booleanas.")


@dataclass(frozen=True)
class Perfil:
    id: str
    nombre: str
    mano_dominante: Mano = Mano.DERECHA
    tiempo_espera_gesto_ms: int = 400
    limite_dictado: int = 250
    calibracion: Calibracion | None = None
    configuracion: Configuracion = field(default_factory=Configuracion)
    gestos: tuple[Gesto, ...] = ()
    asignaciones: tuple[AsignacionGesto, ...] = ()

    def __post_init__(self):
        validar_texto(self.id, "Identificador del perfil")
        object.__setattr__(self, "nombre", validar_texto(self.nombre, "Nombre del perfil"))
        if not isinstance(self.mano_dominante, Mano):
            raise ErrorDominio("Seleccione mano derecha o izquierda.")
        validar_entero(self.tiempo_espera_gesto_ms, "Espera entre gestos", 1, 10000)
        validar_entero(self.limite_dictado, "Límite de dictado", 1, 10000)
        if not isinstance(self.configuracion, Configuracion):
            raise ErrorDominio("Configuración inválida.")
        if self.calibracion is not None and (
                not isinstance(self.calibracion, Calibracion) or self.calibracion.id_perfil != self.id):
            raise ErrorDominio("La calibración pertenece a otro perfil.")
        object.__setattr__(self, "gestos", tuple(self.gestos))
        object.__setattr__(self, "asignaciones", tuple(self.asignaciones))
        if any(g.id_perfil != self.id for g in self.gestos):
            raise ErrorDominio("El gesto personalizado pertenece a otro perfil.")
        if any(a.id_perfil != self.id for a in self.asignaciones):
            raise ErrorDominio("La asignación pertenece a otro perfil.")
        if len({g.id for g in self.gestos}) != len(self.gestos):
            raise ErrorDominio("Hay gestos duplicados.")
        if len({g.nombre.casefold() for g in self.gestos}) != len(self.gestos):
            raise ErrorDominio("Hay nombres de gesto duplicados.")
        if len({a.id_gesto for a in self.asignaciones}) != len(self.asignaciones):
            raise ErrorDominio("Cada gesto solo puede tener una asignación por perfil.")
