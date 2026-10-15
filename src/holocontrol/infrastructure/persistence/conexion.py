import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from holocontrol.infrastructure.persistence.errores import ErrorPersistencia


class BaseDatos:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta).expanduser().resolve()

    def inicializar(self) -> None:
        """Crea las tablas y carga los catálogos."""
        carpeta = Path(__file__).parent

        try:
            esquema = (carpeta / "esquema.sql").read_text(
                encoding="utf-8"
            )
            catalogos = (carpeta / "catalogos.sql").read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as error:
            raise ErrorPersistencia(
                "No se pudieron leer los archivos SQL de inicialización."
            ) from error

        conexion = self.conectar()

        try:
            tabla = conexion.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'TipoAccion'"
            ).fetchone()
            migracion = ""
            if tabla and "'minimizar'" not in tabla[0]:
                # Rebuild the constrained catalog atomically, preserving FK targets.
                definicion = esquema.split("CREATE TABLE IF NOT EXISTS TipoAccion (")[1].split(";", 1)[0]
                migracion = (
                    "CREATE TABLE TipoAccionNueva (" + definicion + ";\n"
                    "INSERT INTO TipoAccionNueva SELECT * FROM TipoAccion;\n"
                    "DROP TABLE TipoAccion;\n"
                    "ALTER TABLE TipoAccionNueva RENAME TO TipoAccion;\n"
                )
            conexion.execute("PRAGMA foreign_keys = OFF")
            conexion.executescript(
                "BEGIN;\n" + migracion + esquema + "\n" + catalogos
            )
            if conexion.execute("PRAGMA foreign_key_check").fetchone():
                raise sqlite3.IntegrityError("Referencias inválidas al migrar los catálogos.")
            conexion.commit()
        except sqlite3.IntegrityError:
            self._revertir(conexion)
            raise
        except sqlite3.Error as error:
            self._revertir(conexion)
            raise ErrorPersistencia(
                "No se pudo inicializar la base de datos."
            ) from error
        except BaseException:
            self._revertir(conexion)
            raise
        finally:
            conexion.close()

    def conectar(self) -> sqlite3.Connection:
        """Abre una conexión con las claves foráneas activadas."""
        conexion = None

        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)

            conexion = sqlite3.connect(
                self.ruta,
                timeout=5.0,
                isolation_level=None,
            )

            conexion.row_factory = sqlite3.Row
            conexion.execute("PRAGMA foreign_keys = ON")

            return conexion
        except (OSError, sqlite3.Error) as error:
            if conexion is not None:
                conexion.close()

            raise ErrorPersistencia(
                f"No se pudo abrir la base de datos: {self.ruta}"
            ) from error

    @contextmanager
    def transaccion(self) -> Iterator[sqlite3.Connection]:
        """Confirma los cambios o los deshace cuando falla la operación."""
        conexion = self.conectar()

        try:
            conexion.execute("BEGIN IMMEDIATE")
            yield conexion
            conexion.commit()

        except sqlite3.IntegrityError:
            self._revertir(conexion)
            raise

        except sqlite3.Error as error:
            self._revertir(conexion)
            raise ErrorPersistencia(
                "No se pudo completar la operación en la base de datos."
            ) from error

        except BaseException:
            self._revertir(conexion)
            raise

        finally:
            conexion.close()

    def _revertir(self, conexion: sqlite3.Connection) -> None:
        """Intenta deshacer cambios sin ocultar el error original."""
        try:
            conexion.rollback()
        except sqlite3.Error:
            pass
