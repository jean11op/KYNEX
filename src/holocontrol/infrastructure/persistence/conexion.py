import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class BaseDatos:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta).expanduser().resolve()

    def inicializar(self) -> None:
        """Crea las tablas y carga los catálogos."""
        carpeta = Path(__file__).parent
        esquema = (carpeta / "esquema.sql").read_text(encoding="utf-8")
        catalogos = (carpeta / "catalogos.sql").read_text(encoding="utf-8")

        conexion = self.conectar()

        try:
            conexion.executescript(
                "BEGIN;\n" + esquema + "\n" + catalogos + "\nCOMMIT;"
            )
        except BaseException:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    def conectar(self) -> sqlite3.Connection:
        """Abre una conexión con las claves foráneas activadas."""
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
        """Confirma todos los cambios o los deshace si ocurre un error."""
        conexion = self.conectar()

        try:
            conexion.execute("BEGIN IMMEDIATE")
            yield conexion
            conexion.commit()
        except BaseException:
            conexion.rollback()
            raise
        finally:
            conexion.close()