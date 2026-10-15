from holocontrol.domain.entities import Accion, AsignacionGesto, Gesto, TipoAccion

ACCIONES = (
    Accion("minimizar", "Minimizar ventana", TipoAccion.MINIMIZAR),
    Accion("cambiar_ventana", "Cambiar ventana (Alt+Tab)", TipoAccion.CAMBIAR_VENTANA),
    Accion("cursor", "Mover cursor", TipoAccion.MOVER_CURSOR),
    Accion("clic_izquierdo", "Clic izquierdo", TipoAccion.CLIC_IZQUIERDO),
    Accion("clic_derecho", "Clic derecho", TipoAccion.CLIC_DERECHO),
    Accion("desplazar_arriba", "Desplazar arriba", TipoAccion.DESPLAZAR, 3),
    Accion("desplazar_abajo", "Desplazar abajo", TipoAccion.DESPLAZAR, -3),
    Accion("desplazar_vertical", "Desplazamiento vertical de la mano", TipoAccion.DESPLAZAR, 1),
    Accion("pausar", "Pausar control", TipoAccion.PAUSAR),
)
GESTOS = (
    Gesto("tres_dedos", "Tres dedos", umbral_confianza=0.6),
    Gesto("indice", "Índice extendido"),
    Gesto("pellizco", "Pellizco"),
    Gesto("dos_dedos", "Dos dedos", umbral_confianza=0.6),
    Gesto("subir", "Deslizar arriba"),
    Gesto("bajar", "Deslizar abajo"),
    Gesto("palma_abierta", "Palma abierta"),
    Gesto("puno", "Puño"),
    Gesto("deslizamiento_izquierda", "Deslizamiento a la izquierda"),
    Gesto("deslizamiento_derecha", "Deslizamiento a la derecha"),
)
# Los gestos sin función implementada quedan disponibles, sin asignación automática.
PARES_PREDETERMINADOS = (
    ("puno", "minimizar"),
    ("tres_dedos", "cambiar_ventana"),
    ("indice", "cursor"),
    ("pellizco", "clic_izquierdo"),
    ("dos_dedos", "desplazar_vertical"),
    ("subir", "desplazar_arriba"),
    ("bajar", "desplazar_abajo"),
    ("palma_abierta", "pausar"),
)


# Genera las asignaciones predeterminadas de gestos a acciones para un perfil.
def asignaciones_predeterminadas(id_perfil: str) -> tuple[AsignacionGesto, ...]:
    return tuple(AsignacionGesto(id_perfil, gesto, accion) for gesto, accion in PARES_PREDETERMINADOS)
