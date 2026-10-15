import sqlite3
from dataclasses import replace

import pytest

from holocontrol.domain.entities import (
    AsignacionGesto,
    Calibracion,
    Configuracion,
    Gesto,
    Mano,
    Perfil,
)
from holocontrol.domain.errores import ErrorConflicto, ErrorNoEncontrado
from holocontrol.infrastructure.persistence.conexion import BaseDatos
from holocontrol.infrastructure.persistence.repositorio_perfil import (
    RepositorioPerfilesSQLite,
)


# Estas dos funciones preparan datos para no repetirlos en cada prueba.
def preparar_repositorio(tmp_path):
    base = BaseDatos(tmp_path / "prueba.sqlite3")
    base.inicializar()
    return RepositorioPerfilesSQLite(base)


def preparar_perfil():
    gesto = Gesto(
        id="gesto-personal",
        nombre="Mi gesto",
        id_perfil="perfil-1",
    )

    asignacion = AsignacionGesto(
        id_perfil="perfil-1",
        id_gesto="gesto-personal",
        id_accion="clic_izquierdo",
    )

    return Perfil(
        id="perfil-1",
        nombre="Gabriela",
        mano_dominante=Mano.IZQUIERDA,
        configuracion=Configuracion(tema="oscuro"),
        calibracion=Calibracion(
            id_perfil="perfil-1",
            sensibilidad=1.5,
        ),
        gestos=(gesto,),
        asignaciones=(asignacion,),
    )


def test_crear_y_obtener_perfil_completo(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    perfil = preparar_perfil()

    repositorio.crear(perfil)

    # Recuperamos los datos desde otra instancia.
    otra_base = BaseDatos(repositorio.base.ruta)
    otro_repositorio = RepositorioPerfilesSQLite(otra_base)

    recuperado = otro_repositorio.obtener("perfil-1")

    assert recuperado == perfil


def test_crear_perfil_sin_calibracion(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    perfil = Perfil(id="perfil-1", nombre="Gabriela")

    repositorio.crear(perfil)
    recuperado = repositorio.obtener("perfil-1")

    assert recuperado == perfil
    assert recuperado.calibracion is None
    assert recuperado.configuracion.tema == "sistema"


def test_obtener_inexistente(tmp_path):
    repositorio = preparar_repositorio(tmp_path)

    assert repositorio.obtener("no-existe") is None


def test_listar(tmp_path):
    repositorio = preparar_repositorio(tmp_path)

    assert repositorio.listar() == ()

    primero = preparar_perfil()
    segundo = Perfil(id="perfil-2", nombre="Fernando")

    repositorio.crear(primero)
    repositorio.crear(segundo)

    assert repositorio.listar() == (primero, segundo)


def test_rechaza_id_repetido(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    primero = Perfil(id="perfil-1", nombre="Gabriela")
    segundo = Perfil(id="perfil-1", nombre="Fernando")

    repositorio.crear(primero)

    with pytest.raises(ErrorConflicto):
        repositorio.crear(segundo)

    assert repositorio.obtener("perfil-1") == primero


def test_rechaza_nombre_repetido(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    primero = Perfil(id="perfil-1", nombre="Gabriela")
    segundo = Perfil(id="perfil-2", nombre="  GABRIELA  ")

    repositorio.crear(primero)

    with pytest.raises(ErrorConflicto):
        repositorio.crear(segundo)

    assert repositorio.obtener("perfil-2") is None


def test_actualizar_perfil_completo(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    original = preparar_perfil()
    repositorio.crear(original)

    gesto_editado = replace(
        original.gestos[0],
        nombre="Gesto editado",
        umbral_confianza=0.9,
    )

    asignacion_editada = replace(
        original.asignaciones[0],
        id_accion="clic_derecho",
        activo=False,
    )

    # replace crea otro objeto con los cambios indicados.
    modificado = replace(
        original,
        nombre="Gabriela editado",
        mano_dominante=Mano.DERECHA,
        tiempo_espera_gesto_ms=600,
        limite_dictado=300,
        configuracion=Configuracion(
            tema="claro",
            alto_contraste=True,
        ),
        calibracion=Calibracion(
            id_perfil="perfil-1",
            sensibilidad=2.0,
        ),
        gestos=(gesto_editado,),
        asignaciones=(asignacion_editada,),
    )

    repositorio.actualizar(modificado)

    assert repositorio.obtener("perfil-1") == modificado


def test_actualizar_retira_relaciones(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    original = preparar_perfil()
    repositorio.crear(original)

    modificado = replace(
        original,
        calibracion=None,
        gestos=(),
        asignaciones=(),
    )

    repositorio.actualizar(modificado)

    assert repositorio.obtener("perfil-1") == modificado

    with repositorio.base.transaccion() as conexion:
        gesto = conexion.execute(
            "SELECT * FROM Gesto WHERE id_gesto = ?",
            ("gesto-personal",),
        ).fetchone()

    assert gesto is None


def test_actualizar_conserva_muestras(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    original = preparar_perfil()
    repositorio.crear(original)

    with repositorio.base.transaccion() as conexion:
        conexion.execute(
            """
            INSERT INTO MuestraGesto (id_muestra, id_gesto)
            VALUES (?, ?)
            """,
            (1, "gesto-personal"),
        )

    gesto_editado = replace(
        original.gestos[0],
        nombre="Gesto editado",
    )
    modificado = replace(original, gestos=(gesto_editado,))

    repositorio.actualizar(modificado)

    with repositorio.base.transaccion() as conexion:
        muestra = conexion.execute(
            "SELECT * FROM MuestraGesto WHERE id_muestra = 1"
        ).fetchone()

    assert muestra is not None
    assert repositorio.obtener("perfil-1") == modificado


def test_actualizar_rechaza_nombre_repetido(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    primero = Perfil(id="perfil-1", nombre="Gabriela")
    segundo = Perfil(id="perfil-2", nombre="Fernando")

    repositorio.crear(primero)
    repositorio.crear(segundo)

    modificado = replace(segundo, nombre="GABRIELA")

    with pytest.raises(ErrorConflicto):
        repositorio.actualizar(modificado)

    assert repositorio.obtener("perfil-2") == segundo


def test_creacion_fallida_no_guarda_nada(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    perfil = preparar_perfil()

    asignacion_invalida = replace(
        perfil.asignaciones[0],
        id_accion="accion-inexistente",
    )
    perfil_invalido = replace(
        perfil,
        asignaciones=(asignacion_invalida,),
    )

    with pytest.raises(sqlite3.IntegrityError):
        repositorio.crear(perfil_invalido)

    assert repositorio.obtener("perfil-1") is None

    with repositorio.base.transaccion() as conexion:
        configuracion = conexion.execute(
            "SELECT * FROM Configuracion WHERE id_perfil = ?",
            ("perfil-1",),
        ).fetchone()

        calibracion = conexion.execute(
            "SELECT * FROM Calibracion WHERE id_perfil = ?",
            ("perfil-1",),
        ).fetchone()

        gesto = conexion.execute(
            "SELECT * FROM Gesto WHERE id_gesto = ?",
            ("gesto-personal",),
        ).fetchone()

    assert configuracion is None
    assert calibracion is None
    assert gesto is None


def test_actualizacion_fallida_conserva_datos(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    original = preparar_perfil()
    repositorio.crear(original)

    asignacion_invalida = AsignacionGesto(
        id_perfil="perfil-1",
        id_gesto="palma_abierta",
        id_accion="accion-inexistente",
    )

    modificado = replace(
        original,
        nombre="Cambio que debe deshacerse",
        configuracion=Configuracion(tema="claro"),
        calibracion=None,
        gestos=(),
        asignaciones=(asignacion_invalida,),
    )

    with pytest.raises(sqlite3.IntegrityError):
        repositorio.actualizar(modificado)

    assert repositorio.obtener("perfil-1") == original


def test_eliminar_perfil_y_dependientes(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    perfil = preparar_perfil()
    repositorio.crear(perfil)

    repositorio.eliminar("perfil-1")

    assert repositorio.obtener("perfil-1") is None

    with repositorio.base.transaccion() as conexion:
        configuracion = conexion.execute(
            "SELECT * FROM Configuracion WHERE id_perfil = ?",
            ("perfil-1",),
        ).fetchone()

        calibracion = conexion.execute(
            "SELECT * FROM Calibracion WHERE id_perfil = ?",
            ("perfil-1",),
        ).fetchone()

        gesto_personal = conexion.execute(
            "SELECT * FROM Gesto WHERE id_gesto = ?",
            ("gesto-personal",),
        ).fetchone()

        asignacion = conexion.execute(
            "SELECT * FROM AsignacionGesto WHERE id_perfil = ?",
            ("perfil-1",),
        ).fetchone()

        gesto_compartido = conexion.execute(
            "SELECT * FROM Gesto WHERE id_gesto = ?",
            ("palma_abierta",),
        ).fetchone()

    assert configuracion is None
    assert calibracion is None
    assert gesto_personal is None
    assert asignacion is None
    assert gesto_compartido is not None


def test_actualizar_inexistente(tmp_path):
    repositorio = preparar_repositorio(tmp_path)
    perfil = Perfil(id="no-existe", nombre="Gabriela")

    with pytest.raises(ErrorNoEncontrado):
        repositorio.actualizar(perfil)


def test_eliminar_inexistente(tmp_path):
    repositorio = preparar_repositorio(tmp_path)

    with pytest.raises(ErrorNoEncontrado):
        repositorio.eliminar("no-existe")
