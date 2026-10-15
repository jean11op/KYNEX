# Propuesta de contrato: visión y Windows Actions

**Estado:** especificación para revisión del equipo. No define todavía una interfaz
compartida ni afirma que los módulos estén integrados.

## Contratos comprobados

En `feature/windows-actions`, `ActionExecutor` expone movimiento en píxeles, clic
izquierdo/derecho y scroll entero. `WindowsActionExecutor` implementa ese puerto y
añade ciclo de vida y handlers de gesto propios. El control y el enfriamiento de
Windows deben seguir protegiendo el adaptador.

En `feature/vision-gestures`, `ProveedorVision` inicia un trabajador y entrega
`ResultadoVision` mediante consulta. El resultado contiene estado, coordenadas
normalizadas, desplazamiento normalizado y cero o más eventos con nombre, fase,
confianza y tiempo monotónico en milisegundos. `AdaptadorVision.detener()` devuelve
si el hilo terminó.

En `feature/domain-model`, `FuenteReconocimiento` entrega por callback un
`Reconocimiento` por fotograma. El DTO actual contiene generación, tiempo
monotónico en segundos, presencia de mano, un identificador de gesto, confianza y
coordenadas normalizadas. No contiene fases de eventos ni desplazamiento vertical.
`AplicacionControl` procesa ese DTO y coordina perfiles, calibración, estados y
`EjecutorControl`. `AdaptadorEjecutorExistente` traduce el protocolo español a los
métodos ingleses del ejecutor Windows.

## Contrato recomendado para acordar

1. **Observaciones y eventos.** Mantener `ProveedorVision` como productor y usar
   un adaptador que lo consulte y entregue datos al contrato de aplicación. Para
   no perder varios inicios/fines acumulados entre consultas, acordar que el DTO
   de aplicación incluya una colección ordenada de eventos con identificador,
   fase y confianza. El estado por fotograma puede seguir incluyendo coordenadas
   y presencia de mano. No colapsar `INICIO` y `FIN` en un único `id_gesto`.
2. **Pérdida de mano.** Todo estado sin resultado válido debe llegar como
   `mano_detectada=False`, sin posición ni inicio de gesto; los fines pendientes
   se conservan. Errores de cámara/procesamiento se notifican como fallo del
   proveedor para que la aplicación pause el control. `DETENIDO` por cierre
   solicitado no es un fallo.
3. **Scroll.** El DTO debe transportar `desplazamiento_y` (positivo hacia abajo,
   cero sin acción), o el equipo debe acordar una conversión explícita a acciones
   discretas. La primera opción conserva mejor `desplazamiento_indice` de visión;
   el dominio debe validar magnitud y limitar el valor antes de llamar a
   `ActionExecutor.scroll(int)`.
4. **Tiempo y generación.** Convertir `instante_ms` monotónico a segundos con
   `instante_ms / 1000`. El adaptador captura la generación recibida al iniciar
   una sesión y la adjunta a cada entrega. Al detener o reiniciar, invalida esa
   generación y descarta callbacks tardíos. El consumidor sigue rechazando datos
   vencidos y fuera de orden.
5. **Nombres y asignaciones.** Acordar un catálogo compartido antes de habilitar
   acciones: `palma_abierta` frente a `palma`; `dos_dedos` está asignado a clic
   derecho en dominio, pero visión lo usa para desplazamiento vertical; visión
   también produce `puno` y deslizamientos horizontales que el catálogo de dominio
   no registra. No inferir acciones a partir del nombre sin una asignación activa
   del perfil.
6. **Suavizado.** El DTO actual de dominio describe `x/y` como coordenadas crudas
   y aplica calibración/suavizado en aplicación. Para evitar filtrar dos veces,
   enviar el punto crudo del índice (`mano.puntos[8]`) o acordar que aplicación
   consuma `posicion_indice` y desactive su propio suavizado. Dominio debe decidir
   cuál es la fuente de verdad.
7. **Ciclo de vida y errores.** `FuenteReconocimiento.iniciar(generacion, ...)`
   necesita la generación de aplicación, pero `iniciar_control()` requiere saber
   que la cámara está disponible y el proveedor actual inicia de forma asíncrona.
   Dominio y visión deben acordar un handshake de preparación/disponibilidad antes
   de activar acciones. Si `detener()` devuelve `False`, el adaptador debe
   notificar fallo y la aplicación debe mantener el control pausado/detenido.

La aplicación debe ser la única autoridad de asignaciones y deduplicación de
gestos. El adaptador no debe llamar a PyAutoGUI. Debe invocar el `ActionExecutor`
solo a través de la aplicación (`AplicacionControl` → `EjecutorControl` →
`AdaptadorEjecutorExistente` → `WindowsActionExecutor`). El equipo debe decidir
si el cooldown del ejecutor es una barrera adicional fija o si el servicio de
aplicación será la única política de espera; no mantener dos configuraciones
independientes.

## Responsables y cambios mínimos

| Responsable | Decisión o aporte mínimo |
| --- | --- |
| Integrante 3 — visión | Confirmar semántica/dirección de desplazamiento, orden de eventos pendientes, estados de error y cierre del proveedor. No ejecutar acciones del sistema. |
| Integrante 2 — dominio | Extender `Reconocimiento` y `AplicacionControl` para eventos ordenados y desplazamiento, acordar catálogo/aliases, y definir handshake de cámara. Ajustar `FuenteReconocimiento` si necesita resultado de parada o disponibilidad. |
| Integrante 5 — Windows e integración | Tras integrar los contratos compartidos, implementar el adaptador pull→callback, etiquetar generación, traducir unidades/estados y mapear fallos. Mantener `ActionExecutor` como puerto de acciones. |

## Estructura de integración prevista

Cuando las ramas estén reunidas mediante el flujo Git acordado por el equipo, el
adaptador puede vivir en `infrastructure/vision/` como adaptador de
`ProveedorVision` a `FuenteReconocimiento`. Reutilizará los modelos publicados;
no copiará DTOs ni creará un segundo coordinador. `bootstrap.py` compondrá el
proveedor, el adaptador, `AplicacionControl` y `AdaptadorEjecutorExistente`.

Pruebas del adaptador deben usar proveedor y receptor simulados para validar
conversiones, eventos múltiples, pérdida de mano, generación vieja, fallo y
timeout de cierre. Una prueba de flujo debe verificar la cadena hasta un
`ActionExecutor` falso con PyAutoGUI simulado. La prueba manual con cámara solo se
realiza después, con el control inicialmente detenido y acciones verificadas en
una aplicación inocua.

## Dependencias de configuración

La configuración actual de Windows y dominio declara `opencv-python`; visión
declara `opencv-contrib-python`. El proyecto combinado debe instalar una sola
distribución OpenCV y conservar las dependencias de PySide6, MediaPipe y PyAutoGUI.
La distribución también debe incluir el modelo local de MediaPipe y sus avisos de
licencia según la configuración de empaquetado documentada por visión.
