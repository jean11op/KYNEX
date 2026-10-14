CREATE TABLE IF NOT EXISTS Perfil (
    id_perfil TEXT PRIMARY KEY NOT NULL
        CHECK (length(trim(id_perfil)) BETWEEN 1 AND 100),
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) BETWEEN 1 AND 100),
    mano_dominante TEXT NOT NULL DEFAULT 'derecha'
        CHECK (mano_dominante IN ('derecha', 'izquierda')),
    tiempo_espera_gesto_ms INTEGER NOT NULL DEFAULT 400
        CHECK (
            typeof(tiempo_espera_gesto_ms) = 'integer'
            AND tiempo_espera_gesto_ms BETWEEN 1 AND 10000
        ),
    limite_dictado INTEGER NOT NULL DEFAULT 250
        CHECK (
            typeof(limite_dictado) = 'integer'
            AND limite_dictado BETWEEN 1 AND 10000
        ),
    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Calibracion (
    id_perfil TEXT PRIMARY KEY NOT NULL,
    x_min REAL NOT NULL DEFAULT 0.0,
    x_max REAL NOT NULL DEFAULT 1.0,
    y_min REAL NOT NULL DEFAULT 0.0,
    y_max REAL NOT NULL DEFAULT 1.0,
    sensibilidad REAL NOT NULL DEFAULT 1.0
        CHECK (sensibilidad BETWEEN 0.1 AND 5.0),
    suavizado REAL NOT NULL DEFAULT 0.5
        CHECK (suavizado BETWEEN 0 AND 1),

    CHECK (x_min >= 0 AND x_max <= 1 AND x_min < x_max),
    CHECK (y_min >= 0 AND y_max <= 1 AND y_min < y_max),

    FOREIGN KEY (id_perfil)
        REFERENCES Perfil(id_perfil) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Configuracion (
    id_perfil TEXT PRIMARY KEY NOT NULL,
    indice_camara INTEGER NOT NULL DEFAULT 0
        CHECK (
            typeof(indice_camara) = 'integer'
            AND indice_camara BETWEEN 0 AND 100
        ),
    tema TEXT NOT NULL DEFAULT 'sistema'
        CHECK (tema IN ('claro', 'oscuro', 'sistema')),
    escala_interfaz REAL NOT NULL DEFAULT 1.0
        CHECK (escala_interfaz BETWEEN 1 AND 2),
    alto_contraste INTEGER NOT NULL DEFAULT 0
        CHECK (alto_contraste IN (0, 1)),
    minimizar_bandeja INTEGER NOT NULL DEFAULT 1
        CHECK (minimizar_bandeja IN (0, 1)),
    mostrar_avisos INTEGER NOT NULL DEFAULT 1
        CHECK (mostrar_avisos IN (0, 1)),
    atajo_pausa TEXT NOT NULL DEFAULT 'ctrl+alt+p'
        CHECK (atajo_pausa IN ('ctrl+alt+p', 'ctrl+shift+p', 'f8')),

    FOREIGN KEY (id_perfil)
        REFERENCES Perfil(id_perfil) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS TipoAccion (
    id_tipo_accion TEXT PRIMARY KEY NOT NULL
        CHECK (
            id_tipo_accion IN (
                'mover_cursor',
                'clic_izquierdo',
                'clic_derecho',
                'desplazar',
                'pausar'
            )
        ),
    nombre TEXT NOT NULL UNIQUE
        CHECK (length(trim(nombre)) BETWEEN 1 AND 100)
);

CREATE TABLE IF NOT EXISTS Accion (
    id_accion TEXT PRIMARY KEY NOT NULL
        CHECK (length(trim(id_accion)) BETWEEN 1 AND 100),
    nombre TEXT NOT NULL UNIQUE
        CHECK (length(trim(nombre)) BETWEEN 1 AND 100),
    id_tipo_accion TEXT NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 0
        CHECK (
            typeof(cantidad) = 'integer'
            AND cantidad BETWEEN -10 AND 10
        ),

    CHECK (
        (id_tipo_accion = 'desplazar' AND cantidad <> 0)
        OR
        (id_tipo_accion <> 'desplazar' AND cantidad = 0)
    ),

    FOREIGN KEY (id_tipo_accion)
        REFERENCES TipoAccion(id_tipo_accion) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Gesto (
    id_gesto TEXT PRIMARY KEY NOT NULL
        CHECK (length(trim(id_gesto)) BETWEEN 1 AND 100),
    id_perfil TEXT,
    nombre TEXT NOT NULL
        CHECK (length(trim(nombre)) BETWEEN 1 AND 100),
    umbral_confianza REAL NOT NULL DEFAULT 0.8
        CHECK (umbral_confianza BETWEEN 0 AND 1),

    FOREIGN KEY (id_perfil)
        REFERENCES Perfil(id_perfil) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS MuestraGesto (
    id_muestra INTEGER PRIMARY KEY,
    id_gesto TEXT NOT NULL,
    fecha_captura TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_gesto)
        REFERENCES Gesto(id_gesto) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS PuntoMuestra (
    id_muestra INTEGER NOT NULL,
    indice_punto INTEGER NOT NULL
        CHECK (
            typeof(indice_punto) = 'integer'
            AND indice_punto BETWEEN 0 AND 20
        ),
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,

    PRIMARY KEY (id_muestra, indice_punto),

    FOREIGN KEY (id_muestra)
        REFERENCES MuestraGesto(id_muestra) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AsignacionGesto (
    id_perfil TEXT NOT NULL,
    id_gesto TEXT NOT NULL,
    id_accion TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1
        CHECK (activo IN (0, 1)),

    PRIMARY KEY (id_perfil, id_gesto),

    FOREIGN KEY (id_perfil)
        REFERENCES Perfil(id_perfil) ON DELETE CASCADE,
    FOREIGN KEY (id_gesto)
        REFERENCES Gesto(id_gesto) ON DELETE CASCADE,
    FOREIGN KEY (id_accion)
        REFERENCES Accion(id_accion) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ComandoVoz (
    id_comando INTEGER PRIMARY KEY,
    id_perfil TEXT,
    frase TEXT NOT NULL CHECK (length(trim(frase)) > 0),
    id_accion TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1
        CHECK (activo IN (0, 1)),

    FOREIGN KEY (id_perfil)
        REFERENCES Perfil(id_perfil) ON DELETE CASCADE,
    FOREIGN KEY (id_accion)
        REFERENCES Accion(id_accion) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS Dibujo (
    id_dibujo INTEGER PRIMARY KEY,
    id_perfil TEXT NOT NULL,
    nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    ruta_imagen TEXT NOT NULL CHECK (length(trim(ruta_imagen)) > 0),
    fecha_creacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_perfil)
        REFERENCES Perfil(id_perfil) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS SesionUso (
    id_sesion INTEGER PRIMARY KEY,
    id_perfil TEXT NOT NULL,
    inicio TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fin TEXT,
    fps_promedio REAL CHECK (fps_promedio >= 0),

    FOREIGN KEY (id_perfil)
        REFERENCES Perfil(id_perfil) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS RegistroGesto (
    id_registro INTEGER PRIMARY KEY,
    id_sesion INTEGER NOT NULL,
    id_gesto TEXT NOT NULL,
    momento TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    latencia_ms REAL NOT NULL CHECK (latencia_ms >= 0),
    confianza REAL NOT NULL CHECK (confianza BETWEEN 0 AND 1),
    resultado TEXT NOT NULL
        CHECK (resultado IN ('ejecutado', 'descartado')),
    posible_error TEXT,

    FOREIGN KEY (id_sesion)
        REFERENCES SesionUso(id_sesion) ON DELETE CASCADE,
    FOREIGN KEY (id_gesto)
        REFERENCES Gesto(id_gesto) ON DELETE CASCADE
);

-- Impide asignar a un perfil un gesto personalizado de otro.
CREATE TRIGGER IF NOT EXISTS validar_asignacion_insertar
BEFORE INSERT ON AsignacionGesto
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM Gesto
    WHERE id_gesto = NEW.id_gesto
      AND id_perfil IS NOT NULL
      AND id_perfil <> NEW.id_perfil
)
BEGIN
    SELECT RAISE(ABORT, 'El gesto pertenece a otro perfil');
END;

CREATE TRIGGER IF NOT EXISTS validar_asignacion_actualizar
BEFORE UPDATE OF id_perfil, id_gesto ON AsignacionGesto
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM Gesto
    WHERE id_gesto = NEW.id_gesto
      AND id_perfil IS NOT NULL
      AND id_perfil <> NEW.id_perfil
)
BEGIN
    SELECT RAISE(ABORT, 'El gesto pertenece a otro perfil');
END;

-- Impide cambiar el propietario si invalida asignaciones existentes.
CREATE TRIGGER IF NOT EXISTS validar_propietario_gesto
BEFORE UPDATE OF id_perfil ON Gesto
FOR EACH ROW
WHEN NEW.id_perfil IS NOT NULL
AND EXISTS (
    SELECT 1
    FROM AsignacionGesto
    WHERE id_gesto = OLD.id_gesto
      AND id_perfil <> NEW.id_perfil
)
BEGIN
    SELECT RAISE(ABORT, 'El cambio invalida asignaciones existentes');
END;