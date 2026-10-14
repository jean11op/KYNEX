# Kinex

Interfaz de escritorio en Python y PySide6. El diseño usa el estilo de la
referencia de control gestual: negro, azul, vista de mano y paneles compactos.

## Abrir

```powershell
python -m pip install PySide6
python run.py
```

En VS Code también puedes abrir `run.py` y pulsar **Run Python File**.

## Funciones de interfaz

- Inicio con perfil activo, controles de inicio/pausa/detención y modo cursor/dibujo.
- Vista ilustrativa de una mano; cámara y reconocimiento indicados como desconectados.
- Crear, editar, seleccionar y eliminar perfiles, con confirmación y validación de nombres.
- Preferencias persistentes por perfil: sensibilidad, suavizado, umbral, gestos y voz.
- Asistente de calibración de cinco pasos; guarda preferencias, nunca inventa una calibración válida.
- Asignar/activar gestos y atajos, validar conflictos y restaurar valores predeterminados.
- Lienzo manual: color, grosor, deshacer, borrar y exportar PNG.
- Diagnóstico sin datos falsos; no se simulan métricas de rendimiento.
- Tema oscuro, claro, del sistema o alto contraste, texto ajustable y vista opcional.
- Bandeja: minimizar, restaurar, consultar estado, pausar y salir.
- Atajo de pausa configurable **dentro de Kinex**; no es un atajo global de Windows.
- Configuración de frases de voz y límite de dictado; no se abre el micrófono.

Las asignaciones se guardan con **Guardar asignaciones**. Los formularios de
apariencia/ventana se guardan con **Guardar configuración**. El perfil activo
se muestra en Inicio. Los cambios aún no guardados en formularios no se transfieren
al seleccionar otro perfil.

## Límites de integración

No se implementan cámara, visión artificial, reconocimiento, control del ratón,
calibración medida, audio, autenticación ni sincronización. El inicio, entrenamiento,
prueba de gestos y reanudación permanecen deshabilitados hasta conectar sus módulos.
El dibujo actual usa mouse; el motor podrá integrarse después con el lienzo.

La persistencia de UI usa QSettings (`Kinex/Interface`, usuario local de Windows).
Es un adaptador provisional, separado en `presentation/preferences.py`, para que
el integrante de persistencia lo sustituya por sus repositorios. No son cuentas.
Se conserva `holocontrol` como paquete interno para evitar romper imports del equipo.

La bandeja requiere una sesión gráfica de Windows. Si no está disponible, se usa
la minimización normal. Minimizar no cambia el estado del control. El botón X sale;
la opción de configuración de bandeja se refiere al botón de minimizar.

## Validación

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests/ui -v
Remove-Item Env:QT_QPA_PLATFORM
```

Pruebas de navegación, perfil, aislamiento, persistencia, conflictos, calibración,
voz, temas y lienzo. La bandeja real necesita comprobación manual en Windows.

Ver `docs/ui-requirements.md` para la correspondencia con los documentos y
`docs/asset-provenance.md` para la procedencia de la imagen ilustrativa.
