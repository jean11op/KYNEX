from pathlib import Path

from holocontrol.domain.entities import (
    Perfil,
    Calibracion,
    Configuracion,
    AsignacionGesto,
)
from holocontrol.infrastructure.persistence.conexion import BaseDatos
from holocontrol.infrastructure.persistence.repositorio_perfil import (
    RepositorioPerfilesSQLite,
)


raiz = Path(__file__).resolve().parents[1]
base = BaseDatos(raiz / "data" / "holocontrol.sqlite3")
base.inicializar()

repositorio = RepositorioPerfilesSQLite(base)

# Identificador fijo para esta demostración
id_perfil = "perfil-demostracion"

# Preparamos la configuración
configuracion = Configuracion(
    tema="oscuro",
    escala_interfaz=1.25,
)

#son solo de ejemplo
calibracion = Calibracion(
    id_perfil=id_perfil,
    x_min=0.1,
    x_max=0.9,
    y_min=0.1,
    y_max=0.9,
    sensibilidad=1.5,
    suavizado=0.5,
)

#dos gestos compartidos que ya están en el catálogo.
clic = AsignacionGesto(
    id_perfil=id_perfil,
    id_gesto="pellizco",
    id_accion="clic_izquierdo",
)

pausa = AsignacionGesto(
    id_perfil=id_perfil,
    id_gesto="palma",
    id_accion="pausar",
)

perfil = Perfil(
    id=id_perfil,
    nombre="Perfil de demostración",
    configuracion=configuracion,
    calibracion=calibracion,
    asignaciones=(clic, pausa),
)


if repositorio.obtener(id_perfil) is None:
    repositorio.crear(perfil)
    print("Perfil de demostración creado.")
else:
    print("El perfil de demostración ya existe.")

guardado = repositorio.obtener(id_perfil)

print("Base utilizada:", base.ruta)
print("Identificador:", guardado.id)
print("Nombre:", guardado.nombre)
print("Tema:", guardado.configuracion.tema)
print("Cantidad de asignaciones:", len(guardado.asignaciones))