import sqlite3

import pytest

from holocontrol.infrastructure.persistence.conexion import BaseDatos


def test_crea_archivo_y_carpeta(tmp_path):
    base = BaseDatos(tmp_path / "datos" / "prueba.sqlite3")

    with base.transaccion() as conexion:
        resultado = conexion.execute("SELECT 1").fetchone()
        assert resultado[0] == 1

    assert base.ruta.is_file()


def test_conserva_datos_al_reabrir(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")

    with base.transaccion() as conexion:
        conexion.execute(
            """
            CREATE TABLE prueba (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL
            )
            """
        )
        conexion.execute(
            "INSERT INTO prueba (nombre) VALUES (?)",
            ("Dato guardado",),
        )

    otra_base = BaseDatos(base.ruta)

    with otra_base.transaccion() as conexion:
        fila = conexion.execute(
            "SELECT nombre FROM prueba WHERE id = ?",
            (1,),
        ).fetchone()

    assert fila["nombre"] == "Dato guardado"


def test_deshace_cambios_si_falla(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")

    with base.transaccion() as conexion:
        conexion.execute(
            """
            CREATE TABLE prueba (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL
            )
            """
        )

    with pytest.raises(sqlite3.IntegrityError), base.transaccion() as conexion:
        conexion.execute(
            "INSERT INTO prueba (nombre) VALUES (?)",
            ("Este registro debe deshacerse",),
        )
        conexion.execute(
            "INSERT INTO prueba (nombre) VALUES (?)",
            (None,),
        )

    with base.transaccion() as conexion:
        fila = conexion.execute(
            "SELECT COUNT(*) AS total FROM prueba"
        ).fetchone()

    assert fila["total"] == 0


def test_respeta_claves_foraneas_al_reabrir(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")

    with base.transaccion() as conexion:
        conexion.execute(
            "CREATE TABLE padre (id INTEGER PRIMARY KEY)"
        )
        conexion.execute(
            """
            CREATE TABLE hijo (
                id INTEGER PRIMARY KEY,
                id_padre INTEGER NOT NULL,
                FOREIGN KEY (id_padre) REFERENCES padre(id)
            )
            """
        )

    with pytest.raises(sqlite3.IntegrityError), base.transaccion() as conexion:
        conexion.execute(
            "INSERT INTO hijo (id_padre) VALUES (?)",
            (999,),
        )
