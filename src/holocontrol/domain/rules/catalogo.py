from holocontrol.domain.entities import Accion, AsignacionGesto, Gesto, TipoAccion

ACCIONES = (
    Accion("flechas", "Flechas en cuatro direcciones", TipoAccion.TECLA),
    Accion("borrar", "Borrar texto (mantener: borrar todo)", TipoAccion.TECLA),
    Accion("enter", "Enter", TipoAccion.TECLA),
    Accion("escape", "Escape", TipoAccion.TECLA),
    Accion("volumen_subir", "Subir volumen", TipoAccion.TECLA),
    Accion("volumen_bajar", "Bajar volumen", TipoAccion.TECLA),
    Accion("zoom", "Ampliar o reducir", TipoAccion.ZOOM),
    Accion("dictar", "Activar/desactivar voz", TipoAccion.DICTAR),
    Accion("arrastrar", "Arrastrar y dibujar", TipoAccion.ARRASTRAR),
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
    Gesto("pulgar_abajo", "Meñique a la izquierda (borrar)", umbral_confianza=0.6),
    Gesto("menique", "Meñique arriba (Enter)", umbral_confianza=0.6),
    Gesto("cuernos", "Indice y me\u00f1ique (Escape)", umbral_confianza=0.6),
    Gesto("like", "Pulgar arriba (voz)", umbral_confianza=0.6),
    Gesto("zoom", "Separar o juntar dos dedos", umbral_confianza=0.6),
    Gesto("pulgar", "Abrir y cerrar pulgar"),
    Gesto("tres_dedos", "Tres dedos", umbral_confianza=0.6),
    Gesto("indice", "Índice extendido"),
    Gesto("pellizco", "Pulgar sostenido (mantener clic)", umbral_confianza=0.6),
    Gesto("dos_dedos", "Dos dedos", umbral_confianza=0.6),
    Gesto("subir", "Deslizar arriba"),
    Gesto("bajar", "Deslizar abajo"),
    Gesto("palma_abierta", "Palma abierta"),
    Gesto("puno", "Puño", umbral_confianza=0.6),
    Gesto("deslizamiento_izquierda", "Deslizamiento a la izquierda"),
    Gesto("deslizamiento_derecha", "Deslizamiento a la derecha"),
)
# Los gestos sin función implementada quedan disponibles, sin asignación automática.
PARES_PREDETERMINADOS = (
    ("pulgar_abajo", "borrar"),
    ("menique", "enter"),
    ("cuernos", "escape"),
    ("deslizamiento_derecha", "volumen_subir"),
    ("deslizamiento_izquierda", "volumen_bajar"),
    ("like", "dictar"),
    ("zoom", "zoom"),
    ("pellizco", "arrastrar"),
    ("puno", "minimizar"),
    ("tres_dedos", "cambiar_ventana"),
    ("indice", "cursor"),
    ("pulgar", "clic_izquierdo"),
    ("dos_dedos", "flechas"),
    ("subir", "desplazar_arriba"),
    ("bajar", "desplazar_abajo"),
    ("palma_abierta", "pausar"),
)


# Genera las asignaciones predeterminadas de gestos a acciones para un perfil.
def asignaciones_predeterminadas(id_perfil: str) -> tuple[AsignacionGesto, ...]:
    return tuple(AsignacionGesto(id_perfil, gesto, accion) for gesto, accion in PARES_PREDETERMINADOS)
