# HoloControl-Access
Aplicación de control accesible de Windows mediante gestos de las manos

## Ejecutar en Windows

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m holocontrol.bootstrap
```

Al pulsar **Iniciar**, se busca una cámara con imagen: primero el índice del
perfil y después los índices 0 a 3. En **Configuración → Dispositivos** puedes
elegir un índice manual (0 a 5); la selección se conserva y se aplica al siguiente
inicio. Una selección manual no cambia automáticamente a otra cámara.

Un perfil sin calibración abre la vista previa real y mantiene detenido el control
del ratón. Abrir la cámara no calibra el perfil. Los perfiles calibrados usan el
flujo de control existente. Pausar, detener y cerrar liberan la cámara.
Los errores de inicio se muestran en un aviso y permiten volver a intentarlo.

## Calibrar y probar los gestos

1. En Perfiles selecciona la mano que vas a usar (derecha por defecto).
2. En Calibración pulsa **Abrir cámara para calibrar**. La vista muestra puntos
   reales y no activa acciones de Windows durante la medición.
3. Pulsa **Medir esquina superior izquierda (3 s)** y coloca la punta del índice
   en el extremo superior izquierdo de tu zona cómoda, según la imagen reflejada.
   Mantén toda la mano visible. Repite con **Medir esquina inferior derecha (3 s)**.
   La zona debe medir al menos el 10 % de la imagen en cada eje.
4. Pulsa **Guardar calibración** en cualquier paso. Sin mediciones nuevas, conserva la zona guardada o usa la zona inicial. Guarda sensibilidad y suavizado en SQLite.
   La medición se guarda en SQLite para el perfil seleccionado.
5. Vuelve a Inicio y pulsa **Iniciar**. El estado debe decir **Control activo**.

| Gesto | Cómo hacerlo | Acción predeterminada |
|---|---|---|
| Índice | Solo índice extendido; medio, anular y meñique doblados. Separa pulgar e índice y mueve lentamente la mano. | Mover cursor |
| Pellizco | Primero separa pulgar e índice; después junta sus puntas durante al menos 0,1 s y vuelve a separarlas. | Un clic izquierdo al cerrar; espera al menos 0,4 s entre clics |
| Dos dedos | Apunta el índice y el medio hacia arriba para subir o hacia abajo para bajar; cambia de gesto para detener. | Scroll continuo |
| Palma abierta | Cuatro dedos extendidos, pulgar separado del índice; deja la mano quieta durante unos 0,8 s. | Pausar y cerrar cámara; reanuda con Iniciar |
| Puño | Dobla los cuatro dedos y mantenlos quietos unos 0,8 s. | Minimizar ventana activa |
| Tres dedos | Índice, medio y anular extendidos; mueve la mano horizontalmente para recorrer ventanas y cambia de gesto para elegir. | Alt+Tab |
| Barrido lateral | Palma abierta; desplázala horizontalmente al menos un 20 % del ancho de la imagen en aproximadamente 0,1–0,5 s. | Sin acción por defecto; asigna una en Gestos |

Las asignaciones de la pantalla Gestos se guardan en el perfil real de SQLite.
Guardar cambios detiene el control: pulsa Iniciar para aplicarlos.
El control admite arrastre y cambio de ventanas con tres dedos.
Los identificadores históricos `subir` y `bajar` no los emite el reconocedor;
el desplazamiento funcional se realiza con dos dedos y movimiento vertical.

Los puntos desaparecen al perder seguimiento. Si se indica «Presenta la mano…»,
usa la mano seleccionada o cambia el perfil. La vista de puntos consulta una copia
del resultado sin consumir los eventos que el núcleo necesita para ejecutar acciones.

## Fluidez del control

Las acciones del ratón omiten la pausa automática de 100 ms de PyAutoGUI por
llamada, conservando su FAILSAFE y el intervalo entre clics del control gestual.
La consulta y ejecución de acciones se realizan fuera del hilo de Qt. Hay como
máximo una consulta en curso; se lee el resultado reciente del proveedor en lugar
de encolar posiciones antiguas. Pausar y detener se serializan con las acciones.
Las pruebas comprueban que una acción lenta no bloquea la actualización de cámara
ni los eventos de Qt, y que un fallo detiene el control y permite reintentar.

El control de gestos funciona en un trabajador independiente de la ventana, incluso minimizada. Las coordenadas del cursor usan píxeles físicos para respetar el escalado de Windows.
