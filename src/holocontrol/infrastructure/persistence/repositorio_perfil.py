from holocontrol.domain.entities import (
    Perfil,
    Mano,
    Configuracion,
    Calibracion,
    Gesto,
    AsignacionGesto,
)
from holocontrol.domain.errores import ErrorConflicto, ErrorNoEncontrado
from holocontrol.infrastructure.persistence.conexion import BaseDatos


class RepositorioPerfilesSQLite:
    def __init__(self, base: BaseDatos):
        self.base = base

    # 1. CREAR
    def crear(self, perfil: Perfil) -> None:
        with self.base.transaccion() as conexion:
            existente = conexion.execute(
                "SELECT id_perfil FROM Perfil WHERE id_perfil = ?",
                (perfil.id,),
            ).fetchone()

            if existente is not None:
                raise ErrorConflicto(
                    "Ya existe un perfil con ese identificador."
                )

            self._comprobar_nombre(conexion, perfil)

            conexion.execute(
                """
                INSERT INTO Perfil (
                    id_perfil, nombre, mano_dominante,
                    tiempo_espera_gesto_ms, limite_dictado
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    perfil.id,
                    perfil.nombre,
                    perfil.mano_dominante.value,
                    perfil.tiempo_espera_gesto_ms,
                    perfil.limite_dictado,
                ),
            )

            self._guardar_relaciones(conexion, perfil)

    # 2. OBTENER
    def obtener(self, id_perfil: str) -> Perfil | None:
        with self.base.transaccion() as conexion:
            return self._leer_perfil(conexion, id_perfil)

    # 3. LISTAR
    def listar(self) -> tuple[Perfil, ...]:
        with self.base.transaccion() as conexion:
            filas = conexion.execute(
                "SELECT id_perfil FROM Perfil ORDER BY id_perfil"
            ).fetchall()

            perfiles = []

            for fila in filas:
                perfil = self._leer_perfil(conexion, fila["id_perfil"])
                perfiles.append(perfil)

            return tuple(perfiles)

    # 4. ACTUALIZAR
    def actualizar(self, perfil: Perfil) -> None:
        with self.base.transaccion() as conexion:
            existente = conexion.execute(
                "SELECT id_perfil FROM Perfil WHERE id_perfil = ?",
                (perfil.id,),
            ).fetchone()

            if existente is None:
                raise ErrorNoEncontrado("El perfil no existe.")

            self._comprobar_nombre(conexion, perfil)

            conexion.execute(
                """
                UPDATE Perfil
                SET nombre = ?,
                    mano_dominante = ?,
                    tiempo_espera_gesto_ms = ?,
                    limite_dictado = ?
                WHERE id_perfil = ?
                """,
                (
                    perfil.nombre,
                    perfil.mano_dominante.value,
                    perfil.tiempo_espera_gesto_ms,
                    perfil.limite_dictado,
                    perfil.id,
                ),
            )

            self._guardar_relaciones(conexion, perfil)

    # 5. ELIMINAR
    def eliminar(self, id_perfil: str) -> None:
        with self.base.transaccion() as conexion:
            resultado = conexion.execute(
                "DELETE FROM Perfil WHERE id_perfil = ?",
                (id_perfil,),
            )

            if resultado.rowcount == 0:
                raise ErrorNoEncontrado("El perfil no existe.")

    # AUXILIAR: comprobar nombres repetidos.
    def _comprobar_nombre(self, conexion, perfil: Perfil) -> None:
        filas = conexion.execute(
            "SELECT nombre FROM Perfil WHERE id_perfil <> ?",
            (perfil.id,),
        ).fetchall()

        nombre_nuevo = perfil.nombre.strip().casefold()

        for fila in filas:
            nombre_existente = fila["nombre"].strip().casefold()

            if nombre_existente == nombre_nuevo:
                raise ErrorConflicto(
                    "Ya existe un perfil con ese nombre."
                )

    # AUXILIAR: guardar todos los datos relacionados.
    def _guardar_relaciones(self, conexion, perfil: Perfil) -> None:
        configuracion = perfil.configuracion

        conexion.execute(
            """
            INSERT INTO Configuracion (
                id_perfil, indice_camara, tema, escala_interfaz,
                alto_contraste, minimizar_bandeja,
                mostrar_avisos, atajo_pausa
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_perfil) DO UPDATE SET
                indice_camara = excluded.indice_camara,
                tema = excluded.tema,
                escala_interfaz = excluded.escala_interfaz,
                alto_contraste = excluded.alto_contraste,
                minimizar_bandeja = excluded.minimizar_bandeja,
                mostrar_avisos = excluded.mostrar_avisos,
                atajo_pausa = excluded.atajo_pausa
            """,
            (
                perfil.id,
                configuracion.indice_camara,
                configuracion.tema,
                configuracion.escala_interfaz,
                configuracion.alto_contraste,
                configuracion.minimizar_bandeja,
                configuracion.mostrar_avisos,
                configuracion.atajo_pausa,
            ),
        )

        if perfil.calibracion is None:
            conexion.execute(
                "DELETE FROM Calibracion WHERE id_perfil = ?",
                (perfil.id,),
            )
        else:
            calibracion = perfil.calibracion

            conexion.execute(
                """
                INSERT INTO Calibracion (
                    id_perfil, x_min, x_max, y_min, y_max,
                    sensibilidad, suavizado
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id_perfil) DO UPDATE SET
                    x_min = excluded.x_min,
                    x_max = excluded.x_max,
                    y_min = excluded.y_min,
                    y_max = excluded.y_max,
                    sensibilidad = excluded.sensibilidad,
                    suavizado = excluded.suavizado
                """,
                (
                    perfil.id,
                    calibracion.x_min,
                    calibracion.x_max,
                    calibracion.y_min,
                    calibracion.y_max,
                    calibracion.sensibilidad,
                    calibracion.suavizado,
                ),
            )

        # Sustituimos las asignaciones por las recibidas.
        conexion.execute(
            "DELETE FROM AsignacionGesto WHERE id_perfil = ?",
            (perfil.id,),
        )

        ids_gestos = set()

        for gesto in perfil.gestos:
            ids_gestos.add(gesto.id)

        existentes = conexion.execute(
            "SELECT id_gesto FROM Gesto WHERE id_perfil = ?",
            (perfil.id,),
        ).fetchall()

        # Eliminamos solo los gestos retirados del perfil.
        for fila in existentes:
            if fila["id_gesto"] not in ids_gestos:
                conexion.execute(
                    "DELETE FROM Gesto WHERE id_gesto = ?",
                    (fila["id_gesto"],),
                )

        for gesto in perfil.gestos:
            existente = conexion.execute(
                "SELECT id_perfil FROM Gesto WHERE id_gesto = ?",
                (gesto.id,),
            ).fetchone()

            if existente is None:
                conexion.execute(
                    """
                    INSERT INTO Gesto (
                        id_gesto, id_perfil, nombre, umbral_confianza
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        gesto.id,
                        gesto.id_perfil,
                        gesto.nombre,
                        gesto.umbral_confianza,
                    ),
                )
            else:
                if existente["id_perfil"] != perfil.id:
                    raise ErrorConflicto(
                        "El identificador del gesto ya está ocupado."
                    )

                # Actualizar conserva las muestras del gesto.
                conexion.execute(
                    """
                    UPDATE Gesto
                    SET nombre = ?, umbral_confianza = ?
                    WHERE id_gesto = ?
                    """,
                    (
                        gesto.nombre,
                        gesto.umbral_confianza,
                        gesto.id,
                    ),
                )

        for asignacion in perfil.asignaciones:
            conexion.execute(
                """
                INSERT INTO AsignacionGesto (
                    id_perfil, id_gesto, id_accion, activo
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    asignacion.id_perfil,
                    asignacion.id_gesto,
                    asignacion.id_accion,
                    asignacion.activo,
                ),
            )

    # AUXILIAR: convertir los registros en un objeto Perfil.
    def _leer_perfil(self, conexion, id_perfil: str) -> Perfil | None:
        datos = conexion.execute(
            "SELECT * FROM Perfil WHERE id_perfil = ?",
            (id_perfil,),
        ).fetchone()

        if datos is None:
            return None

        fila_configuracion = conexion.execute(
            "SELECT * FROM Configuracion WHERE id_perfil = ?",
            (id_perfil,),
        ).fetchone()

        if fila_configuracion is None:
            raise ValueError(
                "El perfil guardado no tiene configuración."
            )

        configuracion = Configuracion(
            indice_camara=fila_configuracion["indice_camara"],
            tema=fila_configuracion["tema"],
            escala_interfaz=fila_configuracion["escala_interfaz"],
            alto_contraste=bool(fila_configuracion["alto_contraste"]),
            minimizar_bandeja=bool(fila_configuracion["minimizar_bandeja"]),
            mostrar_avisos=bool(fila_configuracion["mostrar_avisos"]),
            atajo_pausa=fila_configuracion["atajo_pausa"],
        )

        fila_calibracion = conexion.execute(
            "SELECT * FROM Calibracion WHERE id_perfil = ?",
            (id_perfil,),
        ).fetchone()

        calibracion = None

        if fila_calibracion is not None:
            calibracion = Calibracion(
                id_perfil=id_perfil,
                x_min=fila_calibracion["x_min"],
                x_max=fila_calibracion["x_max"],
                y_min=fila_calibracion["y_min"],
                y_max=fila_calibracion["y_max"],
                sensibilidad=fila_calibracion["sensibilidad"],
                suavizado=fila_calibracion["suavizado"],
            )

        filas_gestos = conexion.execute(
            """
            SELECT * FROM Gesto
            WHERE id_perfil = ?
            ORDER BY rowid
            """,
            (id_perfil,),
        ).fetchall()

        gestos = []

        for fila in filas_gestos:
            gesto = Gesto(
                id=fila["id_gesto"],
                nombre=fila["nombre"],
                id_perfil=fila["id_perfil"],
                umbral_confianza=fila["umbral_confianza"],
            )
            gestos.append(gesto)

        filas_asignaciones = conexion.execute(
            """
            SELECT * FROM AsignacionGesto
            WHERE id_perfil = ?
            ORDER BY rowid
            """,
            (id_perfil,),
        ).fetchall()

        asignaciones = []

        for fila in filas_asignaciones:
            asignacion = AsignacionGesto(
                id_perfil=fila["id_perfil"],
                id_gesto=fila["id_gesto"],
                id_accion=fila["id_accion"],
                activo=bool(fila["activo"]),
            )
            asignaciones.append(asignacion)

        return Perfil(
            id=datos["id_perfil"],
            nombre=datos["nombre"],
            mano_dominante=Mano(datos["mano_dominante"]),
            tiempo_espera_gesto_ms=datos["tiempo_espera_gesto_ms"],
            limite_dictado=datos["limite_dictado"],
            configuracion=configuracion,
            calibracion=calibracion,
            gestos=tuple(gestos),
            asignaciones=tuple(asignaciones),
        )