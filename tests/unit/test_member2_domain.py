import unittest
from dataclasses import FrozenInstanceError
from holocontrol.domain.entities import (
    Accion, TipoAccion, Calibracion, Gesto, AsignacionGesto, Mano, Perfil, Configuracion,
)
from holocontrol.domain.errors import ErrorDominio
from holocontrol.application.dto.recognition import Reconocimiento


class PruebasDominio(unittest.TestCase):
    def test_perfil_limpia_nombre_y_es_inmutable(self):
        p = Perfil("p", "  Cesar  ")
        self.assertEqual(p.nombre, "Cesar")
        with self.assertRaises(FrozenInstanceError):
            p.nombre = "otro"

    def test_campos_perfil_invalidos(self):
        for kwargs in ({"nombre": " "}, {"mano_dominante": "ambas"},
                       {"tiempo_espera_gesto_ms": 0}, {"tiempo_espera_gesto_ms": True},
                       {"limite_dictado": -1}, {"limite_dictado": 2.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ErrorDominio):
                Perfil("p", **({"nombre": "Cesar"} | kwargs))

    def test_calibracion_invalida(self):
        for kwargs in ({"x_min": 0.8, "x_max": 0.2}, {"y_min": 1},
                       {"sensibilidad": 0}, {"suavizado": 2}, {"x_min": float('nan')},
                       {"x_max": float('inf')}, {"y_max": -0.1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ErrorDominio):
                Calibracion("p", **kwargs)

    def test_limites_calibracion(self):
        self.assertEqual(Calibracion("p", sensibilidad=5, suavizado=1).sensibilidad, 5)

    def test_rechaza_calibracion_ajena(self):
        with self.assertRaises(ErrorDominio):
            Perfil("p", "A", calibracion=Calibracion("q"))

    def test_confianza_es_probabilidad_finita(self):
        for valor in (-1, 1.1, float('nan'), float('inf'), True):
            with self.subTest(valor=valor), self.assertRaises(ErrorDominio):
                Gesto("g", "G", umbral_confianza=valor)

    def test_predefinido_se_deduce(self):
        self.assertTrue(Gesto("g", "G").predefinido)
        self.assertFalse(Gesto("g", "G", "p").predefinido)

    def test_accion_rechaza_comandos_arbitrarios(self):
        with self.assertRaises(ErrorDominio):
            Accion("a", "Abrir comando", "os.system")

    def test_parametro_desplazamiento(self):
        for cantidad in (0, 11, -11, 1.5, True):
            with self.subTest(cantidad=cantidad), self.assertRaises(ErrorDominio):
                Accion("a", "Scroll", TipoAccion.DESPLAZAR, cantidad)

    def test_solo_desplazamiento_acepta_cantidad(self):
        with self.assertRaises(ErrorDominio):
            Accion("a", "Clic", TipoAccion.CLIC_IZQUIERDO, 1)

    def test_gesto_y_asignacion_ajenos(self):
        for kwargs in ({"gestos": (Gesto("g", "G", "q"),)},
                       {"asignaciones": (AsignacionGesto("q", "g", "a"),)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ErrorDominio):
                Perfil("p", "P", **kwargs)

    def test_asignacion_duplicada(self):
        a = AsignacionGesto("p", "g", "a")
        with self.assertRaises(ErrorDominio):
            Perfil("p", "P", asignaciones=(a, a))

    def test_valida_configuracion(self):
        for kwargs in ({"tema": "extra"}, {"escala_interfaz": 0.5}, {"indice_camara": -1},
                       {"atajo_pausa": "shell cmd"}, {"mostrar_avisos": "si"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ErrorDominio):
                Configuracion(**kwargs)

    def test_fotogramas_invalidos(self):
        for kwargs in ({"confianza": float('nan')}, {"x": 0.5},
                       {"instante_captura": -1}, {"generacion": -1}, {"mano_detectada": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ErrorDominio):
                Reconocimiento(**({"generacion": 1, "instante_captura": 1,
                               "mano_detectada": True} | kwargs))

    def test_listas_se_copian_a_tuplas_inmutables(self):
        gestos = [Gesto("g", "G", "p")]
        perfil = Perfil("p", "P", gestos=gestos)
        gestos.clear()
        self.assertEqual(len(perfil.gestos), 1)
