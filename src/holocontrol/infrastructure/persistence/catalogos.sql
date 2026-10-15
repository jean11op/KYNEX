INSERT INTO TipoAccion (id_tipo_accion, nombre)
VALUES
    ('mover_cursor', 'Mover cursor'),
    ('clic_izquierdo', 'Clic izquierdo'),
    ('clic_derecho', 'Clic derecho'),
    ('desplazar', 'Desplazar'),
    ('tecla', 'Tecla'),
    ('zoom', 'Zoom'),
    ('dictar', 'Dictar'),
    ('arrastrar', 'Arrastrar'),
    ('minimizar', 'Minimizar'),
    ('cambiar_ventana', 'Cambiar ventana'),
    ('pausar', 'Pausar')
ON CONFLICT(id_tipo_accion) DO NOTHING;

INSERT INTO Accion (id_accion, nombre, id_tipo_accion, cantidad)
VALUES
    ('flechas', 'Flechas en cuatro direcciones', 'tecla', 0),
    ('borrar', 'Borrar texto (mantener: borrar todo)', 'tecla', 0),
    ('enter', 'Enter', 'tecla', 0),
    ('escape', 'Escape', 'tecla', 0),
    ('volumen_subir', 'Subir volumen', 'tecla', 0),
    ('volumen_bajar', 'Bajar volumen', 'tecla', 0),
    ('zoom', 'Ampliar o reducir', 'zoom', 0),
    ('dictar', 'Activar/desactivar voz', 'dictar', 0),
    ('arrastrar', 'Arrastrar y dibujar', 'arrastrar', 0),
    ('cursor', 'Mover cursor', 'mover_cursor', 0),
    ('clic_izquierdo', 'Clic izquierdo', 'clic_izquierdo', 0),
    ('clic_derecho', 'Clic derecho', 'clic_derecho', 0),
    ('desplazar_arriba', 'Desplazar arriba', 'desplazar', 3),
    ('desplazar_abajo', 'Desplazar abajo', 'desplazar', -3),
    ('desplazar_vertical', 'Desplazamiento vertical de la mano', 'desplazar', 1),
    ('minimizar', 'Minimizar ventana', 'minimizar', 0),
    ('cambiar_ventana', 'Cambiar ventana (Alt+Tab)', 'cambiar_ventana', 0),
    ('pausar', 'Pausar control', 'pausar', 0)
ON CONFLICT(id_accion) DO NOTHING;

INSERT INTO Gesto (id_gesto, id_perfil, nombre, umbral_confianza)
VALUES
    ('pulgar_abajo', NULL, 'Meñique a la izquierda (borrar)', 0.6),
    ('indice', NULL, 'Índice extendido', 0.8),
    ('menique', NULL, 'Meñique arriba (Enter)', 0.6),
    ('cuernos', NULL, 'Indice y menique (Escape)', 0.6),
    ('like', NULL, 'Pulgar arriba (voz)', 0.6),
    ('zoom', NULL, 'Separar o juntar dos dedos', 0.6),
    ('pulgar', NULL, 'Abrir y cerrar pulgar', 0.8),
    ('pellizco', NULL, 'Pellizco', 0.8),
    ('tres_dedos', NULL, 'Tres dedos', 0.8),
    ('dos_dedos', NULL, 'Dos dedos', 0.8),
    ('subir', NULL, 'Deslizar arriba', 0.8),
    ('bajar', NULL, 'Deslizar abajo', 0.8),
    ('palma_abierta', NULL, 'Palma abierta', 0.8),
    ('puno', NULL, 'Puño', 0.6),
    ('deslizamiento_izquierda', NULL, 'Deslizamiento a la izquierda', 0.8),
    ('deslizamiento_derecha', NULL, 'Deslizamiento a la derecha', 0.8)
ON CONFLICT(id_gesto) DO NOTHING;

UPDATE Gesto SET umbral_confianza = 0.6
WHERE id_gesto = 'puno' AND id_perfil IS NULL;

UPDATE Gesto SET nombre = 'Pistola (mantener clic)', umbral_confianza = 0.6
WHERE id_gesto = 'pellizco' AND id_perfil IS NULL;

-- El identificador histórico conserva las asignaciones existentes.
UPDATE Gesto SET nombre = 'Meñique a la izquierda (borrar)'
WHERE id_gesto = 'pulgar_abajo' AND id_perfil IS NULL;

UPDATE Gesto SET nombre = 'Meñique arriba (Enter)'
WHERE id_gesto = 'menique' AND id_perfil IS NULL;
