INSERT INTO TipoAccion (id_tipo_accion, nombre)
VALUES
    ('mover_cursor', 'Mover cursor'),
    ('clic_izquierdo', 'Clic izquierdo'),
    ('clic_derecho', 'Clic derecho'),
    ('desplazar', 'Desplazar'),
    ('pausar', 'Pausar')
ON CONFLICT(id_tipo_accion) DO NOTHING;

INSERT INTO Accion (id_accion, nombre, id_tipo_accion, cantidad)
VALUES
    ('cursor', 'Mover cursor', 'mover_cursor', 0),
    ('clic_izquierdo', 'Clic izquierdo', 'clic_izquierdo', 0),
    ('clic_derecho', 'Clic derecho', 'clic_derecho', 0),
    ('desplazar_arriba', 'Desplazar arriba', 'desplazar', 3),
    ('desplazar_abajo', 'Desplazar abajo', 'desplazar', -3),
    ('pausar', 'Pausar control', 'pausar', 0)
ON CONFLICT(id_accion) DO NOTHING;

INSERT INTO Gesto (id_gesto, id_perfil, nombre, umbral_confianza)
VALUES
    ('indice', NULL, 'Índice extendido', 0.8),
    ('pellizco', NULL, 'Pellizco', 0.8),
    ('dos_dedos', NULL, 'Dos dedos', 0.8),
    ('subir', NULL, 'Deslizar arriba', 0.8),
    ('bajar', NULL, 'Deslizar abajo', 0.8),
    ('palma', NULL, 'Palma abierta', 0.8)
ON CONFLICT(id_gesto) DO NOTHING;