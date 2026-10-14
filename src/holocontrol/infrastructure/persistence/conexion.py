import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class BaseDatos:
    """Administra las conexiones y transacciones de SQLite."""

    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta).expanduser().resolve()

    def inicializar(self) -> None:
        """Crea las tablas sin borrar los registros existentes."""
        archivo = Path(__file__).with_name("esquema.sql")
        esquema = archivo.read_text(encoding="utf-8")

        conexion = self.conectar()

        try:
            conexion.executescript(
                "BEGIN;\n" + esquema + "\nCOMMIT;"
            )
        except BaseException:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    def conectar(self) -> sqlite3.Connection:
        """Abre la base de datos y activa las claves foráneas."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)

        conexion = sqlite3.connect(
            self.ruta,
            timeout=5.0,
            isolation_level=None,
        )

        try:
            conexion.row_factory = sqlite3.Row
            conexion.execute("PRAGMA foreign_keys = ON")
            return conexion
        except BaseException:
            conexion.close()
            raise

    @contextmanager
    def transaccion(self) -> Iterator[sqlite3.Connection]:
        """Confirma los cambios o los deshace si ocurre un error."""
        conexion = self.conectar()

        try:
            conexion.execute("BEGIN")
            yield conexion
            conexion.commit()
        except BaseException:
            conexion.rollback()
            raise
        finally:
            conexion.close()