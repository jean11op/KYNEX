"""Repara la asignación desactivada del puño derecho, con respaldo previo."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3


def reparar(database: Path, backup: Path) -> int:
    if database.resolve() == backup.resolve():
        raise ValueError("El respaldo debe ser distinto de la base original.")
    # mode=rw evita crear una base vacía si la ruta es incorrecta.
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=rw', uri=True)) as connection:
        affected = connection.execute(
            "SELECT a.id_perfil FROM AsignacionGesto a JOIN Perfil p "
            "ON p.id_perfil=a.id_perfil WHERE p.mano_dominante='derecha' "
            "AND a.id_gesto='puno' AND a.id_accion='cursor' AND a.activo=0"
        ).fetchall()
        if not affected:
            return 0
        # Nunca sobrescribir un respaldo anterior.
        with backup.open('xb'):
            pass
        with closing(sqlite3.connect(backup)) as destination:
            connection.backup(destination)
        with connection:
            count = 0
            for (profile_id,) in affected:
                count += connection.execute(
                    "UPDATE AsignacionGesto SET id_accion='minimizar', activo=1 "
                    "WHERE id_perfil=? AND id_gesto='puno' "
                    "AND id_accion='cursor' AND activo=0", (profile_id,)
                ).rowcount
        return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    print(f'Asignaciones reparadas: {reparar(args.database, args.backup)}')
