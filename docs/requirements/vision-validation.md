# Validación del módulo de visión de Kinex

Verificación inicial: 13 de octubre de 2026. Revisión de deslizamientos: 14 de octubre de 2026. Rama local: `feature/vision-gestures`. La revisión previa a publicación añade el manejo de errores de inicio y la compatibilidad de datos con el dominio en `f5f3e8d`.

La entrega se publica como rama de trabajo para integración, con validación real de webcam pendiente. La base es `origin/develop` en `4d4ede9`.

## Resultados

| Comprobación | Resultado observado |
| --- | --- |
| Pruebas propias | 72 pruebas aprobadas: 70 unitarias y 2 de integración con el modelo local |
| Ruff y formato | Sin errores; 23 archivos Python verificados |
| Dependencias | `pip check` sin conflictos; una sola distribución OpenCV |
| Separación de capas | Importación de contratos, procesador y entrenador sin cargar Qt, NumPy, OpenCV, MediaPipe ni PyAutoGUI |
| Modelo real | Inferencia local correcta sobre imágenes vacías, sin eventos ni coordenadas de control |
| Fotografías oficiales de prueba | Índice reconocido y 21 puntos; lateralidad física derecha conservada con y sin espejo |
| Deslizamientos a cadencia de vídeo | Ambos sentidos reconocidos con puntos simulados a 25, 30 y 60 FPS; no activan después palma quieta ni repiten el inicio |
| Gestos propios | 20 muestras, validación de consistencia y ambigüedad; reconstrucción desde puntos canónicos y cambio de espejo aprobados |
| Cierre | Recursos liberados en fallos; lectura bloqueada invalida el control y comunica timeout sin cerrar recursos desde dos hilos |
| Vista previa | Desactivada por defecto, imágenes copiadas, descarte al desactivar o detener |
| Demo de entrenamiento | Flujo de captura, validación y reconocimiento probado con cámara y puntos simulados |
| Paquete distribuible | Wheel construido; adaptadores, contratos, modelo y licencia incluidos; SHA-256 del modelo verificado |
| Compatibilidad Windows y dominio | 94 pruebas aprobadas en una copia temporal con Windows y el dominio publicados: las 72 propias, 20 existentes y 2 de conexión entre visión y ejecutor; conversión de perfil a configuración verificada |
| Integridad de otras áreas | El ejecutor del integrante 5 conserva el mismo objeto Git; no se modificaron UI, aplicación, dominio, persistencia ni acciones de Windows |

La comprobación de Windows usa PyAutoGUI simulado. No mueve el mouse ni prueba interacción real con otras aplicaciones. Su archivo conserva el objeto Git `5d595b2515b65825bbb3aeb61fad5adc1242e0dd`.

La cobertura automatizada observada en la verificación inicial fue 83 % incluyendo la herramienta de diagnóstico, cuya prueba de flujo se ejecutó aparte. La cobertura no mide precisión de reconocimiento ni rendimiento del equipo.

Las pruebas de índice, pellizco, dos dedos, palma, puño, deslizamientos y posturas propias utilizan puntos de mano simulados. La fotografía oficial verifica el índice con MediaPipe real. Esto comprueba la lógica del reconocedor, pero no acredita que todos los gestos se detecten de forma fiable con una webcam, distintas manos e iluminación.

## Revisión de deslizamientos

La revisión adicional reprodujo un fallo a 25, 30 y 60 FPS simulados: mover la palma reiniciaba tanto la espera de quietud como el temporizador de estabilización. Así, un deslizamiento continuo de 200 ms podía no emitir ningún evento, aunque superara el desplazamiento requerido.

Se separaron los dos temporizadores. El deslizamiento necesita mantener la postura abierta durante al menos 100 ms; moverla solo reinicia los 800 ms exigidos para una palma o un puño quietos. Nueve casos adicionales cubren ambos sentidos a tres cadencias, la quietud de palma y puño después de moverse, y el rechazo de un deslizamiento que cambia de postura antes de 100 ms. Todas las pruebas pasan.

Estas cadencias son tiempos de fotogramas simulados; no representan FPS medidos con una cámara real.

## Ramas revisadas

| Rama remota | Estado revisado |
| --- | --- |
| `develop` | Estructura inicial, `4d4ede9` |
| `feature/domain-model` | Entidades, validaciones y catálogo de dominio, `f5f3e8d`; todavía no publica contratos de visión ni coordinador de acciones |
| `feature/sqlite-repository` | Misma base; todavía no contiene persistencia adicional publicada |
| `feature/windows-actions` | Ejecutor y controlador de clic, `e27abd1` |
| `feature/ui-dashboard` | Prototipo PySide6, `87f9dbe`; preferencias y gestos, sin conexión al motor |

La interfaz utiliza los nombres visibles Índice extendido, Pellizco, Pellizco sostenido, Dos dedos, Mano abierta y Deslizamiento. Corresponden a `indice`, las fases/duración de `pellizco`, `dos_dedos`, `palma_abierta` y los dos deslizamientos. El puño genera la solicitud adicional de cambiar modo aprobada para esta entrega.

El coordinador debe convertir la mano del perfil (`Derecha`/`Izquierda`) a `Lateralidad` y los porcentajes de umbral a valores entre 0 y 1. `factor_suavizado` es la mezcla con el punto nuevo: 1 significa sin suavizado y valores pequeños suavizan más; la conversión del control de la UI corresponde a aplicación. La sensibilidad y zona calibrada se aplican al mapear a la pantalla.

### Compatibilidad con el catálogo de dominio publicado

La revisión posterior de `feature/domain-model` en `f5f3e8d` detectó una diferencia funcional: el catálogo de dominio asigna `dos_dedos` a clic derecho y reserva `subir`/`bajar` para scroll. El catálogo de visión aprobado por el usuario utiliza `dos_dedos` con desplazamiento vertical para scroll. No deben conectarse directamente esas asignaciones predeterminadas sin resolver esta diferencia con el integrante 2.

Visión entrega `palma_abierta`; el catálogo de dominio identifica esa postura como `palma`. El coordinador debe traducir ese identificador. Los gestos de puño, deslizamiento horizontal y cambio de modo aprobados para visión todavía no están registrados en ese catálogo de dominio. Su registro y asignación corresponden al integrante 2; esta entrega no modifica esos archivos.

Para el nuevo `Perfil`, la mano puede convertirse mediante `Lateralidad(perfil.mano_dominante.value)` y la cámara mediante `ConfiguracionCamara(indice=perfil.configuracion.indice_camara)`. Los 400 ms de `tiempo_espera_gesto_ms` pertenecen a la espera entre acciones del perfil; no sustituyen automáticamente los 100 ms de estabilización del reconocedor.

## Fusión de configuración compartida

La interfaz y visión añaden contenido en las mismas secciones de `pyproject.toml`; una fusión automática de esos dos archivos produce dos conflictos de texto. Se entrega `docs/architecture/vision-integration-pyproject.toml` como referencia ya resuelta: conserva QtAwesome y los recursos de la interfaz, usa una sola distribución OpenCV e incluye el modelo local y su licencia.

La referencia no se aplica a los archivos ni a la rama de la interfaz. El integrante de integración puede conservar esos bloques al fusionar ambas ramas. El resto del código de visión se mantiene en rutas independientes de las nuevas rutas de UI. El cambio compartido de esta rama solo incorpora la dependencia de visión y su empaquetado.

## Comprobación pendiente con webcam

La prueba real de cámara 0 terminó con `ErrorCamara` y liberó el dispositivo. No aparecen dispositivos de clase Camera/Image disponibles en este entorno. OpenCV sí incluye los backends DirectShow y Media Foundation de Windows.

La revisión con una webcam conectada debe ejecutar:

```powershell
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --duracion 30
.\.venv\Scripts\python.exe -m holocontrol.infrastructure.vision.demo --entrenar mi_postura --duracion 30
```

Las metas de 25 FPS, p95 gesto–acción inferior a 150 ms y 90 % de reconocimiento requieren pruebas reales con usuarios y el flujo integrado. No se declaran alcanzadas. Las cifras de la prueba con cámara simulada no representan rendimiento real.
