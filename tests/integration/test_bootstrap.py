from collections import deque
from time import monotonic, sleep
from unittest.mock import Mock

import pytest

from holocontrol.bootstrap import crear_nucleo
from holocontrol.bootstrap import seleccionar_camara
from holocontrol.infrastructure.vision.errors import ErrorCamara
from holocontrol.domain.entities import Calibracion
from holocontrol.ports.vision.models import (
    EstadoVision,
    EventoGesto,
    FaseGesto,
    Lateralidad,
    ManoDetectada,
    PuntoMano,
    ResultadoVision,
)


def test_seleccion_automatica_prueba_otra_camara_y_libera_recursos(monkeypatch):
    fallida, disponible = Mock(), Mock()
    fallida.abrir.side_effect = ErrorCamara('No disponible')
    constructor = Mock(side_effect=[fallida, disponible])
    monkeypatch.setattr('holocontrol.bootstrap.CamaraOpenCV', constructor)
    assert seleccionar_camara(0) == 1
    assert [call.args[0].indice for call in constructor.call_args_list] == [0, 1]
    fallida.cerrar.assert_called_once()
    disponible.leer.assert_called_once()
    disponible.cerrar.assert_called_once()


def test_seleccion_manual_no_cambia_a_otro_dispositivo(monkeypatch):
    camara = Mock()
    camara.leer.side_effect = ErrorCamara('Sin imagen')
    constructor = Mock(return_value=camara)
    monkeypatch.setattr('holocontrol.bootstrap.CamaraOpenCV', constructor)
    with pytest.raises(ErrorCamara, match='No se encontró'):
        seleccionar_camara(0, 2)
    assert constructor.call_count == 1
    assert constructor.call_args.args[0].indice == 2
    camara.cerrar.assert_called_once()


class EjecutorSimulado:
    def __init__(self):
        self.clics = []
        self.activo = False
        self.mano = False

    def activate(self):
        self.activo = True

    def pause(self):
        self.activo = False

    def stop(self):
        self.activo = False
        self.mano = False

    def set_hand_detected(self, detected):
        self.mano = detected

    def move_cursor(self, x, y):
        pass

    def left_click(self):
        self.clics.append("izquierdo")

    def right_click(self):
        self.clics.append("derecho")

    def scroll(self, amount):
        pass


class ProveedorSimulado:
    def __init__(self):
        self.resultados = deque()
        self._activo = False

    @property
    def estado(self):
        return EstadoVision.CAMARA_DISPONIBLE

    @property
    def en_ejecucion(self):
        return self._activo

    @property
    def camara_disponible(self):
        return self._activo

    def iniciar(self):
        self._activo = True

    def obtener_resultado(self, espera_s=0.0):
        return self.resultados.popleft() if self.resultados else None

    def activar_vista_previa(self, activa):
        pass

    def obtener_fotograma(self):
        return None

    def detener(self, espera_s=2.0):
        self._activo = False
        return True


def test_composicion_sqlite_dominio_coordinador_y_accion_simulada(tmp_path):
    ejecutor = EjecutorSimulado()
    proveedor = ProveedorSimulado()
    componentes = crear_nucleo(
        tmp_path / "holocontrol.sqlite3",
        ejecutor_existente=ejecutor,
        proveedor_vision=proveedor,
    )

    perfil = componentes.repositorio.obtener(componentes.id_perfil)
    assert perfil is not None
    assert perfil.calibracion is None
    assert {a.id_gesto for a in perfil.asignaciones} >= {
        "indice",
        "pellizco",
        "dos_dedos",
        "subir",
        "bajar",
        "palma_abierta",
    }
    assert componentes.aplicacion.estado_actual().id_perfil_seleccionado == perfil.id
    componentes.aplicacion.calibrar_perfil(Calibracion(perfil.id))
    perfil = componentes.repositorio.obtener(perfil.id)

    componentes_lectura = crear_nucleo(
        tmp_path / "holocontrol.sqlite3",
        ejecutor_existente=EjecutorSimulado(),
        proveedor_vision=ProveedorSimulado(),
    )
    assert componentes_lectura.id_perfil == perfil.id
    assert componentes_lectura.repositorio.obtener(perfil.id) == perfil

    componentes.coordinador.iniciar_control(ancho_pantalla=800, alto_pantalla=600)
    sleep(0.01)
    ahora_ms = int(monotonic() * 1000)
    mano = ManoDetectada(
        tuple(PuntoMano(indice, 0.5, 0.5, 0.0) for indice in range(21)),
        Lateralidad.DERECHA,
        1.0,
    )
    proveedor.resultados.append(
        ResultadoVision(
            instante_ms=ahora_ms,
            estado=EstadoVision.MANO_DETECTADA,
            mano=mano,
            eventos=(EventoGesto("pellizco", FaseGesto.INICIO, ahora_ms, 0, 1.0),),
        )
    )
    try:
        resultado = componentes.coordinador.consultar_vision()
        assert resultado.ejecutado
        assert ejecutor.clics == ["izquierdo"]
    finally:
        componentes.coordinador.detener_control()

    guardado = componentes.repositorio.obtener(perfil.id)
    assert guardado == perfil


def test_existing_profiles_receive_new_gestures_without_overwriting_customization(tmp_path):
    from dataclasses import replace
    from holocontrol.domain.entities import AsignacionGesto
    path = tmp_path / 'upgrade.sqlite3'
    core = crear_nucleo(path, ejecutor_existente=Mock(), proveedor_vision=Mock())
    profile = core.repositorio.obtener(core.id_perfil)
    assignments = tuple(a for a in profile.asignaciones if a.id_gesto not in ('puno', 'tres_dedos'))
    assignments += (AsignacionGesto(profile.id, 'puno', 'clic_derecho'),)
    core.repositorio.actualizar(replace(profile, asignaciones=assignments))
    upgraded = crear_nucleo(path, ejecutor_existente=Mock(), proveedor_vision=Mock())
    profile = upgraded.repositorio.obtener(core.id_perfil)
    actual = {a.id_gesto: a.id_accion for a in profile.asignaciones}
    assert actual['puno'] == 'clic_derecho'
    assert actual['tres_dedos'] == 'cambiar_ventana'
