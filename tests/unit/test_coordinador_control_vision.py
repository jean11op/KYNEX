from threading import Event, Thread
from time import monotonic, sleep

from holocontrol.application.services.coordinador_control_vision import (
    CoordinadorControlVision,
)
from holocontrol.application.use_cases import AplicacionControl
from holocontrol.domain.entities import Calibracion
from holocontrol.domain.value_objects.estado_control import EstadoControl
from holocontrol.infrastructure.vision.errors import ErrorCamara
from holocontrol.infrastructure.vision.vision_worker import AdaptadorVision
from holocontrol.ports.vision.models import (
    EstadoVision,
    EventoGesto,
    FaseGesto,
    Lateralidad,
    ManoDetectada,
    PuntoMano,
    ResultadoVision,
)
from tests.soporte import EjecutorRegistro, RelojSimulado, RepositorioPerfilesMemoria


class ProveedorSimulado:
    def __init__(self):
        self.estado = EstadoVision.DETENIDO
        self.en_ejecucion = False
        self.camara_disponible = False
        self.pendientes = []
        self.resultado_bloqueado = None
        self.entrada = None
        self.liberar = None

    def iniciar(self):
        self.en_ejecucion = True
        self.camara_disponible = True
        self.estado = EstadoVision.CAMARA_DISPONIBLE

    def detener(self, espera_s=2.0):
        self.en_ejecucion = False
        self.camara_disponible = False
        self.estado = EstadoVision.DETENIDO
        return True

    def obtener_resultado(self, espera_s=0.0):
        if self.resultado_bloqueado is not None:
            resultado = self.resultado_bloqueado
            self.resultado_bloqueado = None
            self.entrada.set()
            assert self.liberar.wait(2)
            return resultado
        return self.pendientes.pop(0) if self.pendientes else None

    def activar_vista_previa(self, activa):
        pass

    def obtener_fotograma(self):
        return None


def _configurar():
    reloj = RelojSimulado()
    ejecutor = EjecutorRegistro()
    aplicacion = AplicacionControl(RepositorioPerfilesMemoria(), ejecutor, reloj)
    perfil = aplicacion.crear_perfil("Sesiones")
    aplicacion.seleccionar_perfil(perfil.id)
    aplicacion.calibrar_perfil(Calibracion(perfil.id, suavizado=0))
    proveedor = ProveedorSimulado()
    coordinador = CoordinadorControlVision(aplicacion, proveedor)
    return reloj, ejecutor, aplicacion, proveedor, coordinador


def _resultado_clic(instante_ms):
    mano = ManoDetectada(
        tuple(PuntoMano(i, 0.5, 0.5, 0) for i in range(21)),
        Lateralidad.DERECHA,
        0.99,
    )
    evento = EventoGesto("pulgar", FaseGesto.INICIO, instante_ms, 0, 0.99)
    return ResultadoVision(
        instante_ms,
        EstadoVision.MANO_DETECTADA,
        mano,
        (0.5, 0.5),
        (0, 0),
        (evento,),
    )


def test_resultado_de_trabajador_antiguo_que_llega_tarde_no_actua():
    reloj, ejecutor, aplicacion, proveedor, coordinador = _configurar()
    primera = coordinador.iniciar_control(ancho_pantalla=100, alto_pantalla=100)
    reloj.avanzar(0.1)
    proveedor.resultado_bloqueado = _resultado_clic(round(reloj() * 1000))
    proveedor.entrada, proveedor.liberar = Event(), Event()
    respuestas = []
    hilo = Thread(target=lambda: respuestas.append(coordinador.consultar_vision()))
    hilo.start()
    assert proveedor.entrada.wait(2)

    coordinador.pausar_control()
    reloj.avanzar(0.1)
    nueva = coordinador.reanudar_control()
    proveedor.liberar.set()
    hilo.join(2)

    assert not hilo.is_alive()
    assert nueva.generacion > primera.generacion
    assert respuestas[0].motivo == "generacion_anterior"
    assert aplicacion.estado_actual().generacion == nueva.generacion
    assert ejecutor.llamadas == []
    coordinador.detener_control()


def test_pendientes_del_trabajador_anterior_se_drenan_antes_de_reiniciar():
    reloj, ejecutor, aplicacion, proveedor, coordinador = _configurar()
    coordinador.iniciar_control(ancho_pantalla=100, alto_pantalla=100)
    reloj.avanzar(0.1)
    proveedor.pendientes.append(_resultado_clic(round(reloj() * 1000)))

    coordinador.pausar_control()
    coordinador.reanudar_control()
    resultado = coordinador.consultar_vision()

    assert resultado.motivo == "sin_resultado"
    assert proveedor.pendientes == []
    assert ejecutor.llamadas == []
    assert aplicacion.estado_actual().estado is EstadoControl.ACTIVE
    coordinador.detener_control()


def test_proveedor_real_descarta_eventos_anteriores_al_iniciar_ciclo():
    class CamaraConFallo:
        def abrir(self):
            raise ErrorCamara("Sin cámara física en esta prueba")

        def cerrar(self):
            pass

    class DetectorSinRecursos:
        def cerrar(self):
            pass

    proveedor = AdaptadorVision(
        crear_camara=CamaraConFallo,
        crear_detector=DetectorSinRecursos,
    )
    proveedor._publicar(_resultado_clic(1))
    assert proveedor.detener()
    proveedor.iniciar()
    limite = monotonic() + 2
    while proveedor.estado is not EstadoVision.ERROR_CAMARA and monotonic() < limite:
        sleep(0.005)
    resultado = proveedor.obtener_resultado()
    assert resultado.estado is EstadoVision.ERROR_CAMARA
    assert resultado.eventos == ()
    assert proveedor.detener()
