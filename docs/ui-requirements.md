# Interfaz Kinex: alcance y correspondencia documental

Se revisaron `HoloControl_Access_Requisitos_y_Modelo_BDvdvd.docx` y `reparticion (1).docx`.
La referencia visual define el estilo; las funciones corresponden a Kinex.
El pedido del usuario excluye implementar cámara y visión artificial.

| Requisitos | Entrega de UI | Integración pendiente |
|---|---|---|
| RF-UI-01–07 | Navegación, perfil, estado detenido y controles persistentes | Estado real, inicio y reconocimiento |
| RF-UI-08–14 | CRUD de perfiles, selección, nombre único, persistencia local | Repositorio definitivo del integrante 4 |
| RF-UI-15–21 | Asistente guiado, ajustes y repetición; calibración pendiente | Cámara, zona medida, prueba de cursor y confirmación real |
| RF-UI-22–27 | Asignaciones activables, umbral, atajos y conflictos, restauración | Captura/entrenamiento/prueba de reconocimiento |
| RF-UI-28–33, 35 | Bandeja, restaurar, estado textual, pausa, salida y aviso | Pausa/reanudación de motor real |
| RF-UI-34 | Atajo configurable con foco en Kinex | Atajo global del integrante de Windows |
| RF-UI-36–38 | Tema oscuro/claro/sistema/alto contraste y tamaño de texto | Validación de accesibilidad con usuarios |
| RF-UI-39–42 | Preferencias de ventana, avisos, estado de módulos | Enumeración de cámaras y telemetría real |
| RF-20, 20.1–20.3, 22 | Lienzo manual, color, grosor, deshacer, borrar, exportación; modo visible | Puntos de dibujo entregados por motor gestual |
| RF-14–15, 21 | Preferencias de frases y límite de dictado por perfil | Audio, escucha y confirmación de texto reconocido |
| RF-23–27 | Información de modo local y límites de sincronización | API de cuentas y aislamiento remoto; no se finge login |

## Fronteras de módulos

- `main_window.py`: ventanas, navegación, formularios y bandeja.
- `preferences.py`: preferencias locales provisionales; no define el esquema SQLite del equipo.
- `visuals.py`: ilustración estática, mapa editorial, dial y lienzo manual.
- `widgets.py`: iconos vectoriales.
- `assets/hand-demo.png`: imagen sintética, sin cámara ni detección.

Los puntos sobre la mano son coordenadas editoriales dibujadas para reproducir
el estilo de la referencia, no salidas de MediaPipe. Las métricas vacías son
intencionales. No se marcan cámara, mano ni control como activos.

El documento contiene tanto cuentas obligatorias como una sección posterior de
MVP local; esta UI sigue el MVP local, dejando el backend de cuentas pendiente.
No se implementan funcionalidades de otros integrantes para simular integración.
