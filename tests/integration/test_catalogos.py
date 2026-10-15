from holocontrol.infrastructure.persistence.conexion import BaseDatos


def test_carga_acciones_y_tipos(tmp_path):
    # Creamos una base temporal y cargamos las tablas y catálogos.
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    with base.transaccion() as conexion:
        # Contamos los tipos de acción.
        resultado = conexion.execute(
            "SELECT COUNT(*) FROM TipoAccion"
        ).fetchone()

        cantidad_tipos = resultado[0]
        assert cantidad_tipos == 7

        # Contamos las acciones.
        resultado = conexion.execute(
            "SELECT COUNT(*) FROM Accion"
        ).fetchone()

        cantidad_acciones = resultado[0]
        assert cantidad_acciones == 9

        # Cada elemento contiene:
        # identificador de acción, tipo y cantidad de desplazamiento.
        acciones_esperadas = [
            ("cursor", "mover_cursor", 0),
            ("clic_izquierdo", "clic_izquierdo", 0),
            ("clic_derecho", "clic_derecho", 0),
            ("desplazar_arriba", "desplazar", 3),
            ("desplazar_abajo", "desplazar", -3),
            ("desplazar_vertical", "desplazar", 1),
            ("pausar", "pausar", 0),
        ]

        for accion in acciones_esperadas:
            identificador = accion[0]
            tipo_esperado = accion[1]
            cantidad_esperada = accion[2]

            fila = conexion.execute(
                "SELECT * FROM Accion WHERE id_accion = ?",
                (identificador,),
            ).fetchone()

            assert fila is not None
            assert fila["id_tipo_accion"] == tipo_esperado
            assert fila["cantidad"] == cantidad_esperada


def test_carga_gestos_compartidos(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    with base.transaccion() as conexion:
        resultado = conexion.execute(
            "SELECT COUNT(*) FROM Gesto"
        ).fetchone()

        cantidad_gestos = resultado[0]
        assert cantidad_gestos == 10

        gestos_esperados = [
            "indice",
            "pellizco",
            "dos_dedos",
            "subir",
            "bajar",
            "palma_abierta",
            "puno",
            "deslizamiento_izquierda",
            "deslizamiento_derecha",
        ]

        for identificador in gestos_esperados:
            fila = conexion.execute(
                "SELECT * FROM Gesto WHERE id_gesto = ?",
                (identificador,),
            ).fetchone()

            # El gesto debe existir.
            assert fila is not None

            # No pertenece a un perfil: es compartido.
            assert fila["id_perfil"] is None

            # Su confianza mínima inicial debe ser 0.8.
            assert fila["umbral_confianza"] == 0.8


def test_reinicializar_no_duplica_ni_borra_datos(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    # Agregamos un perfil y un gesto personalizado.
    with base.transaccion() as conexion:
        conexion.execute(
            """
            INSERT INTO Perfil (id_perfil, nombre)
            VALUES (?, ?)
            """,
            ("perfil-prueba", "Gabriela"),
        )

        conexion.execute(
            """
            INSERT INTO Gesto (id_gesto, id_perfil, nombre)
            VALUES (?, ?, ?)
            """,
            ("gesto-personal", "perfil-prueba", "Mi gesto"),
        )

    # Ejecutamos nuevamente la inicialización.
    base.inicializar()

    with base.transaccion() as conexion:
        # Los tipos y acciones no deben duplicarse.
        resultado = conexion.execute(
            "SELECT COUNT(*) FROM TipoAccion"
        ).fetchone()

        assert resultado[0] == 7

        resultado = conexion.execute(
            "SELECT COUNT(*) FROM Accion"
        ).fetchone()

        assert resultado[0] == 9

        # Debe haber seis gestos compartidos y uno personalizado.
        resultado = conexion.execute(
            "SELECT COUNT(*) FROM Gesto"
        ).fetchone()

        assert resultado[0] == 11

        # El perfil debe conservarse.
        perfil = conexion.execute(
            "SELECT nombre FROM Perfil WHERE id_perfil = ?",
            ("perfil-prueba",),
        ).fetchone()

        assert perfil is not None
        assert perfil["nombre"] == "Gabriela"

        # El gesto personalizado también debe conservarse.
        gesto = conexion.execute(
            "SELECT * FROM Gesto WHERE id_gesto = ?",
            ("gesto-personal",),
        ).fetchone()

        assert gesto is not None
        assert gesto["nombre"] == "Mi gesto"
        assert gesto["id_perfil"] == "perfil-prueba"


def test_migrates_old_action_constraint_without_losing_profile(tmp_path):
    from pathlib import Path
    from holocontrol.infrastructure.persistence import conexion as module
    base = BaseDatos(tmp_path / "old.sqlite3")
    folder = Path(module.__file__).parent
    schema = (folder / "esquema.sql").read_text(encoding="utf-8")
    schema = schema.replace("'pausar', 'minimizar', 'cambiar_ventana'", "'pausar'")
    with base.conectar() as connection:
        connection.executescript(schema)
        connection.execute("INSERT INTO TipoAccion VALUES ('mover_cursor', 'Mover cursor')")
        connection.execute("INSERT INTO Accion VALUES ('cursor', 'Mover cursor', 'mover_cursor', 0)")
        connection.execute("INSERT INTO Perfil (id_perfil, nombre) VALUES ('old', 'Original')")
    base.inicializar()
    base.inicializar()
    with base.transaccion() as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT nombre FROM Perfil WHERE id_perfil='old'").fetchone()[0] == 'Original'
        assert connection.execute("SELECT count(*) FROM TipoAccion").fetchone()[0] == 7
