# PresentationExecuter — Plan de Implementación

## Context

El usuario necesita una herramienta desktop para usar videos como presentaciones.
El flujo es: cargar video → definir checkpoints de pausa → en modo presentación,
el video se pausa automáticamente en cada checkpoint y `Space` reanuda hasta el siguiente.
Soporte para múltiples proyectos (video + lista de checkpoints guardados en JSON).

**Outcome esperado**: App funcional con gestor de proyectos, editor de checkpoints y modo presentación fullscreen.

---

## Stack Tecnológico

| Componente | Elección | Razón |
|---|---|---|
| Lenguaje | Python 3.10+ | Cross-platform, ecosistema rico |
| UI Framework | **PyQt6** | Nativa, potente, buena integración con VLC |
| Video | **python-vlc** | Maneja cualquier formato, control ms-level |
| Persistencia | JSON files | Simple, human-readable, sin servidor |

```
pip install PyQt6 python-vlc
```

---

## Estructura del Proyecto

```
PresentationExecuter/
├── main.py                    ← Entry point (XInitThreads + QApp + VLC Instance)
├── requirements.txt
├── PLAN.md                    ← Este archivo
├── projects/                  ← Auto-creado, almacena .json de cada proyecto
└── src/
    ├── __init__.py
    ├── models/
    │   └── project.py         ← Dataclass Project + load/save JSON
    ├── widgets/
    │   ├── video_widget.py    ← VLC embebido en QFrame
    │   └── timeline_bar.py    ← QSlider con marcas de checkpoints
    └── windows/
        ├── project_manager.py ← Ventana principal: lista de proyectos
        ├── editor.py          ← Editor: video + añadir/quitar checkpoints
        └── presenter.py       ← Fullscreen: reproducción con pausas automáticas
```

---

## Formato JSON de Proyecto

```json
{
  "name": "Mi Presentación",
  "video_path": "/ruta/absoluta/al/video.mp4",
  "checkpoints": [10.5, 25.3, 45.0, 67.8],
  "created_at": "2026-03-27T10:00:00",
  "updated_at": "2026-03-27T10:05:00"
}
```

Los checkpoints se guardan en **segundos (float)**. Internamente se convierten a ms para comparar con `vlc.MediaPlayer.get_time()`.

---

## Gotchas Críticos

| # | Problema | Solución |
|---|---|---|
| 1 | Crash X11 threading | `XInitThreads()` como primera línea absoluta de `main.py` |
| 2 | Deadlock en callbacks VLC | Nunca usar `event_attach()` para lógica de UI — solo QTimer polling |
| 3 | `winId()` inestable | `attach_vlc_window()` via `QTimer.singleShot(100, ...)` post `show()` |
| 4 | VLC captura Space/ESC | `video_set_key_input(False)` + `video_set_mouse_input(False)` |
| 5 | `pause()` es toggle | Usar `set_pause(1)` / `set_pause(0)` — determinísticos |
| 6 | `get_length_ms()` = -1 al inicio | Configurar timeline solo cuando state → `Playing` por primera vez |
| 7 | Feedback loop slider↔VLC | `user_dragging` flag + solo seek en `sliderReleased` |
| 8 | Checkpoint pasa desapercibido | Lookahead 50ms + seek al frame exacto post-pause |

---

## Instalación y Uso

```bash
# Instalar dependencias
pip install PyQt6 python-vlc

# Ejecutar
python main.py
```

### Flujo de uso:
1. **New Project** → elegir nombre y video → se abre el editor
2. En el editor: reproduce el video y presiona **"Add Checkpoint Here"** en los momentos donde quieres que se pause
3. Guarda el proyecto (Ctrl+S)
4. En el Project Manager, selecciona el proyecto y presiona **Present**
5. En presentación: `Space` / `Tab` para avanzar al siguiente checkpoint, `ESC` para salir
