# PROJECT_STATE — Bashkar Station

Última verificación: **7-sep-2026**, antes de migrar del PC Lenovo a un MSI.
Comprobado en esta sesión, no recordado.

## Estado funcional

Aplicación de escritorio (Python 3.11+ / Tkinter) para análisis editorial
computacional de publicaciones periódicas históricas digitalizadas en español.
Corre **100% offline** tras la instalación; solo son opcionales y en línea la
descripción de imágenes con IA y la extracción de metadatos desde URL.

- `python -m pytest -q` → **1.587 pasan, 27 saltadas, 0 fallan**. Medido dos
  veces el 7-sep-2026: **6 min 01 s** en disco local (`C:`) y **6 min 33 s**
  desde Google Drive (`I:`). El disco pesa poco aquí, ~9%.
- Caso real: corpus de ***Estampa*** (1930-1940), Instituto Caro y Cuervo.
- Estado del código en sesión **66** (3-sep-2026).

> ⚠️ La sección 8 de `CLAUDE.md` decía "sesión 14, 499 tests" — quedó
> desactualizada 52 sesiones. Corregida hoy. Si vuelves a ver una cifra que no
> cuadra con `pytest`, gana `pytest`.

### Generalización fuera de *Estampa* (medido, sesión 66)

Primera medición real sobre 9 publicaciones de la BNC:

- **8 de 9 traen la capa oculta de Paper Capture.** El acoplamiento al formato
  de la BNC es menos grave de lo que sugería leer el código.
- **La fusión de palabras ya no es problema** en ningún corpus (máx. 0,26%): el
  umbral relativo de la sesión 65 funcionó para todos.
- **La fragmentación varía de 2,6% a 35,6% y nada la detecta ni la reporta.**
  Umbral empírico propuesto de abstención: por encima de ~10% el documento no es
  utilizable sin revisión. **No implementado.**
- ***El Día*** declara capa oculta pero solo tiene 2 de 16 páginas OCR-izadas:
  la ruta debe decidirse **por página y por presencia real de texto**, nunca por
  la declaración de la fuente.
- ***El Gráfico*** (el contraste principal del plan de beca) es la única sin
  capa de texto, y está bloqueada porque **Tesseract no tenía el español
  instalado**.

## Arquitectura

Ver `CLAUDE.md` sección 4, que es la referencia detallada y está al día.
En resumen: `app.py` (GUI Tkinter, ~14.500 líneas), `core/` (motores: OCR,
NER, embeddings, estilometría, TEI, zonas), `datos/` (capa SQLite,
`schema.py`), `exportadores/`, `conocimiento/`, `lib/`, `tests/`.

Formato de proyecto: un `.bashkar` (JSON) **más un SQLite hermano**. Desde v11
el texto **no vive en el JSON** sino en el SQLite, y las correcciones manuales
del usuario están en la tabla `normalizaciones`, no en `ocr` (que solo guarda
salida de motores). Confundir esas dos tablas fue la causa de un bug real.

## Comandos

```bash
python instalar.py     # dependencias y modelos (Tesseract, Poppler, spaCy)

Ejecutar.bat           # arrancar la app (Windows)
./ejecutar.sh          # Linux/macOS
python app.py          # directo

python -m pytest -q    # 1.587 pruebas, 27 saltadas, ~6 min
check.bat              # CI local: py_compile app.py + ruff + pytest
```

**Empaquetado:** `bashkar_station.spec` (PyInstaller) → `dist/`.
Recordar `--clean` y, tras compilar, copiar `dist/` a "Para usar en cualquier
PC/" y crear el acceso directo (`crear_acceso_directo.ps1`).

## Dependencias externas

- **Tesseract OCR** — ⚠️ necesita el paquete de idioma **español** instalado
  aparte; su ausencia bloqueó *El Gráfico* en la prueba de generalización
- **Poppler** (render de PDF) · **spaCy** + modelo español
- **BERT-Spanish / RoBERTa** y **CHURRO** (transformers + torch, offline)
- **FAISS** (embeddings y búsqueda semántica)
- **Kraken 7.0.2** — instalado en `D:\kraken_env` ⚠️ **esa unidad no existirá
  en el MSI**
- **Ollama** (opcional) · **API de Claude** (opcional, para Vision y NER)

## Variables de entorno

Ningún secreto vive en el repo. Las credenciales van a
`~/.bashkar/credenciales.json`, **nunca al proyecto**.

`HF_HUB_OFFLINE=1` no es configuración del usuario: el código la fija, y
**cuándo** la fija es crítico (ver limitación 1).

## Errores y limitaciones conocidas

1. **`HF_HUB_OFFLINE` fijado tarde = segfault sin traza.** `importlib.util.
   find_spec()` **ejecuta el módulo** con torch/transformers, así que fijar la
   variable "justo antes del import" ya es tarde. Causó un segfault
   (0xC0000005 / 139) sin stderr ni traza en CHURRO, y antes en
   `ner_roberta_local.py`. La lógica está **copiada en tres módulos**: si tocas
   uno, revisa los tres.
2. **La fragmentación de OCR no se detecta ni se reporta** (varía 2,6%-35,6%).
   El umbral de abstención propuesto (~10%) no está implementado.
3. **`core/identidad_articulo.py` está aislado a propósito.** Resuelve un bug
   real y medido —con el título como id, **21 de 138 artículos (15%) se pisaban
   en silencio**— pero adoptarlo en `app.py` cambia los ids de proyectos
   existentes y exige migración. Decisión aparte, no tomada.
4. **`app.py` tiene ~14.500 líneas y estado global.** Es la causa raíz
   reconocida de los bugs recurrentes. El refactor está pendiente.
5. **Kraken vive en `D:\kraken_env`** — ruta absoluta fuera del repo, en una
   unidad que no estará en el equipo nuevo.
6. **El repo vive en Google Drive**, pero medido cuesta poco: 6 min 01 s en
   disco local frente a 6 min 33 s desde `I:\` (~9%). Aun asi conviene el disco
   local, y sobre todo **no correr dos trabajos pesados a la vez sobre `I:\`**,
   que es donde Drive si se atasca.
7. Existe un clon en `C:\Users\Lenovo\Bashkar-Station`. Hoy estaba **23 commits
   atrasado** y su `origin` desactualizado lo hacía parecer "5 commits sin
   pushear" que en realidad ya estaban en GitHub. No trabajar en los dos.

## Último trabajo realizado

**Sesión 66 (3-sep-2026)** — cinco bugs reales, todos verificados contra datos
reales y no fixtures:

1. Los parches de colaboración salían **sin una sola corrección de OCR** (0 antes,
   169 después). Además guardaban solo los primeros 200 caracteres del texto y
   el receptor escribía ese recorte como texto completo.
2. El fixture de migración reproducía una forma que **ningún proyecto tuvo**: los
   12 tests existentes ejercitaban solo la rama embebida, nunca la que corre con
   un proyecto de usuario — justo donde vivía el fallo silencioso de la sesión 65.
3. **Contrato A1 (identidad de artículo)**: convivían nueve formas incompatibles
   de acuñar el id; el índice NER tenía 184 entidades y la exportación TEI
   asignaba 0. Y peor: 15% de los artículos se perdía en silencio.
4. **CHURRO reparado** (ver limitación 1).
5. Prueba de generalización sobre 9 publicaciones de la BNC (ver arriba).

**Sin commitear al llegar a esta sesión:** `PAPER_METODOLOGICO_ESQUELETO.md` con
la revista objetivo ya decidida (ver NEXT_STEPS). Se commitea hoy.
