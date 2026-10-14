from pathlib import Path

from holocontrol.infrastructure.persistence.conexion import BaseDatos


raiz = Path(__file__).resolve().parents[1]

base = BaseDatos(raiz / "data" / "holocontrol.sqlite3")
base.inicializar()

print("Base de datos preparada en:")
print(base.ruta)