# Integración de dominio con visión

La aplicación consume `ProveedorVision` del integrante 3. Los contratos de
`ports/vision/models.py` y `vision_provider.py` coinciden con los del ZIP
`HoloControl-Access-feature-vision-gestures.zip`. No se requiere importar OpenCV,
MediaPipe ni PyAutoGUI en el dominio o en sus casos de uso.

## Consumo y generaciones

El coordinador de integración administra el ciclo de vida del proveedor. Inicia
el trabajador una vez y conserva la generación devuelta al activar el control:

```python
estado = aplicacion.iniciar_control(
    camara_disponible=True,  # Solo después de comprobar la disponibilidad real.
    ancho_pantalla=1920,
    alto_pantalla=1080,
)
generacion_del_trabajador = estado.generacion

# Desde el temporizador/coordinador, sin espera de cámara:
resultado = aplicacion.consultar_vision(
    proveedor, generacion=generacion_del_trabajador,
)
```

El perfil debe estar seleccionado y calibrado antes de activar. El proveedor ya
debe estar iniciado y comprobado por el coordinador. `consultar_vision` obtiene
datos; no inicia ni detiene trabajadores. Una excepción del proveedor o un dato
que no puede convertirse pausa el control y publica el error.

Antes de iniciar o reanudar otra sesión, detener el trabajador anterior y verificar
que `detener()` devolvió `True`; descartar sus resultados pendientes e iniciar el
trabajador de la nueva sesión. No etiquetar resultados antiguos con la generación
actual. Las consultas en curso conservan su generación y se rechazan si la sesión
cambió mientras esperaban. `FuenteReconocimiento` queda como contrato anterior
por callbacks; no es el proveedor implementado por esta rama de visión.

También se puede entregar directamente
`Reconocimiento.desde_vision(resultado, generacion_del_trabajador)` a
`procesar_reconocimiento`. El reloj compartido es monotónico: los fotogramas usan
segundos y los eventos de visión milisegundos. Se descartan generaciones distintas,
fotogramas repetidos, anteriores a la sesión, futuros o de más de 250 ms.

## Eventos y asignaciones

Se recorren todos los eventos en el orden recibido. Cada evento tiene su propio
resultado en `ResultadoGesto.resultados_eventos`; el resumen indica si se ejecutó
alguna acción. Los eventos anteriores al último aceptado, repetidos, futuros o
vencidos no disparan acciones. Se admiten eventos diferentes en un mismo instante.
`FIN` libera el gesto sin ejecutar una acción, incluso si llega retrasado.

Los clics y otras acciones discretas se disparan en `INICIO`. Su mantenimiento no
repite acciones; requieren `FIN` antes de un nuevo inicio. El tiempo de espera del
perfil se mide entre los instantes de los eventos, también dentro de un lote.
El cursor y el scroll vertical son continuos. Un lote vacío no libera los gestos
de eventos. El contrato anterior `id_gesto/confianza` sigue disponible.

| Gesto | Asignación inicial |
| --- | --- |
| `indice` | Cursor calibrado |
| `pellizco` | Clic izquierdo |
| `dos_dedos` | Desplazamiento vertical |
| `subir` / `bajar` | Scroll fijo de +3 / -3; compatibilidad anterior |
| `palma_abierta` | Pausar |
| `puno` | Disponible para asignar |
| `deslizamiento_izquierda` / `deslizamiento_derecha` | Disponibles para asignar |
| `personalizado:<nombre>` | Asignación del gesto propio del perfil activo |

Los perfiles existentes conservan sus asignaciones. Para aplicar las iniciales se
usa la restauración explícita existente. El clic derecho continúa disponible para
asignarlo. Cambio de modo, dibujo, arrastre y cambio de pestaña no forman parte del
contrato actual de `EjecutorControl`; esos gestos no ejecutan acciones inventadas.

El scroll convierte `delta_y` en `-delta_y * 30` unidades de rueda, conserva el
residuo fraccionario y consume el delta una sola vez por lote. Así, +0,1 en y
produce -3 unidades (abajo); cero no produce scroll. La pérdida de mano, el fin de
gesto o el cambio de sesión limpian el residuo. La escala inicial requiere ajuste
de usabilidad con cámara real.

## Estados y ejecución

- Sin mano, mano perdida, mano no seleccionada o baja confianza: bloquean acciones
  y limpian detección y suavizado; la cámara sigue disponible y el control activo.
- Error de cámara, error de procesamiento o trabajador detenido: pausan, invalidan
  la generación y publican cámara no disponible y el mensaje. Se necesita reanudar
  explícitamente después de comprobar la cámara. Los avisos retrasados también
  bloquean si pertenecen a la sesión y no están fuera de orden.
- Un gesto de pausa interrumpe las acciones restantes del lote.
- Las excepciones del ejecutor pausan el control y solicitan su detención.

La cadena de acciones sigue siendo `AplicacionControl → EjecutorControl →
AdaptadorEjecutorExistente → WindowsActionExecutor`. Visión solo produce datos.
La aplicación conserva asignaciones, confianza, deduplicación y reglas del dominio.

## Verificación

`python scripts/verificar.py` ejecuta las pruebas del integrante 2 sin cámara ni
acciones reales del mouse. Incluye lotes, fases, scroll, generaciones, tiempos,
estados, proveedor, gestos propios y el contrato del adaptador de Windows con
PyAutoGUI simulado. La prueba física de cámara e interfaz corresponde al ensamblado
con la rama de visión.
