from holocontrol.domain.errores import ErrorConflicto, ErrorNoEncontrado


class RepositorioPerfilesMemoria:
    """Doble de pruebas. Se pierde al cerrar y no reemplaza SQLite."""

    def __init__(self):
        self.perfiles = {}
        self.fallar_guardado = False


    def crear(self, perfil):
        if self.fallar_guardado:
            raise OSError("Almacenamiento no disponible")
        if perfil.id in self.perfiles:
            raise ErrorConflicto("Perfil ya existente")
        if any(p.nombre.casefold() == perfil.nombre.casefold()
               for p in self.perfiles.values()):
            raise ErrorConflicto("Nombre duplicado")
        self.perfiles[perfil.id] = perfil

    def actualizar(self, perfil):
        if self.fallar_guardado:
            raise OSError("Almacenamiento no disponible")
        if perfil.id not in self.perfiles:
            raise ErrorNoEncontrado("Perfil inexistente")
        if any(p.id != perfil.id and p.nombre.casefold() == perfil.nombre.casefold()
               for p in self.perfiles.values()):
            raise ErrorConflicto("Nombre duplicado")
        self.perfiles[perfil.id] = perfil


    def listar(self):
        return tuple(self.perfiles.values())

    def obtener(self, id_perfil):
        return self.perfiles.get(id_perfil)

    def eliminar(self, id_perfil):
        if id_perfil not in self.perfiles:
            raise ErrorNoEncontrado("Perfil inexistente")
        del self.perfiles[id_perfil]


class EjecutorRegistro:
    """Registra órdenes sin mover el mouse ni generar clics reales."""

    def __init__(self):
        self.llamadas = []
        self.activo = False
        self.mano = False
        self.fallar_accion = False
        self.fallar_activacion = False
        self.fallar_detencion = False

    def activar(self):
        if self.fallar_activacion:
            raise OSError("No se puede activar")
        self.activo = True

    def pausar(self):
        self.activo = False

    def detener(self):
        if self.fallar_detencion:
            raise OSError("No se puede detener")
        self.activo = self.mano = False

    def establecer_mano_detectada(self, detectado):
        self.mano = detectado

    def _registrar(self, *args):
        if self.fallar_accion:
            raise OSError("Fallo de dispositivo")
        assert self.activo and self.mano
        self.llamadas.append(args)

    def mover_cursor(self, x, y):
        self._registrar("mover", x, y)

    def clic_izquierdo(self):
        self._registrar("clic_izquierdo")

    def clic_derecho(self):
        self._registrar("clic_derecho")

    def desplazar(self, cantidad):
        self._registrar("desplazar", cantidad)


class RelojSimulado:
    def __init__(self):
        self.ahora = 100.0

    def __call__(self):
        return self.ahora

    def avanzar(self, segundos=0.5):
        self.ahora += segundos
        return self.ahora
