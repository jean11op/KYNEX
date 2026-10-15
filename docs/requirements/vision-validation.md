# Validación del módulo de visión de Kinex

Verificación inicial: 13 de octubre de 2026. Revisión de deslizamientos y del contrato solicitado para integración: 14 de octubre de 2026. Rama: `feature/vision-gestures`.

La entrega se publica como rama de trabajo para integración, con validación real de webcam pendiente. La base es `origin/develop` en `4d4ede9`.

Los resultados de coexistencia que siguen son mediciones históricas en copias
temporales, no validaciones de esta integración. La suite combinada y el flujo
con dispositivos simulados se ejecutan de nuevo como parte de esta rama. Durante
la integración, los eventos pendientes se conservan entre consultas del mismo
ciclo y se descartan al iniciar un ciclo nuevo para impedir acciones de una sesión
anterior.

## Resultados

| Comprobación | Resultado observado |
| --- | --- |
| Pruebas propias | 97 pruebas aprobadas: 95 unitarias y 2 de integración con el modelo local |
| Ruff y formato | Sin errores; 26 archivos Python verificados |
| Dependencias | `pip check` sin conflictos; una sola distribución OpenCV |
| Separación de capas | Importación de contratos, procesador y entrenador sin cargar Qt, NumPy, OpenCV, MediaPipe ni PyAutoGUI |
| Modelo real | Inferencia local correcta sobre imágenes vacías, sin eventos ni coordenadas de control |
| Fotografías oficiales de prueba | Índice reconocido y 21 puntos; lateralidad física derecha conservada con y sin espejo |
| Deslizamientos a cadencia de vídeo | Ambos sentidos reconocidos con puntos simulados a 25, 30 y 60 FPS; no activan después palma quieta ni repiten el inicio |
| Gestos propios | 20 muestras, validación de consistencia y ambigüedad; reconstrucción desde puntos canónicos y cambio de espejo aprobados |
| Entrega de eventos | Inicio, mantenimiento y fin en orden, una sola vez; 128 eventos pendientes sin pérdida; historial conservado en el ciclo del proveedor |
| Datos de control | Coordenadas normalizadas, presencia explícita y desplazamiento vertical acumulado entre consultas; pérdida y caducidad invalidan puntos y deltas |
| Estados | Disponibilidad de cámara independiente de presencia de mano; inicio, pérdida, errores y cierre expuestos por resultados y propiedades del proveedor |
| Cierre | Recursos liberados en fallos; lectura bloqueada invalida el control y comunica timeout sin cerrar recursos desde dos hilos; error comunicado antes de un cierre nativo bloqueado |
| Vista previa | Desactivada por defecto, imágenes copiadas, descarte al desactivar o detener |
| Demo de entrenamiento | Flujo de captura, validación y reconocimiento probado con cámara y puntos simulados |
| Paquete distribuible | Wheel construido; adaptadores, contratos, modelo y licencia incluidos; SHA-256 del modelo verificado |
| Coexistencia con aplicación/dominio | 159 pruebas y 35 subpruebas aprobadas en copia de `c0d8c96`: 97 propias y 62 de aplicación/dominio y contrato Windows de I2 |
| Coexistencia con Windows | 127 pruebas aprobadas en copia de `81bab63`: 97 propias y 30 existentes; PyAutoGUI simulado |
| Coexistencia con SQLite | 115 pruebas aprobadas en copia de `ce09895`: 97 propias y 18 existentes |
| Integridad de otras áreas | Se probaron copias independientes de las ramas publicadas; no se modificaron UI, aplicación, dominio, persistencia ni acciones de Windows |

Las comprobaciones se ejecutaron en copias temporales separadas, superponiendo únicamente visión y sus pruebas a cada rama. Las cifras incluyen las mismas 97 pruebas propias y no deben sumarse entre sí. La revisión de dominio seleccionó las tres suites `test_member2_application.py`, `test_member2_domain.py` y `test_member2_windows_contract.py`. La comprobación de Windows usa PyAutoGUI simulado; no mueve el mouse ni prueba interacción real con otras aplicaciones. La coexistencia por rama no equivale a una fusión final ni a la conexión completa del flujo de cámara a acciones.

La cobertura automatizada observada en la verificación inicial fue 83 % incluyendo la herramienta de diagnóstico, cuya prueba de flujo se ejecutó aparte. La cobertura no mide precisión de reconocimiento ni rendimiento del equipo.

Las pruebas de índice, pellizco, dos dedos, palma, puño, deslizamientos y posturas propias utilizan puntos de mano simulados. La fotografía oficial verifica el índice con MediaPipe real. Esto comprueba la lógica del reconocedor, pero no acredita que todos los gestos se detecten de forma fiable con una webcam, distintas manos e iluminación.

## Los cinco ajustes solicitados para integración

| Solicitud | Entrega |
| --- | --- |
| Mantener `ProveedorVision` responsable de obtener resultados de cámara | Se conserva el protocolo y `obtener_resultado()`; exportación pública en `holocontrol.ports.vision` y adaptación en `AdaptadorVision` |
| Incluir coordenadas, presencia, desplazamiento vertical y metadatos de gestos | `posicion_indice`, `mano_detectada`, `desplazamiento_vertical` y eventos con nombre, fase, confianza, instante y duración |
| Entregar eventos acumulados en orden y sin pérdidas entre consultas | Cola FIFO de todas las fases, sin descartes por antigüedad, pérdida de mano o límite de 64; drenado único bajo `Condition` |
| Exponer disponibilidad de cámara, pérdida, error y detención del trabajador | `EstadoVision`, `estado`, `en_ejecucion`, `camara_disponible`, mensajes y estados `INICIANDO`, `CAMARA_DISPONIBLE`, `DETENIENDO`, `DETENIDO` |
| Independencia de las acciones del sistema | Sin imports ni llamadas a ejecutores, PyAutoGUI o control de mouse; prueba aislada de límites de importación |

Los eventos acumulados son historial de reconocimiento. Una pérdida, error, caducidad o cierre no recupera coordenadas anteriores ni autoriza esos eventos para ejecutar acciones. El consumidor valida estado, vigencia y generación. La guía de arquitectura distingue `eventos` de `eventos_actuales` y documenta la consulta con un solo coordinador.

## Revisión de deslizamientos

La revisión adicional reprodujo un fallo a 25, 30 y 60 FPS simulados: mover la palma reiniciaba tanto la espera de quietud como el temporizador de estabilización. Así, un deslizamiento continuo de 200 ms podía no emitir ningún evento, aunque superara el desplazamiento requerido.

Se separaron los dos temporizadores. El deslizamiento necesita mantener la postura abierta durante al menos 100 ms; moverla solo reinicia los 800 ms exigidos para una palma o un puño quietos. Nueve casos adicionales cubren ambos sentidos a tres cadencias, la quietud de palma y puño después de moverse, y el rechazo de un deslizamiento que cambia de postura antes de 100 ms. Todas las pruebas pasan.

Estas cadencias son tiempos de fotogramas simulados; no representan FPS medidos con una cámara real.

## Ramas revisadas

| Rama remota | Estado revisado |
| --- | --- |
| `develop` | Estructura inicial, `4d4ede9` |
| `feature/domain-model` | Aplicación, entidades, validaciones y catálogo, `c0d8c96`; publica `FuenteReconocimiento` basado en callbacks y DTO `Reconocimiento` |
| `feature/sqlite-repository` | SQLite, esquema, repositorio de perfiles y pruebas, `ce09895` |
| `feature/windows-actions` | Ejecutor, controlador de clic y validación de seguridad, `81bab63` |
| `feature/ui-dashboard` | Prototipo PySide6, `87f9dbe`; preferencias y gestos, sin conexión al motor |

La interfaz utiliza los nombres visibles Índice extendido, Pellizco, Pellizco sostenido, Dos dedos, Mano abierta y Deslizamiento. Corresponden a `indice`, las fases/duración de `pellizco`, `dos_dedos`, `palma_abierta` y los dos deslizamientos. El puño genera la solicitud adicional de cambiar modo aprobada para esta entrega.

El coordinador debe convertir la mano del perfil (`Derecha`/`Izquierda`) a `Lateralidad` y los porcentajes de umbral a valores entre 0 y 1. `factor_suavizado` es la mezcla con el punto nuevo: 1 significa sin suavizado y valores pequeños suavizan más; la conversión del control de la UI corresponde a aplicación. La sensibilidad y zona calibrada se aplican al mapear a la pantalla.

### Compatibilidad con el catálogo de dominio publicado

La revisión citada es histórica. El catálogo del dominio integrado asigna `dos_dedos` a desplazamiento vertical y conserva `subir`/`bajar` como acciones de scroll fijo. Esta integración no altera esas asignaciones.

El identificador compartido para la palma es `palma_abierta`. Los gestos sin
asignación en el catálogo actual permanecen sin acción; esta integración no les
asigna una semántica nueva.

Para el nuevo `Perfil`, la mano puede convertirse mediante `Lateralidad(perfil.mano_dominante.value)` y la cámara mediante `ConfiguracionCamara(indice=perfil.configuracion.indice_camara)`. Los 400 ms de `tiempo_espera_gesto_ms` pertenecen a la espera entre acciones del perfil; no sustituyen automáticamente los 100 ms de estabilización del reconocedor.

`Reconocimiento.desde_vision` conserva los eventos, el desplazamiento vertical,
el estado y los tiempos del resultado. La aplicación aplica actualmente su propio
suavizado además del aplicado por visión; la decisión pendiente se documenta en
`domain-vision-integration.md`.

## Fusión de configuración compartida

La interfaz y visión añaden contenido en las mismas secciones de `pyproject.toml`; una fusión automática de esos dos archivos produce dos conflictos de texto. Se entrega `docs/architecture/vision-integration-pyproject.toml` como referencia ya resuelta: conserva QtAwesome y los recursos de la interfaz, usa una sola distribución OpenCV e incluye el modelo local y su licencia.

La referencia no se aplica a los archivos ni a la rama de la interfaz. El integrante de integración puede conservar esos bloques al fusionar ambas ramas. El resto del código de visión se mantiene en rutas independientes de las nuevas rutas de UI. El cambio compartido de esta rama solo incorpora la dependencia de visión y su empaquetado.

## Comprobación pendiente con webcam

La prueba inicial de cámara 0 terminó con `ErrorCamara` y liberó el dispositivo. Esa comprobación no encontró dispositivos de clase Camera/Image disponibles en el entorno. OpenCV sí incluye los backends DirectShow y Media Foundation de Windows.

La revisión con una webcam conectada debe ejecutar:

```powershell
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --duracion 30
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --entrenar mi_postura --duracion 30
```

Las metas de 25 FPS, p95 gesto–acción inferior a 150 ms y 90 % de reconocimiento requieren pruebas reales con usuarios y el flujo integrado. No se declaran alcanzadas. Las cifras de la prueba con cámara simulada no representan rendimiento real.
