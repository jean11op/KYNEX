# Integración de dominio con visión

Los contratos canónicos de visión de esta integración son `ports/vision/models.py`
y `ports/vision/vision_provider.py` de `origin/feature/vision-gestures`. El DTO de
dominio usa sus nombres y campos existentes; no se mantiene una copia provisional.
El proveedor real y sus adaptadores viven en `infrastructure/vision/`.

La aplicación consulta el puerto `ProveedorVision`; `AdaptadorVision` implementa
ese contrato con cámara y detector inyectables. El dominio y sus casos de uso no
importan OpenCV, MediaPipe ni PyAutoGUI.

## Suavizado del cursor y del scroll

`ProcesadorVision.interpretar` suaviza `posicion_indice` usando
`ConfiguracionVision.factor_suavizado`; esa posición suavizada alimenta el delta
vertical del scroll. `Reconocimiento.desde_vision` usa el punto crudo 8 para el
cursor y `AplicacionControl._posicion_cursor` aplica calibración y el único
suavizado del perfil. Así el filtro de visión sigue estabilizando scroll sin
filtrar dos veces la coordenada del cursor.

## Consumo y generaciones

`CoordinadorControlVision` administra el ciclo de vida del proveedor y conserva la
generación de cada trabajador. La UI debe componerlo con `AplicacionControl` en
`bootstrap.py` cuando se integre esa fase:

```python
coordinador = CoordinadorControlVision(aplicacion, proveedor)
estado = coordinador.iniciar_control(
    ancho_pantalla=1920,
    alto_pantalla=1080,
)

# Desde el temporizador de la UI:
resultado = coordinador.consultar_vision()
```

El perfil debe estar seleccionado y calibrado antes de activar. El coordinador
inicia el proveedor, espera disponibilidad de cámara, activa el dominio y fija la
generación devuelta. Pausa y detención invalidan esa generación antes de detener
y drenar el proveedor. Una excepción del proveedor o un dato que no puede
convertirse pausa el control y publica el error.

Antes de reiniciar, el coordinador verifica que `detener()` haya terminado y drena
resultados pendientes. Cada consulta captura localmente la generación asociada al
trabajador; si termina tras una pausa o reanudación, el dominio rechaza ese
reconocimiento como antiguo. `FuenteReconocimiento` queda como contrato anterior
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
