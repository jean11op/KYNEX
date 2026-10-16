import importlib.util
from pathlib import Path
import sqlite3


def test_repair_only_disabled_right_fist_and_keep_backup(tmp_path):
    path = Path(__file__).parents[2] / 'scripts/reparar_puno_derecho.py'
    spec = importlib.util.spec_from_file_location('repair', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    database, backup = tmp_path / 'profiles.sqlite3', tmp_path / 'backup.sqlite3'
    with sqlite3.connect(database) as c:
        c.execute('CREATE TABLE Perfil (id_perfil TEXT, mano_dominante TEXT)')
        c.execute('CREATE TABLE AsignacionGesto (id_perfil TEXT, id_gesto TEXT, id_accion TEXT, activo INTEGER)')
        c.executemany('INSERT INTO Perfil VALUES (?,?)', [('r', 'derecha'), ('l', 'izquierda')])
        original = [('r', 'puno', 'cursor', 0), ('r', 'indice', 'cursor', 1),
                    ('l', 'puno', 'minimizar', 1)]
        c.executemany('INSERT INTO AsignacionGesto VALUES (?,?,?,?)', original)
    assert module.reparar(database, backup) == 1
    with sqlite3.connect(backup) as c:
        assert c.execute('SELECT * FROM AsignacionGesto').fetchall() == original
    with sqlite3.connect(database) as c:
        assert c.execute('SELECT * FROM AsignacionGesto').fetchall() == [
            ('r', 'puno', 'minimizar', 1), *original[1:]]
    assert module.reparar(database, backup) == 0
