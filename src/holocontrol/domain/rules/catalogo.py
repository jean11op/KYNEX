from holocontrol.domain.entities import Accion, TipoAccion, Gesto, AsignacionGesto

ACCIONES = (
    Accion("cursor", "Mover cursor", TipoAccion.MOVER_CURSOR),
    Accion("clic_izquierdo", "Clic izquierdo", TipoAccion.CLIC_IZQUIERDO),
    Accion("clic_derecho", "Clic derecho", TipoAccion.CLIC_DERECHO),
    Accion("desplazar_arriba", "Desplazar arriba", TipoAccion.DESPLAZAR, 3),
    Accion("desplazar_abajo", "Desplazar abajo", TipoAccion.DESPLAZAR, -3),
    Accion("pausar", "Pausar control", TipoAccion.PAUSAR),
)
GESTOS = (
    Gesto("indice", "Índice extendido"),
    Gesto("pellizco", "Pellizco"),
    Gesto("dos_dedos", "Dos dedos"),
    Gesto("subir", "Deslizar arriba"),
    Gesto("bajar", "Deslizar abajo"),
    Gesto("palma", "Palma abierta"),
)
PARES_PREDETERMINADOS = tuple(zip(
    ("indice", "pellizco", "dos_dedos", "subir", "bajar", "palma"),
    ("cursor", "clic_izquierdo", "clic_derecho", "desplazar_arriba", "desplazar_abajo", "pausar"),
))


# Genera las asignaciones predeterminadas de gestos a acciones para un perfil.
def asignaciones_predeterminadas(id_perfil: str) -> tuple[AsignacionGesto, ...]:
    return tuple(AsignacionGesto(id_perfil, gesto, accion) for gesto, accion in PARES_PREDETERMINADOS)
