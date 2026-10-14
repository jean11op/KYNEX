import sqlite3

import pytest

from holocontrol.infrastructure.persistence.conexion import BaseDatos


@pytest.fixture
def base(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()
    return base


def test_crea_las_13_tablas(base):
    esperadas = {
        "Perfil",
        "Calibracion",
        "Configuracion",
        "TipoAccion",
        "Accion",
        "Gesto",
        "MuestraGesto",
        "PuntoMuestra",
        "AsignacionGesto",
        "ComandoVoz",
        "Dibujo",
        "SesionUso",
        "RegistroGesto",
    }

    with base.transaccion() as conexion:
        filas = conexion.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()

    assert {fila["name"] for fila in filas} == esperadas


def test_reinicializar_conserva_perfil(base):
    with base.transaccion() as conexion:
        conexion.execute(
            "INSERT INTO Perfil (id_perfil, nombre) VALUES (?, ?)",
            ("perfil-prueba", "Gabriela"),
        )

    base.inicializar()

    with base.transaccion() as conexion:
        fila = conexion.execute(
            "SELECT * FROM Perfil WHERE id_perfil = ?",
            ("perfil-prueba",),
        ).fetchone()

    assert fila["nombre"] == "Gabriela"
    assert fila["limite_dictado"] == 250


def test_rechaza_sensibilidad_fuera_del_rango(base):
    with base.transaccion() as conexion:
        conexion.execute(
            "INSERT INTO Perfil (id_perfil, nombre) VALUES (?, ?)",
            ("perfil-prueba", "Gabriela"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with base.transaccion() as conexion:
            conexion.execute(
                """
                INSERT INTO Calibracion (id_perfil, sensibilidad)
                VALUES (?, ?)
                """,
                ("perfil-prueba", 6.0),
            )


def test_eliminar_perfil_elimina_configuracion(base):
    with base.transaccion() as conexion:
        conexion.execute(
            "INSERT INTO Perfil (id_perfil, nombre) VALUES (?, ?)",
            ("perfil-prueba", "Gabriela"),
        )
        conexion.execute(
            "INSERT INTO Configuracion (id_perfil) VALUES (?)",
            ("perfil-prueba",),
        )

    with base.transaccion() as conexion:
        conexion.execute(
            "DELETE FROM Perfil WHERE id_perfil = ?",
            ("perfil-prueba",),
        )

    with base.transaccion() as conexion:
        fila = conexion.execute(
            "SELECT COUNT(*) AS total FROM Configuracion"
        ).fetchone()

    assert fila["total"] == 0


def test_impide_asignar_gesto_de_otro_perfil(base):
    with base.transaccion() as conexion:
        conexion.executemany(
            "INSERT INTO Perfil (id_perfil, nombre) VALUES (?, ?)",
            [("perfil-a", "Gabriela"), ("perfil-b", "Fernando")],
        )
        conexion.execute(
            """
            INSERT INTO Gesto (id_gesto, id_perfil, nombre)
            VALUES ('gesto-a', 'perfil-a', 'Gesto personal')
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        with base.transaccion() as conexion:
            conexion.execute(
                """
                INSERT INTO AsignacionGesto (
                    id_perfil, id_gesto, id_accion
                )
                VALUES ('perfil-b', 'gesto-a', 'clic_izquierdo')
                """
            )

    with base.transaccion() as conexion:
        conexion.execute(
            """
            INSERT INTO AsignacionGesto (
                id_perfil, id_gesto, id_accion
            )
            VALUES ('perfil-a', 'gesto-a', 'clic_izquierdo')
            """
        )