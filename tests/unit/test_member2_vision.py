import unittest
from dataclasses import replace
from unittest.mock import Mock

from holocontrol.application.dto.reconocimiento import Reconocimiento
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Calibracion
from holocontrol.domain.errores import ErrorDominio
from holocontrol.domain.rules.catalogo import GESTOS
from holocontrol.domain.value_objects.estado_control import EstadoControl
from holocontrol.ports.vision.models import (
    EstadoVision,
    EventoGesto,
    FaseGesto,
    GestoBasico,
    Lateralidad,
    ManoDetectada,
    PuntoMano,
    ResultadoVision,
)
from tests.soporte import EjecutorRegistro, RelojSimulado, RepositorioPerfilesMemoria


class PruebasIntegracionVision(unittest.TestCase):
    def setUp(self):
        self.reloj = RelojSimulado()
        self.ejecutor = EjecutorRegistro()
        self.app = AplicacionControl(RepositorioPerfilesMemoria(), self.ejecutor, self.reloj)
        self.perfil = self.app.crear_perfil("Visión", tiempo_espera_gesto_ms=1)
        self.app.seleccionar_perfil(self.perfil.id)
        self.app.calibrar_perfil(Calibracion(self.perfil.id, suavizado=0))
        self.app.iniciar_control(camara_disponible=True, ancho_pantalla=101, alto_pantalla=101)
        self.reloj.avanzar(0.1)

    def evento(self, nombre="pellizco", fase=FaseGesto.INICIO, delta_ms=0, confianza=0.99):
        return EventoGesto(nombre, fase, round(self.reloj() * 1000) + delta_ms, 0, confianza)

    def enviar(self, *eventos, **kwargs):
        return self.app.procesar_reconocimiento(Reconocimiento(
            **({"generacion": self.app.estado_actual().generacion,
                "instante_captura": self.reloj(), "mano_detectada": True,
                "estado_vision": EstadoVision.MANO_DETECTADA, "eventos": eventos} | kwargs)))

    def test_lote_inicio_fin_inicio_respeta_tiempos_y_orden(self):
        resultado = self.enviar(self.evento(delta_ms=-80),
                               self.evento(fase=FaseGesto.FIN, delta_ms=-50),
                               self.evento(delta_ms=-20))
        self.assertEqual(self.ejecutor.llamadas, [("clic_izquierdo",)] * 2)
        self.assertEqual([r.motivo for r in resultado.resultados_eventos],
                         ["accion_enviada", "fin_gesto", "accion_enviada"])

    def test_cooldown_usa_tiempo_del_evento(self):
        self.app.editar_perfil(self.perfil.id, tiempo_espera_gesto_ms=400)
        self.app.reanudar_control(camara_disponible=True)
        self.reloj.avanzar(0.1)
        resultado = self.enviar(self.evento(delta_ms=-80),
                               self.evento(fase=FaseGesto.FIN, delta_ms=-50),
                               self.evento(delta_ms=-20))
        self.assertEqual(resultado.resultados_eventos[-1].motivo, "tiempo_espera")
        self.assertEqual(self.ejecutor.llamadas, [("clic_izquierdo",)])

    def test_mantenimiento_y_lote_vacio_no_rearman_clic(self):
        self.enviar(self.evento())
        self.reloj.avanzar(0.01)
        self.enviar()
        self.reloj.avanzar(0.01)
        self.enviar(self.evento(fase=FaseGesto.MANTENIMIENTO))
        self.reloj.avanzar(0.01)
        self.enviar(self.evento())
        self.assertEqual(self.ejecutor.llamadas, [("clic_izquierdo",)])

    def test_eventos_simultaneos_distintos_y_duplicado(self):
        inicio = self.evento()
        resultado = self.enviar(inicio, self.evento("indice"), inicio, x=0.4, y=0.6)
        self.assertEqual(self.ejecutor.llamadas, [("clic_izquierdo",), ("mover", 33, 75)])
        self.assertEqual(resultado.resultados_eventos[-1].motivo, "evento_duplicado")
        self.reloj.avanzar(0.01)
        self.assertEqual(self.enviar(inicio).motivo, "evento_duplicado")

    def test_evento_fuera_de_orden_no_rearma(self):
        self.enviar(self.evento())
        self.reloj.avanzar(0.01)
        resultado = self.enviar(self.evento(fase=FaseGesto.FIN, delta_ms=-20), self.evento())
        self.assertEqual(resultado.resultados_eventos[0].motivo, "evento_fuera_de_orden")
        self.assertEqual(len(self.ejecutor.llamadas), 1)

    def test_evento_vencido_o_futuro_no_ejecuta(self):
        self.reloj.avanzar(1)
        resultado = self.enviar(self.evento(delta_ms=-300), self.evento(delta_ms=1))
        self.assertEqual([r.motivo for r in resultado.resultados_eventos],
                         ["evento_vencido", "evento_futuro"])
        self.assertFalse(self.ejecutor.llamadas)

    def test_generacion_anterior_no_pausa_nueva_sesion(self):
        anterior = self.app.estado_actual().generacion
        self.app.pausar_control()
        self.app.reanudar_control(camara_disponible=True)
        resultado = self.enviar(generacion=anterior, estado_vision=EstadoVision.ERROR_CAMARA)
        self.assertEqual(resultado.motivo, "generacion_anterior")
        self.assertEqual(self.app.estado_actual().estado, EstadoControl.ACTIVE)

    def test_evento_anterior_a_sesion_no_se_reetiqueta(self):
        antiguo = self.evento()
        self.app.pausar_control()
        self.reloj.avanzar(0.01)
        self.app.reanudar_control(camara_disponible=True)
        self.reloj.avanzar(0.01)
        self.assertEqual(self.enviar(antiguo).motivo, "evento_fuera_de_orden")
        self.assertFalse(self.ejecutor.llamadas)

    def test_scroll_continuo_signo_y_fracciones(self):
        for fase in (FaseGesto.INICIO, FaseGesto.MANTENIMIENTO):
            self.enviar(self.evento("dos_dedos", fase), desplazamiento_vertical=0.02)
            self.reloj.avanzar(0.01)
        self.assertEqual(self.ejecutor.llamadas, [("desplazar", -1)])
        self.enviar(self.evento("dos_dedos", FaseGesto.MANTENIMIENTO),
                    desplazamiento_vertical=-0.1)
        self.assertEqual(self.ejecutor.llamadas[-1], ("desplazar", 2))

    def test_delta_scroll_se_aplica_una_vez_por_lote(self):
        self.enviar(self.evento("dos_dedos", delta_ms=-10),
                    self.evento("dos_dedos", FaseGesto.MANTENIMIENTO),
                    desplazamiento_vertical=0.1)
        self.assertEqual(self.ejecutor.llamadas, [("desplazar", -3)])

    def test_scroll_cero_no_produce_accion(self):
        self.assertEqual(self.enviar(self.evento("dos_dedos")).motivo, "sin_desplazamiento")
        self.assertFalse(self.ejecutor.llamadas)

    def test_pausa_en_lote_bloquea_los_eventos_siguientes(self):
        resultado = self.enviar(self.evento("palma_abierta", delta_ms=-1), self.evento())
        self.assertEqual(resultado.resultados_eventos[-1].motivo, "control_inactivo")
        self.assertFalse(self.ejecutor.llamadas)
        self.assertEqual(self.app.estado_actual().estado, EstadoControl.PAUSED)

    def test_perdida_y_baja_confianza_bloquean_aunque_dto_indique_mano(self):
        for estado in (EstadoVision.SIN_MANO, EstadoVision.MANO_PERDIDA,
                       EstadoVision.BAJA_CONFIANZA, EstadoVision.MANO_NO_SELECCIONADA):
            self.assertEqual(self.enviar(self.evento(), estado_vision=estado).motivo, "sin_mano")
            self.assertTrue(self.app.estado_actual().camara_disponible)
            self.assertFalse(self.ejecutor.mano)
            self.reloj.avanzar(0.01)
        self.assertFalse(self.ejecutor.llamadas)

    def test_errores_y_detencion_pausan_y_exigen_reanudacion(self):
        for estado in (EstadoVision.ERROR_CAMARA, EstadoVision.ERROR_PROCESAMIENTO,
                       EstadoVision.DETENIDO):
            self.enviar(self.evento(), estado_vision=estado, mensaje="Detalle del proveedor")
            actual = self.app.estado_actual()
            self.assertEqual(actual.estado, EstadoControl.PAUSED)
            self.assertEqual(actual.error, "Detalle del proveedor")
            self.assertFalse(actual.camara_disponible)
            self.assertFalse(self.ejecutor.activo)
            self.app.reanudar_control(camara_disponible=True)
            self.reloj.avanzar(0.01)
        self.assertFalse(self.ejecutor.llamadas)

    def test_error_retrasado_tambien_bloquea(self):
        captura = self.reloj()
        self.reloj.avanzar(1)
        self.enviar(instante_captura=captura, estado_vision=EstadoVision.ERROR_CAMARA)
        self.assertEqual(self.app.estado_actual().estado, EstadoControl.PAUSED)

    def test_proveedor_excepcion_y_ausencia_de_resultado(self):
        proveedor = Mock()
        generacion = self.app.estado_actual().generacion
        proveedor.obtener_resultado.return_value = None
        self.assertEqual(self.app.consultar_vision(proveedor, generacion=generacion).motivo,
                         "sin_resultado")
        proveedor.obtener_resultado.side_effect = OSError("Cámara desconectada")
        self.assertEqual(self.app.consultar_vision(proveedor, generacion=generacion).motivo,
                         "error_proveedor")
        self.assertIn("Cámara desconectada", self.app.estado_actual().error)
        self.assertFalse(self.app.estado_actual().camara_disponible)

    def test_consulta_que_termina_tras_reanudacion_se_descarta(self):
        generacion = self.app.estado_actual().generacion

        def consulta():
            self.app.pausar_control()
            self.app.reanudar_control(camara_disponible=True)
            return ResultadoVision(round(self.reloj() * 1000), EstadoVision.ERROR_CAMARA)

        proveedor = Mock(obtener_resultado=Mock(side_effect=consulta))
        self.assertEqual(self.app.consultar_vision(proveedor, generacion=generacion).motivo,
                         "generacion_anterior")
        self.assertEqual(self.app.estado_actual().estado, EstadoControl.ACTIVE)

    def test_conversion_y_consumo_del_contrato_real(self):
        mano = ManoDetectada(tuple(PuntoMano(i, 0.5, 0.5, 0) for i in range(21)),
                             Lateralidad.DERECHA, 0.99)
        vision = ResultadoVision(round(self.reloj() * 1000), EstadoVision.MANO_DETECTADA,
                                 mano, (0.2, 0.7), (0, 0.1), (self.evento("indice"),))
        dato = Reconocimiento.desde_vision(vision, self.app.estado_actual().generacion)
        self.assertEqual((dato.x, dato.y, dato.desplazamiento_vertical), (0.5, 0.5, 0.1))
        self.assertEqual(dato.eventos, vision.eventos)
        self.app.consultar_vision(Mock(obtener_resultado=Mock(return_value=vision)),
                                 generacion=dato.generacion)
        self.assertEqual(self.ejecutor.llamadas, [("mover", 50, 58)])

    def test_coordenada_cruda_y_suavizado_unico_del_dominio(self):
        self.app.calibrar_perfil(Calibracion(self.perfil.id, suavizado=0.5))
        self.app.reanudar_control(camara_disponible=True)
        self.reloj.avanzar(0.1)
        generacion = self.app.estado_actual().generacion

        def consultar(cruda, suavizada, fase):
            instante_ms = int(self.reloj() * 1000)
            mano = ManoDetectada(
                tuple(PuntoMano(i, cruda, cruda, 0) for i in range(21)),
                Lateralidad.DERECHA,
                0.99,
            )
            resultado = ResultadoVision(
                instante_ms,
                EstadoVision.MANO_DETECTADA,
                mano,
                (suavizada, suavizada),
                (0, 0),
                (EventoGesto("indice", fase, instante_ms, 0, 0.99),),
            )
            return self.app.consultar_vision(
                Mock(obtener_resultado=Mock(return_value=resultado)),
                generacion=generacion,
            )

        primero = consultar(0, 0, FaseGesto.INICIO)
        self.reloj.avanzar(0.01)
        segundo = consultar(1, 0.35, FaseGesto.MANTENIMIENTO)

        # La entrada de visión filtrada es 0.35; el DTO entrega el punto crudo (1)
        # y el dominio llega al borde sin que el suavizado impida alcanzarlo.
        self.assertTrue(primero.ejecutado, primero)
        self.assertTrue(segundo.ejecutado, segundo)
        self.assertEqual(self.ejecutor.llamadas, [("mover", 0, 0), ("mover", 100, 100)])

    def test_nombre_personalizado_resuelve_asignacion_del_perfil(self):
        gesto = self.app.guardar_gesto(self.perfil.id, "Mi postura")
        self.app.configurar_gesto(self.perfil.id, gesto.id, "clic_derecho")
        self.app.reanudar_control(camara_disponible=True)
        self.reloj.avanzar(0.01)
        self.enviar(self.evento("personalizado:MI POSTURA"))
        self.assertEqual(self.ejecutor.llamadas, [("clic_derecho",)])

    def test_catalogo_cubre_vision_y_no_inventa_acciones(self):
        self.assertTrue({g.value for g in GestoBasico} <= {g.id for g in GESTOS})
        self.enviar(self.evento("puno"), self.evento("deslizamiento_izquierda"))
        self.assertEqual(self.ejecutor.llamadas, [("minimizar",)])

    def test_confianza_baja_y_asignacion_inactiva_bloquean_eventos(self):
        self.enviar(self.evento(confianza=0.1))
        self.app.configurar_gesto(self.perfil.id, "pellizco", "clic_izquierdo", activo=False)
        self.app.reanudar_control(camara_disponible=True)
        self.reloj.avanzar(0.01)
        self.assertEqual(self.enviar(self.evento()).motivo, "sin_asignacion_activa")
        self.assertFalse(self.ejecutor.llamadas)

    def test_dto_rechaza_datos_invalidos(self):
        valido = Reconocimiento(1, 100, True)
        for cambios in ({"eventos": ("pellizco",)}, {"estado_vision": "error"},
                        {"desplazamiento_vertical": float("nan")},
                        {"desplazamiento_vertical": 1.1}):
            with self.subTest(cambios=cambios), self.assertRaises(ErrorDominio):
                replace(valido, **cambios)
