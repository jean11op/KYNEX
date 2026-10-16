# KYNEX
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
| Puño | Cierra la mano; mantenla cerrada durante 2 segundos. Funciona con cualquiera de las dos manos. | Minimizar una ventana, sin repetir al mantener el puño |
| Dos dedos | Apunta el índice y el medio hacia arriba para subir o hacia abajo para bajar; cambia de gesto para detener. | Scroll continuo |
| Palma abierta | Mantén los cuatro dedos extendidos durante 7 segundos continuos. Cambiar de gesto reinicia la cuenta. | Pausar control |
| Tres dedos | Índice, medio y anular extendidos; mueve la mano horizontalmente para recorrer ventanas y cambia de gesto para elegir. | Alt+Tab |
| Barrido lateral | Palma abierta; desplázala horizontalmente al menos un 20 % del ancho de la imagen en aproximadamente 0,1–0,5 s. | Derecha: subir volumen. Izquierda: bajar volumen. |

Las asignaciones de la pantalla Gestos se guardan en el perfil real de SQLite.
Guardar cambios detiene el control: pulsa Iniciar para aplicarlos.
El control admite arrastre y cambio de ventanas con tres dedos.
Los identificadores históricos `subir` y `bajar` no los emite el reconocedor;
la navegaci?n se realiza apuntando dos dedos en cuatro direcciones.

Los puntos desaparecen al perder seguimiento. Si se indica «Presenta la mano…»,
muestra cualquiera de las dos manos. La vista de puntos consulta una copia
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

Gestos adicionales:

- **Zoom:** con índice y medio extendidos, sepáralos o júntalos manteniendo el centro de la mano quieto. Cambia de gesto para volver a las flechas.
- **Dibujar/arrastrar:** con el índice extendido y los otros tres dedos doblados, abre el pulgar como para hacer clic y mantenlo abierto aproximadamente medio segundo. El botón permanece presionado mientras el pulgar siga abierto; escóndelo para soltar. El trazo sigue la palma y perder la mano también suelta el botón. Abrir y esconder el pulgar brevemente sigue haciendo un clic simple. Funciona con la mano seleccionada en el perfil; la otra mano se ignora. El movimiento de dibujo tiene menor amplificaci?n y suavizado adaptativo para reducir temblores.
- **Voz:** haz clic en un campo de texto y muestra el pulgar arriba (like), con los otros dedos doblados. Espera a que Windows indique que escucha y habla. Baja el gesto y haz otro like para detenerlo.
- El dictado usa la escritura por voz de Windows, necesita internet, micrófono y teclado en español (España o México). El audio se procesa mediante el servicio de Microsoft. La precisión depende del ruido, el micrófono y la pronunciación; no es infalible.
- **Scroll opcional (reasignable en Gestos):** en Canva, el scroll envía mensajes de rueda directamente a la ventana bajo el centro del editor, sin hacer clic ni pulsar flechas. El zoom usa Ctrl + rueda. Esta detección requiere que el título de la ventana incluya «Canva».
- **Puño:** usa el mismo umbral de confianza que el reconocedor (0,6) y minimiza la ventana activa tras 2 segundos continuos, una vez por cierre. Abrir la mano o perder seguimiento reinicia la cuenta. Reinicia HoloControl para cargar los cambios.

Referencia del dictado: https://support.microsoft.com/en-us/accessibility/windows/use-voice-typing-to-talk-instead-of-type-on-your-pc

Todos los comandos funcionan con cualquiera de las dos manos. Si aparecen ambas, se conserva la mano que controla; al iniciar, la preferencia del perfil decide cuál usar.

Controles de teclado:

- **Enter:** solo el meñique extendido; mantén el gesto medio segundo.
- **Escape:** índice y meñique extendidos, medio y anular doblados; mantén medio segundo.
- **Subir volumen:** palma abierta y barrido horizontal hacia la derecha de la imagen de cámara.
- **Bajar volumen:** palma abierta y barrido horizontal hacia la izquierda de la imagen.
- Cada gesto envía una pulsación. Cambia de postura antes de repetirlo. La palma abierta durante 7 segundos sigue pausando el control.
- Enter y Escape actúan sobre la aplicación que esté activa. El volumen corresponde al sistema.

- **Flechas:** apunta índice y medio juntos hacia arriba, abajo, izquierda o derecha. Mantener repite la tecla; bajar los dedos detiene las pulsaciones. Se aplican al elemento que tenga el foco.
- **Borrar:** extiende solo el meñique y apúntalo hacia la izquierda de la pantalla. El mismo dedo apuntando arriba hace Enter. Borra un carácter (o la selección); mantener 2 segundos adicionales selecciona todo y borra el contenido del campo activo. Suelta antes de repetir.
