# Kinex: módulo de visión del integrante 3

Esta entrega implementa percepción local en `infrastructure/vision/` y entrega datos al resto del monolito mediante `ports/vision/`. Incluye captura de webcam seleccionable, OpenCV, MediaPipe Tasks, los 21 puntos de la mano, movimiento suavizado, gestos básicos y posturas propias. No ejecuta acciones del sistema.

La rama local es `feature/vision-gestures`, creada desde `origin/develop`. El paquete Python sigue llamándose `holocontrol` para conservar la compatibilidad con las ramas del equipo. El nombre de producto en esta entrega es Kinex.

Los resultados y el estado de las ramas revisadas se documentan en [la validación de visión](../requirements/vision-validation.md). Para fusionar con el prototipo de UI se incluye [la configuración compartida resuelta](vision-integration-pyproject.toml), sin modificar los archivos de esa rama.

## Decisiones confirmadas

El usuario confirmó el catálogo completo, entrenamiento de posturas estáticas con al menos 20 muestras, contrato mínimo de visión y parámetros iniciales configurables. Se conserva la arquitectura de monolito modular por capas con principios hexagonales del documento.

| Señal reconocida | Forma y condición | Uso acordado para la aplicación |
| --- | --- | --- |
| `indice` | Índice extendido y otros tres dedos flexionados; 100 ms estables | Posición del cursor |
| `pellizco` | Pulgar e índice próximos; 100 ms estables | Clic/arrastre en cursor o trazo en dibujo |
| `dos_dedos` | Índice y medio extendidos; otros dos flexionados; 100 ms | Desplazamiento vertical |
| `palma_abierta` | Cuatro dedos extendidos y palma quieta durante 800 ms | Solicitud de activar/pausar |
| `puno` | Cuatro dedos flexionados y palma quieta durante 800 ms | Solicitud de cambiar cursor/dibujo |
| `deslizamiento_izquierda` / `deslizamiento_derecha` | Palma abierta, movimiento horizontal de al menos 0,20 del ancho en hasta 500 ms | Solicitud de cambio de pestaña/diapositiva |
| `personalizado:<nombre>` | Postura propia válida, suficientemente similar a una plantilla, 100 ms | Asignación validada por el dominio |

La visión informa señales. La aplicación decide la acción y si puede ejecutarla. El mismo pellizco tiene una sola función según el modo elegido por la aplicación.

## Archivos y dependencias

| Archivo o directorio | Responsabilidad |
| --- | --- |
| `ports/vision/models.py` | Datos inmutables y enumeraciones sin importar OpenCV, NumPy, MediaPipe o Qt |
| `ports/vision/vision_provider.py` | Protocolos de cámara, detector, proveedor en segundo plano y entrenamiento |
| `ports/vision/__init__.py` | Exportación pública del proveedor, estados y datos de visión |
| `infrastructure/vision/camera.py` | Apertura, lectura, espejo y liberación de webcam |
| `infrastructure/vision/hand_detector.py` | Conversión BGR/RGB y adaptación de MediaPipe Tasks VIDEO |
| `infrastructure/vision/geometry.py` | Geometría de puntos, puntuación de dedos y descriptor normalizado |
| `infrastructure/vision/gesture_recognizer.py` | Estabilización, histéresis, permanencia y deslizamientos |
| `infrastructure/vision/gesture_training.py` | Captura y validación de muestras y plantillas propias en memoria |
| `infrastructure/vision/vision_processor.py` | Mano dominante, invalidación, coordenadas y desplazamientos suavizados |
| `infrastructure/vision/vision_worker.py` | Hilo de captura/procesamiento y entrega de resultados recientes |
| `infrastructure/vision/models/` | Modelo oficial local y su licencia Apache 2.0 |
| `infrastructure/vision/demo.py` | Prueba independiente por consola y vista de diagnóstico opcional |
| `tests/unit/vision/`, `tests/integration/vision/` | Pruebas exclusivas del módulo |

No se modifican `presentation/`, `domain/`, `application/`, persistencia ni acciones de Windows. El único ajuste compartido está en `pyproject.toml`: usar una sola distribución `opencv-contrib-python`, requerida también por MediaPipe, e incluir el modelo y su licencia en el paquete distribuible.

## Instalación y revisión

Entorno verificado: Python 3.13.15, Windows x64, MediaPipe 1.1.0, OpenCV contrib 5.0.0.93 y NumPy 2.5.4. Las versiones de visión y pruebas se fijan en `scripts/vision-constraints.txt`; esto no garantiza rendimiento en cualquier computador.

Desde la raíz del repositorio, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -c scripts/vision-constraints.txt
.\.venv\Scripts\python.exe -m pytest tests/unit/vision tests/integration/vision -q
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --duracion 30
```

Para otra cámara o mano:

```powershell
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --camara 1 --mano izquierda --duracion 30
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --sin-vista --duracion 10
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --entrenar mi_postura --duracion 30
```

La demo dibuja los puntos sobre la vista previa y muestra inicio/fin de gestos por consola. No mueve el mouse, hace clic ni guarda fotografías. `Esc`, `Q`, cierre de la vista y `Ctrl+C` finalizan la prueba. El entrenamiento de la demo solo conserva su plantilla en memoria durante esa ejecución.

Primero presenta el índice abierto para habilitar el reconocimiento posterior de pellizcos. Mantén palma o puño quietos durante 800 ms; cambia de postura antes de repetirlos. Prueba movimientos horizontales de palma en menos de 500 ms. Para un gesto propio, mantén una postura distinta de las básicas, por ejemplo solo el dedo medio extendido.

La creación de entornos requiere internet para instalar bibliotecas. Una vez instalado, el procesamiento usa el modelo incluido y no requiere internet. No deben coexistir `opencv-python`, `opencv-contrib-python` y sus variantes headless en el mismo entorno.

## Contrato de resultados

`Fotograma` contiene una imagen `uint8 BGR`, `instante_ms` y `en_espejo`. Para imágenes suministradas por otro módulo, declara correctamente si se reflejaron. El detector compensa la inversión de lateralidad cuando `en_espejo=True`, conservando los puntos en las coordenadas de la imagen entregada.

`DeteccionManos` entrega todas las manos detectadas (máximo dos), tamaño real de imagen y estado. El procesador selecciona una sola mano dominante. Si aparecen dos manos con la misma lateralidad estimada, descarta la detección por ambigüedad.

`ResultadoVision` entrega:

- `instante_ms`: reloj monotónico en milisegundos, no fecha UTC. Los instantes de fotogramas aumentan estrictamente; los cambios de ciclo pueden ocurrir en el mismo milisegundo.
- `estado`, `es_valido` y `mano_detectada`: estado reciente y presencia de una mano seleccionada válida. `mano_detectada` equivale a `es_valido`; nunca describe una mano anterior conservada en el historial.
- `camara_disponible`: el estado reciente informa una cámara abierta sin un error terminal; no garantiza presencia de mano ni vigencia de coordenadas.
- `mano`: 21 puntos ordenados del 0 al 20, lateralidad física y `confianza_lateralidad`.
- `posicion_indice`: coordenadas suavizadas entre 0 y 1; el origen está en la esquina superior izquierda.
- `desplazamiento_indice` y `desplazamiento_vertical`: desplazamiento normalizado acumulado desde la última consulta al proveedor dentro del mismo seguimiento. `desplazamiento_vertical` es su componente y; positivo significa hacia abajo. Se reinicia al consumir, perder la mano, iniciar o cerrar. El procesador utilizado directamente entrega el delta entre fotogramas.
- `eventos`: todos los eventos pendientes en orden de generación, con nombre, fase `inicio`/`mantenimiento`/`fin`, instante, duración desde el inicio confirmado y puntuación. Incluye historial anterior a una pérdida, error o cierre; se entrega una vez.
- `eventos_actuales`: eventos del último fotograma, distinguidos del historial acumulado. Con un resultado inválido solo expone el fin generado en ese instante.
- `latencia_procesamiento_ms`: detección y procesamiento de ese fotograma.
- `latencia_total_ms`: tiempo desde la entrega del fotograma al proceso hasta obtener el resultado; no es latencia física cámara-acción.
- `mensaje`: orientación o descripción del problema.

MediaPipe no expone aquí una probabilidad de presencia por mano. Sus umbrales de detección, presencia y seguimiento se aplican dentro del detector. La confianza de lateralidad solo clasifica izquierda/derecha. La puntuación de los gestos básicos es geométrica y la de un gesto propio es similitud con su plantilla; ninguna equivale a una precisión de reconocimiento medida.

`ResultadoVision` valida coordenadas entre 0 y 1, deltas finitos y eventos ordenados que no sean posteriores al resultado. Una mano perdida, error o detención no admite coordenadas ni puntos de mano vigentes, aunque conserve eventos históricos.

El valor z es profundidad relativa a la muñeca, puede ser negativo y no es una coordenada de pantalla. Se rechazan puntos no finitos, incompletos o fuera de imagen. El detector utiliza el tamaño real del fotograma para corregir distancias y ángulos por relación de aspecto.

## Integración con aplicación e interfaz

La implementación de visión depende de contratos de `ports/vision`. Los contratos no dependen de los adaptadores. El ensamblado final corresponde a `bootstrap` y al integrante de integración; esta entrega no modifica su implementación.

`EntrenadorVision` define el contrato de captura y entrenamiento. `MuestraPostura` y `PlantillaGesto` son datos inmutables en `ports/vision/models.py`, accesibles a aplicación y persistencia sin importar la implementación del entrenador. Su algoritmo y la geometría permanecen en infraestructura.

```python
from holocontrol.infrastructure.vision import AdaptadorVision, ConfiguracionVision
from holocontrol.ports.vision import ProveedorVision

proveedor: ProveedorVision = AdaptadorVision(ConfiguracionVision())
proveedor.iniciar()

# En un temporizador de la interfaz o en el coordinador de aplicación:
resultado = proveedor.obtener_resultado()  # No bloquea: espera por defecto de cero.
if resultado is not None:
    print(resultado.estado, resultado.camara_disponible, resultado.mano_detectada)
    for evento in resultado.eventos:
        print(evento.nombre, evento.fase, evento.confianza, evento.instante_ms)
    if resultado.es_valido:
        print(resultado.posicion_indice, resultado.desplazamiento_vertical)

finalizado = proveedor.detener()
if not finalizado:
    print("El controlador de cámara no respondió al cierre; conserva el control detenido.")
```

El ejemplo muestra el intercambio de datos; la aplicación debe implementar la validación y ejecución mediante sus propios contratos. No se debe llamar `iniciar()` en cada actualización de ventana. Se inicia una vez y se consulta periódicamente, por ejemplo desde un `QTimer` de 16–33 ms. El hilo no llama widgets ni callbacks de Qt.

`ProveedorVision` sigue siendo el responsable de obtener resultados de cámara. Usa un solo coordinador como consumidor de `obtener_resultado()` y distribuye el objeto inmutable obtenido a aplicación e interfaz. Cada consulta drena la cola: dos consumidores independientes repartirían los eventos entre sí. `espera_s=0` consulta sin esperar datos nuevos; `None` indica que no hay novedades. Las propiedades `estado`, `en_ejecucion` y `camara_disponible` pueden consultarse sin drenar eventos.

### Estados de cámara y trabajador

| `EstadoVision` | Significado para integración |
| --- | --- |
| `INICIANDO` | Se inició el trabajador; aún no se confirmó la apertura de cámara |
| `CAMARA_DISPONIBLE` | Cámara abierta; todavía puede no existir un fotograma procesado |
| `MANO_DETECTADA` | Mano seleccionada válida y coordenadas recientes |
| `SIN_MANO` | Se procesa cámara, sin una mano detectada |
| `MANO_PERDIDA` | Se perdió el seguimiento o caducaron los datos; sin coordenadas |
| `MANO_NO_SELECCIONADA` / `BAJA_CONFIANZA` | No hay una mano admitida para control; sin coordenadas |
| `ERROR_CAMARA` | Fallo de apertura/lectura o timeout al detener; mensaje con la causa |
| `ERROR_PROCESAMIENTO` | Fallo de modelo, procesamiento o liberación de recursos |
| `DETENIENDO` | Cierre solicitado, acciones gestuales invalidadas; el hilo puede seguir liberando recursos |
| `DETENIDO` | Cierre normal completado; cámara y detector liberados |

El estado inicial del proveedor es `DETENIDO`. `camara_disponible` se confirma después de `abrir()` y permanece independiente de que haya una mano. Los estados transitorios pueden ser sustituidos por el siguiente resultado antes de una consulta; utiliza la propiedad de disponibilidad para comprobar la apertura. `en_ejecucion` indica si el hilo sigue vivo, incluso mientras completa un cierre. Un error queda expuesto hasta iniciar otro ciclo. Si se solicita cierre, `camara_disponible` pasa a `False` de inmediato y ningún resultado que termine después puede reactivar coordenadas.

Para calibración o una vista opcional, llama `activar_vista_previa(True)` y consulta `obtener_fotograma()`. Devuelve una copia del último fotograma BGR reciente, sin abrir otra cámara. La conversión a `QImage` y su visualización corresponden a presentación. La vista previa permanece desactivada por defecto, conserva como máximo una imagen en memoria y la descarta al desactivarse o detenerse; nunca escribe archivos. Puede mostrar la cámara aunque todavía no se detecte una mano.

Para recibir imágenes de otra fuente, usa `DetectorMediaPipe.detectar(Fotograma(...))` seguido de `ProcesadorVision.interpretar(deteccion)`. Así no es necesario abrir una webcam. Un detector pertenece a un único hilo y usa instantes crecientes. `cerrar()` permite reiniciarlo con una nueva secuencia.

| Integrante | Datos que consume o entrega |
| --- | --- |
| 1, interfaz | Estado, mensajes, puntos y eventos para calibración/prueba; formularios y vista del producto siguen siendo su responsabilidad |
| 2, aplicación/dominio | Perfil, mano elegida, parámetros, asignaciones, pausa y modo; convierte coordenadas a zona calibrada y decide acciones |
| 4, persistencia | Muestras exportadas como 21 puntos por muestra; calibraciones y asignaciones siguen a través de sus repositorios |
| 5, Windows/integración | Acciones autorizadas por aplicación; nunca consume directamente una detección cruda para ejecutar clics |

En `origin/feature/windows-actions`, `ActionExecutor` recibe coordenadas en píxeles y cantidades de scroll; este módulo entrega coordenadas normalizadas y deltas. El coordinador debe transformar zona calibrada, sensibilidad y dimensiones de pantalla antes de llamar al ejecutor. La clase `ClickController` existente sigue intacta; no representa por sí sola la lógica de arrastre ni la separación cursor/dibujo.

Esa rama importa `pyautogui`, dependencia que todavía no aparece en `develop`. Su declaración e integración corresponden al integrante 5. La comprobación temporal de compatibilidad utiliza un módulo PyAutoGUI simulado para impedir acciones reales del mouse.

La pausa no detiene obligatoriamente la percepción: puede seguir reconociéndose la palma que solicita reanudación. El dominio impide mover/clicar/dibujar mientras esté pausado. Detener la aplicación sí requiere cerrar cámara y detector.

La rama de aplicación/dominio revisada en `c0d8c96` utiliza una asignación diferente para `dos_dedos` y el identificador `palma` para la palma abierta. Antes de conectar acciones reales, aplicación debe resolver esa correspondencia con el catálogo aprobado de visión; la diferencia y los campos del perfil están detallados en la ficha de validación. Este módulo conserva el comportamiento aprobado por el usuario.

Esa rama también publica `FuenteReconocimiento`, basada en callbacks, y `Reconocimiento`, un DTO de un gesto por fotograma. No sustituyen el contrato de consulta `ProveedorVision` solicitado para esta entrega. El coordinador de I1/I5 debe conectar ambos contratos y conservar el historial de visión por separado, ya que el DTO de aplicación no tiene campos de fase ni lista de eventos.

| Campo de aplicación | Correspondencia con visión |
| --- | --- |
| `generacion` | Generación vigente entregada por `AplicacionControl`; no se inventa desde visión |
| `instante_captura` | `resultado.instante_ms / 1000`, en el mismo reloj monotónico |
| `mano_detectada` | `resultado.mano_detectada` |
| `x`, `y` | Puntos crudos normalizados `resultado.mano.puntos[8].x/y` si hay mano válida; aplicación aplica su calibración y suavizado |
| `id_gesto`, `confianza` | Gesto vigente y puntuación de `eventos_actuales`, aplicando la traducción de catálogo acordada con I2 |

La lista histórica `eventos` no debe convertirse en órdenes de acción con el instante nuevo de otro fotograma. Conserva los instantes originales y comprueba vigencia, generación y estado del control. Al recibir un resultado inválido, comunica ausencia de mano y libera interacciones activas. La visión no llama a `procesar_reconocimiento`, a ejecutores de Windows ni a sus métodos de clic.

## Invalidación y eventos

Ante pérdida de mano, lateralidad incierta, cambio brusco de posición, intervalo superior a 200 ms o error, se borran las coordenadas anteriores y termina cualquier gesto activo. El procesador emite `fin`; el proveedor añade los eventos históricos que aún no fueron consultados. La aplicación debe liberar cualquier arrastre/trazo activo al recibir un resultado inválido, aunque el consumidor reciba su inicio y fin juntos.

El pellizco usa histéresis: distancia pulgar–índice dividida por ancho de palma; entrada 0,30 y salida 0,45. Al iniciar la captura o recuperar una mano perdida se exige observar primero un pellizco abierto. Una mano cerrada recuperada no inicia por sí sola otra interacción. No existe clic por permanencia del cursor.

Palma y puño producen un solo `inicio` mientras se mantenga esa postura. Las fases de mantenimiento no deben repetir acciones discretas. Un deslizamiento consume la misma postura de palma y no genera después una solicitud de pausa hasta cambiar de postura.

El proveedor conserva el resultado estructurado más reciente y una cola en memoria con todas las fases pendientes: inicio, mantenimiento y fin. Las entrega en orden una sola vez al consultar, incluso si entre consultas perdió la mano, hubo un error, se detuvo o se inició otro ciclo. No hay descarte por antigüedad ni límite de 64 eventos. La cola guarda metadatos de gestos; se drena periódicamente y no almacena imágenes ni escribe archivos.

La caducidad de 200 ms invalida la mano, sus coordenadas y desplazamientos. Los eventos anteriores se conservan con sus instantes originales como historial, no como gestos válidos para ejecutar. `es_valido` y el estado reciente se comprueban antes de cualquier acción; la aplicación valida además la edad de cada evento que decida utilizar. Al consumir, el desplazamiento se reinicia para evitar repetir scroll.

`detener(espera_s=2)` tiene espera acotada. Si un controlador nativo queda bloqueado en lectura, devuelve `False` e informa error. No intenta cerrar el mismo recurso simultáneamente desde dos hilos. El hilo conserva la responsabilidad de liberarlo cuando responda el controlador. La aplicación debe mantener detenidas las acciones hasta resolver ese error.

## Gestos propios y almacenamiento

`EntrenadorGestos.registrar(deteccion)` acepta una mano dominante fiable y 21 puntos válidos. Las capturas se separan al menos 50 ms para evitar reutilizar un fotograma. `finalizar(nombre)` exige 20 muestras coherentes, valida cada muestra frente a las demás y rechaza posturas que coincidan con los gestos básicos.

El descriptor elimina traslación, escala y orientación absoluta de la palma; reconoce posturas estáticas relativas de los dedos. No aprende secuencias dinámicas ni garantiza distinguir posturas con geometría casi idéntica. Se rechaza el reconocimiento si dos plantillas presentan puntuaciones demasiado próximas.

```python
from holocontrol.infrastructure.vision import EntrenadorGestos, ProcesadorVision

entrenador = EntrenadorGestos()
# Por cada nueva detección válida seleccionada durante la captura de muestras:
# entrenador.registrar(deteccion)
# Después de reunir al menos 20 muestras:
# plantilla = entrenador.finalizar("mi_postura")
# procesador = ProcesadorVision(plantillas=(plantilla,))
```

`entrenador.muestras` y `plantilla.muestras` exponen el instante monotónico de captura y una mano con sus 21 puntos canónicos: sin espejo y en una escala isotrópica dentro del cuadro unitario. Son coordenadas de entrenamiento; la vista previa utiliza los puntos originales de `DeteccionManos` o `ResultadoVision`. La conversión canónica elimina la necesidad de almacenar dimensiones de imagen en la base de datos.

El integrante 4 puede guardar esos 21 puntos directamente en `punto_muestra`, con una fila por índice. El integrante 2 valida propietario, perfil y asignación. Para reconstruir una plantilla desde puntos persistidos, crea detecciones de esos puntos canónicos con la lateralidad del perfil, `ancho=1`, `alto=1`, `en_espejo=False` e instantes secuenciales separados 50 ms. Registra las muestras en un nuevo entrenador y finaliza de nuevo. Estos instantes de reconstrucción no son fechas de uso; la persistencia registra `fecha_captura` por su propio mecanismo.

Este módulo no añade columnas ni escribe SQLite. Hasta conectarlo al repositorio del equipo, las plantillas se conservan en memoria. Al cambiar perfil o parámetros, detén el proveedor y crea otro con la configuración y plantillas de ese perfil. La reconstrucción y la conservación de reconocimiento al cambiar el espejo tienen pruebas automatizadas.

## Trazabilidad y límites de validación

| Referencia del documento | Entrega de visión |
| --- | --- |
| RF-01 / RF-UI-39 | Webcam seleccionable y lectura local |
| RF-02 | MediaPipe y 21 puntos estructurados |
| RF-04 / RF-07 / RF-12 | Índice normalizado, deltas y suavizado; zona/sensibilidad final a cargo de aplicación |
| RF-05 / RF-06 / RF-20 | Inicio, mantenimiento y fin de pellizco; no ejecuta acciones ni implementa el lienzo |
| RF-08 / RF-09 / RF-22 | Deslizamientos y permanencia de palma/puño como solicitudes |
| RF-10 retirado | No hay clic al dejar quieto el índice |
| RF-17 | Tiempos por fotograma y resumen de diagnóstico |
| RF-18 | Captura, validación y reconocimiento de posturas propias; pantalla y guardado pertenecen a otros módulos |
| RF-27 / RNF-06 | Modelo local, sin transmisión ni grabación de cámara |
| RNF-04 / RNF-UI-01 | Invalidación y procesamiento en hilo independiente |
| RNF-10 | Contratos sin bibliotecas externas, pruebas y documentación |

Las pruebas automatizadas verifican geometría, eventos, pérdidas, expiración, errores, entrenamiento y el modelo local en imágenes sin mano. Se hicieron además comprobaciones con fotografías oficiales de prueba de MediaPipe para índice y lateralidad. Las imágenes de terceros no se agregan al repositorio.

RNF-01 (<150 ms gesto–acción en p95), RNF-02 (25 FPS) y RNF-03 (90 % de precisión) son metas pendientes de evaluación conjunta en el equipo objetivo. Los tiempos de inferencia de esta entrega no sustituyen latencia de acción, y las pruebas sintéticas no miden precisión de uso real. La revisión debe cubrir diferentes manos, iluminación, distancia, oclusión, espejo y posturas no intencionales.

## Fuentes técnicas

- [MediaPipe Hand Landmarker para Python](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python)
- [Modelo oficial y ficha](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker)
- [OpenCV VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html)
- [Instalación de una única distribución de OpenCV](https://pypi.org/project/opencv-python/)
