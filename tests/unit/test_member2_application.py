import unittest
from dataclasses import replace
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.application.dto.reconocimiento import Reconocimiento
from holocontrol.domain.entities import Calibracion, Mano, Configuracion, AsignacionGesto
from holocontrol.domain.errores import ErrorConflicto, ErrorControl, ErrorDominio, ErrorNoEncontrado
from holocontrol.domain.value_objects.estado_control import EstadoControl
from tests.soporte import RepositorioPerfilesMemoria, EjecutorRegistro, RelojSimulado


class PruebasAplicacion(unittest.TestCase):
    def setUp(self):
        self.repositorio = RepositorioPerfilesMemoria()
        self.ejecutor = EjecutorRegistro()
        self.reloj = RelojSimulado()
        self.aplicacion = AplicacionControl(self.repositorio, self.ejecutor, self.reloj)
        self.perfil = self.aplicacion.crear_perfil("Cesar")

    def iniciar(self):
        self.aplicacion.seleccionar_perfil(self.perfil.id)
        self.aplicacion.calibrar_perfil(Calibracion(self.perfil.id, suavizado=0))
        return self.aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=101, alto_pantalla=101)

    def fotograma(self, gesto="pellizco", **kwargs):
        self.reloj.avanzar()
        return Reconocimiento(**({"generacion": self.aplicacion.estado_actual().generacion,
                              "instante_captura": self.reloj(), "mano_detectada": True,
                              "id_gesto": gesto, "confianza": 0.95} | kwargs))

    def test_crear_perfil_incluye_valores_iniciales(self):
        self.assertEqual(len(self.perfil.asignaciones), 6)
        self.assertIsNone(self.perfil.calibracion)

    def test_nombre_perfil_unico(self):
        with self.assertRaises(ErrorConflicto):
            self.aplicacion.crear_perfil(" cEsAr ")
        self.assertEqual(len(self.aplicacion.listar_perfiles()), 1)

    def test_editar_conserva_identificador(self):
        actualizado = self.aplicacion.editar_perfil(self.perfil.id, nombre="Nuevo")
        self.assertEqual(actualizado.id, self.perfil.id)
        self.assertEqual(self.repositorio.obtener(actualizado.id).nombre, "Nuevo")

    def test_rechaza_nombre_duplicado_al_editar(self):
        otro = self.aplicacion.crear_perfil("Otro")
        with self.assertRaises(ErrorConflicto):
            self.aplicacion.editar_perfil(otro.id, nombre="CESAR")

    def test_perfil_inexistente(self):
        with self.assertRaises(ErrorNoEncontrado):
            self.aplicacion.seleccionar_perfil("no-existe")

    def test_eliminar_exige_confirmacion(self):
        with self.assertRaises(ErrorConflicto):
            self.aplicacion.eliminar_perfil(self.perfil.id)
        self.assertIsNotNone(self.repositorio.obtener(self.perfil.id))

    def test_eliminar_seleccionado_detiene_control(self):
        self.iniciar()
        self.aplicacion.eliminar_perfil(self.perfil.id, confirmado=True)
        self.assertIsNone(self.aplicacion.estado_actual().id_perfil_seleccionado)
        self.assertFalse(self.ejecutor.activo)

    def test_seleccion_carga_configuracion_guardada(self):
        self.aplicacion.calibrar_perfil(Calibracion(self.perfil.id, sensibilidad=2))
        otra_aplicacion = AplicacionControl(self.repositorio, self.ejecutor)
        cargado = otra_aplicacion.seleccionar_perfil(self.perfil.id)
        self.assertEqual(cargado.calibracion.sensibilidad, 2)

    def test_cambiar_perfil_detiene_control(self):
        self.iniciar()
        otro = self.aplicacion.crear_perfil("Otro")
        self.aplicacion.seleccionar_perfil(otro.id)
        self.assertEqual(self.aplicacion.estado_actual().estado, EstadoControl.STOPPED)
        self.assertFalse(self.ejecutor.activo)

    def test_editar_perfil_pausa_control(self):
        self.iniciar()
        self.aplicacion.editar_perfil(self.perfil.id, tiempo_espera_gesto_ms=600)
        self.assertEqual(self.aplicacion.estado_actual().estado, EstadoControl.PAUSED)

    def test_cambiar_mano_invalida_calibracion(self):
        self.iniciar()
        perfil = self.aplicacion.editar_perfil(self.perfil.id, mano_dominante=Mano.IZQUIERDA)
        self.assertIsNone(perfil.calibracion)
        with self.assertRaises(ErrorControl):
            self.aplicacion.reanudar_control(camara_disponible=True)

    def test_configuracion_guardada(self):
        self.aplicacion.cambiar_configuracion(self.perfil.id, Configuracion(tema="oscuro"))
        self.assertEqual(self.repositorio.obtener(self.perfil.id).configuracion.tema, "oscuro")

    def test_fallo_guardado_no_modifica_perfil(self):
        self.repositorio.fallar_guardado = True
        with self.assertRaises(OSError):
            self.aplicacion.editar_perfil(self.perfil.id, nombre="Otro")
        self.assertEqual(self.repositorio.obtener(self.perfil.id).nombre, "Cesar")

    def test_rechaza_gesto_ajeno(self):
        otro = self.aplicacion.crear_perfil("Otro")
        gesto = self.aplicacion.guardar_gesto(otro.id, "Mi gesto")
        with self.assertRaises(ErrorDominio):
            self.aplicacion.configurar_gesto(self.perfil.id, gesto.id, "clic_izquierdo")

    def test_predefinidos_protegidos(self):
        with self.assertRaises(ErrorConflicto):
            self.aplicacion.guardar_gesto(self.perfil.id, "Nuevo", id_gesto="pellizco")
        with self.assertRaises(ErrorConflicto):
            self.aplicacion.eliminar_gesto(self.perfil.id, "pellizco")

    def test_reemplazar_asignacion_exige_confirmacion(self):
        with self.assertRaises(ErrorConflicto):
            self.aplicacion.configurar_gesto(self.perfil.id, "pellizco", "clic_derecho")
        p = self.aplicacion.configurar_gesto(self.perfil.id, "pellizco", "clic_derecho",
                                       reemplazar_existente=True)
        self.assertEqual(next(a for a in p.asignaciones if a.id_gesto == "pellizco").id_accion,
                         "clic_derecho")

    def test_rechaza_accion_desconocida(self):
        with self.assertRaises(ErrorDominio):
            self.aplicacion.configurar_gesto(self.perfil.id, "pellizco", "ejecutar_cmd")

    def test_eliminar_gesto_propio_elimina_asignacion(self):
        gesto = self.aplicacion.guardar_gesto(self.perfil.id, "Mi gesto")
        self.aplicacion.configurar_gesto(self.perfil.id, gesto.id, "clic_izquierdo")
        self.aplicacion.eliminar_gesto(self.perfil.id, gesto.id)
        p = self.repositorio.obtener(self.perfil.id)
        self.assertFalse(p.gestos)
        self.assertNotIn(gesto.id, [a.id_gesto for a in p.asignaciones])

    def test_restaurar_valores_iniciales(self):
        self.aplicacion.configurar_gesto(self.perfil.id, "pellizco", "clic_derecho",
                                    reemplazar_existente=True)
        with self.assertRaises(ErrorConflicto):
            self.aplicacion.restaurar_asignaciones(self.perfil.id)
        p = self.aplicacion.restaurar_asignaciones(self.perfil.id, confirmado=True)
        self.assertEqual(p.asignaciones, self.perfil.asignaciones)

    def test_iniciar_exige_seleccion(self):
        with self.assertRaises(ErrorControl):
            self.aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=100, alto_pantalla=100)

    def test_iniciar_exige_calibracion(self):
        self.aplicacion.seleccionar_perfil(self.perfil.id)
        with self.assertRaises(ErrorControl):
            self.aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=100, alto_pantalla=100)

    def test_iniciar_exige_camara(self):
        self.aplicacion.seleccionar_perfil(self.perfil.id)
        self.aplicacion.calibrar_perfil(Calibracion(self.perfil.id))
        with self.assertRaises(ErrorControl):
            self.aplicacion.iniciar_control(camara_disponible=False, ancho_pantalla=100, alto_pantalla=100)

    def test_gesto_mantenido_hace_un_clic(self):
        self.iniciar()
        self.aplicacion.procesar_reconocimiento(self.fotograma())
        resultado = self.aplicacion.procesar_reconocimiento(self.fotograma())
        self.assertEqual(resultado.motivo, "gesto_mantenido")
        self.assertEqual(self.ejecutor.llamadas, [("clic_izquierdo",)])

    def test_liberar_permite_segundo_clic(self):
        self.iniciar()
        for gesto in ("pellizco", None, "pellizco"):
            self.aplicacion.procesar_reconocimiento(self.fotograma(gesto))
        self.assertEqual(len(self.ejecutor.llamadas), 2)

    def test_confianza_baja_no_rearma_clic_mantenido(self):
        self.iniciar()
        self.aplicacion.procesar_reconocimiento(self.fotograma())
        self.aplicacion.procesar_reconocimiento(self.fotograma(confianza=0.1))
        self.aplicacion.procesar_reconocimiento(self.fotograma())
        self.assertEqual(len(self.ejecutor.llamadas), 1)

    def test_ausencia_mano_bloquea_y_reinicia(self):
        self.iniciar()
        self.assertEqual(self.aplicacion.procesar_reconocimiento(self.fotograma(mano_detectada=False)).motivo,
                         "sin_mano")
        self.assertEqual(self.ejecutor.llamadas, [])
        self.assertFalse(self.aplicacion.estado_actual().mano_detectada)

    def test_confianza_insuficiente_bloquea(self):
        self.iniciar()
        self.assertFalse(self.aplicacion.procesar_reconocimiento(self.fotograma(confianza=0.2)).ejecutado)
        self.assertFalse(self.ejecutor.llamadas)

    def test_pausa_bloquea_y_reanudar_cambia_generacion(self):
        self.iniciar()
        anterior = self.fotograma()
        self.aplicacion.pausar_control()
        self.assertFalse(self.aplicacion.procesar_reconocimiento(anterior).ejecutado)
        self.aplicacion.reanudar_control(camara_disponible=True)
        self.assertEqual(self.aplicacion.procesar_reconocimiento(anterior).motivo, "generacion_anterior")

    def test_detener_bloquea_acciones(self):
        self.iniciar()
        self.aplicacion.detener_control()
        self.assertFalse(self.aplicacion.procesar_reconocimiento(self.fotograma()).ejecutado)

    def test_perdida_camara_pausa(self):
        self.iniciar()
        estado_actual = self.aplicacion.informar_perdida_camara()
        self.assertEqual(estado_actual.estado, EstadoControl.PAUSED)
        self.assertFalse(estado_actual.camara_disponible)
        self.assertFalse(self.ejecutor.activo)

    def test_fotogramas_vencidos_y_futuros(self):
        self.iniciar()
        for delta in (-1, 1):
            self.assertEqual(self.aplicacion.procesar_reconocimiento(
                self.fotograma(instante_captura=self.reloj() + delta)).motivo, "fotograma_vencido")
        self.assertFalse(self.ejecutor.llamadas)

    def test_fotograma_duplicado(self):
        self.iniciar()
        fotograma = self.fotograma()
        self.aplicacion.procesar_reconocimiento(fotograma)
        self.assertEqual(self.aplicacion.procesar_reconocimiento(fotograma).motivo, "fotograma_fuera_de_orden")

    def test_conversion_y_limites_cursor(self):
        self.aplicacion.calibrar_perfil(Calibracion(self.perfil.id, x_min=0.2, x_max=0.8,
                                               y_min=0.2, y_max=0.8, suavizado=0))
        self.aplicacion.seleccionar_perfil(self.perfil.id)
        self.aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=101, alto_pantalla=101)
        self.aplicacion.procesar_reconocimiento(self.fotograma("indice", x=1, y=0))
        self.assertEqual(self.ejecutor.llamadas, [("mover", 100, 0)])

    def test_cursor_continuo_y_suavizado(self):
        self.iniciar()
        self.aplicacion.calibrar_perfil(Calibracion(self.perfil.id, suavizado=1))
        self.aplicacion.reanudar_control(camara_disponible=True)
        self.aplicacion.procesar_reconocimiento(self.fotograma("indice", x=0, y=0))
        self.aplicacion.procesar_reconocimiento(self.fotograma("indice", x=1, y=1))
        self.assertEqual(self.ejecutor.llamadas, [("mover", 0, 0), ("mover", 5, 5)])

    def test_rechaza_coordenadas_ausentes(self):
        self.iniciar()
        self.assertFalse(self.aplicacion.procesar_reconocimiento(self.fotograma("indice")).ejecutado)

    def test_asignacion_desactivada(self):
        self.aplicacion.configurar_gesto(self.perfil.id, "pellizco", "clic_izquierdo", activo=False)
        self.iniciar()
        self.assertEqual(self.aplicacion.procesar_reconocimiento(self.fotograma()).motivo, "sin_asignacion_activa")

    def test_gesto_pausa_funciona(self):
        self.iniciar()
        self.aplicacion.procesar_reconocimiento(self.fotograma("palma"))
        self.assertEqual(self.aplicacion.estado_actual().estado, EstadoControl.PAUSED)

    def test_desplazamiento_y_clic_derecho(self):
        self.iniciar()
        self.aplicacion.procesar_reconocimiento(self.fotograma("dos_dedos"))
        self.aplicacion.procesar_reconocimiento(self.fotograma("subir"))
        self.assertEqual(self.ejecutor.llamadas, [("clic_derecho",), ("desplazar", 3)])

    def test_espera_bloquea_rafaga(self):
        self.iniciar()
        self.aplicacion.editar_perfil(self.perfil.id, tiempo_espera_gesto_ms=2000)
        self.aplicacion.reanudar_control(camara_disponible=True)
        self.aplicacion.procesar_reconocimiento(self.fotograma("pellizco"))
        resultado = self.aplicacion.procesar_reconocimiento(self.fotograma("dos_dedos"))
        self.assertEqual(resultado.motivo, "tiempo_espera")
        self.assertEqual(len(self.ejecutor.llamadas), 1)

    def test_fallo_adaptador_pausa(self):
        self.iniciar()
        self.ejecutor.fallar_accion = True
        with self.assertRaises(ErrorControl):
            self.aplicacion.procesar_reconocimiento(self.fotograma())
        self.assertEqual(self.aplicacion.estado_actual().estado, EstadoControl.PAUSED)
        self.assertFalse(self.ejecutor.activo)
        self.assertIsNotNone(self.aplicacion.estado_actual().error)

    def test_fallo_activacion_no_informa_activo(self):
        self.aplicacion.seleccionar_perfil(self.perfil.id)
        self.aplicacion.calibrar_perfil(Calibracion(self.perfil.id))
        self.ejecutor.fallar_activacion = True
        with self.assertRaises(ErrorControl):
            self.aplicacion.iniciar_control(camara_disponible=True, ancho_pantalla=100, alto_pantalla=100)
        self.assertNotEqual(self.aplicacion.estado_actual().estado, EstadoControl.ACTIVE)

    def test_fallo_detencion_bloquea_aplicacion(self):
        self.iniciar()
        self.ejecutor.fallar_detencion = True
        with self.assertRaises(ErrorControl):
            self.aplicacion.detener_control()
        self.assertFalse(self.aplicacion.procesar_reconocimiento(self.fotograma()).ejecutado)
        self.assertIsNotNone(self.aplicacion.estado_actual().error)

    def test_finalizar_limpia_seleccion(self):
        self.iniciar()
        self.aplicacion.finalizar_sesion()
        self.assertIsNone(self.aplicacion.estado_actual().id_perfil_seleccionado)

    def test_bloquea_configuracion_corrupta(self):
        invalido = replace(self.perfil, asignaciones=(AsignacionGesto(
            self.perfil.id, "gesto_ajeno", "clic_izquierdo"),))
        self.repositorio.guardar(invalido)
        with self.assertRaises(ErrorDominio):
            self.iniciar()
