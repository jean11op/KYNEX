import sqlite3

import pytest

from holocontrol.domain.entities import Perfil
from holocontrol.infrastructure.persistence.conexion import BaseDatos
from holocontrol.infrastructure.persistence.errores import (
    ErrorPersistencia,
    ErrorDatosPersistidos,
)
from holocontrol.infrastructure.persistence.repositorio_perfil import (
    RepositorioPerfilesSQLite,
)


def test_rechaza_archivo_corrupto(tmp_path):
    ruta = tmp_path / "corrupta.sqlite3"

    # Creamos un archivo que no contiene una base SQLite válida.
    ruta.write_bytes(b"Esto no es una base de datos SQLite.")

    base = BaseDatos(ruta)

    with pytest.raises(ErrorPersistencia) as resultado:
        with base.transaccion() as conexion:
            conexion.execute("SELECT name FROM sqlite_master").fetchall()

    # El error conserva la causa original de SQLite.
    assert isinstance(resultado.value.__cause__, sqlite3.Error)


def test_ruta_no_disponible(tmp_path):
    obstaculo = tmp_path / "datos"

    # Hay un archivo donde debería existir una carpeta.
    obstaculo.write_text("Soy un archivo, no una carpeta.")

    base = BaseDatos(obstaculo / "prueba.sqlite3")

    with pytest.raises(ErrorPersistencia) as resultado:
        base.conectar()

    assert isinstance(resultado.value.__cause__, OSError)


def test_no_puede_escribir_en_base_solo_lectura(tmp_path, monkeypatch):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    repositorio = RepositorioPerfilesSQLite(base)

    def conectar_solo_lectura():
        # Abrimos realmente el archivo en modo de solo lectura.
        direccion = base.ruta.as_uri() + "?mode=ro"

        conexion = sqlite3.connect(
            direccion,
            uri=True,
            isolation_level=None,
        )

        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")

        return conexion

    # Solo durante este bloque sustituimos la conexión.
    with monkeypatch.context() as cambio:
        cambio.setattr(base, "conectar", conectar_solo_lectura)

        with pytest.raises(ErrorPersistencia):
            repositorio.crear(
                Perfil(id="perfil-1", nombre="Gabriela")
            )

    # La conexión normal se restaura y verificamos que no se guardó.
    assert repositorio.obtener("perfil-1") is None


def test_detecta_perfil_sin_configuracion(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    repositorio = RepositorioPerfilesSQLite(base)
    repositorio.crear(Perfil(id="perfil-1", nombre="Gabriela"))

    # Provocamos una inconsistencia para comprobar su detección.
    with base.transaccion() as conexion:
        conexion.execute(
            "DELETE FROM Configuracion WHERE id_perfil = ?",
            ("perfil-1",),
        )

    with pytest.raises(ErrorDatosPersistidos):
        repositorio.obtener("perfil-1")


def test_listar_detecta_perfil_incompleto(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    repositorio = RepositorioPerfilesSQLite(base)

    # Insertamos directamente un perfil sin su configuración.
    with base.transaccion() as conexion:
        conexion.execute(
            "INSERT INTO Perfil (id_perfil, nombre) VALUES (?, ?)",
            ("perfil-incompleto", "Incompleto"),
        )

    with pytest.raises(ErrorDatosPersistidos):
        repositorio.listar()


def test_error_sql_deshace_cambios_previos(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    with pytest.raises(ErrorPersistencia) as resultado:
        with base.transaccion() as conexion:
            conexion.execute(
                "INSERT INTO Perfil (id_perfil, nombre) VALUES (?, ?)",
                ("perfil-1", "Gabriela"),
            )

            # Esta tabla no existe y la operación debe fallar.
            conexion.execute(
                "INSERT INTO TablaInexistente (nombre) VALUES (?)",
                ("Dato",),
            )

    assert isinstance(resultado.value.__cause__, sqlite3.Error)

    # La inserción anterior también debe haberse deshecho.
    with base.transaccion() as conexion:
        fila = conexion.execute(
            "SELECT * FROM Perfil WHERE id_perfil = ?",
            ("perfil-1",),
        ).fetchone()

    assert fila is None


def test_datos_invalidos_conservan_error_de_integridad(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    # No confundimos una restricción incumplida con un fallo de archivo.
    with pytest.raises(sqlite3.IntegrityError):
        with base.transaccion() as conexion:
            conexion.execute(
                """
                INSERT INTO Perfil (
                    id_perfil, nombre, tiempo_espera_gesto_ms
                )
                VALUES (?, ?, ?)
                """,
                ("perfil-1", "Gabriela", -1),
            )


def test_cierra_conexion_despues_de_error(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()

    with pytest.raises(ErrorPersistencia):
        with base.transaccion() as conexion:
            conexion.execute("SELECT * FROM TablaInexistente")

    # La conexión usada debe haber quedado cerrada.
    with pytest.raises(sqlite3.ProgrammingError):
        conexion.execute("SELECT 1")