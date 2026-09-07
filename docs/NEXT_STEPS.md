# NEXT_STEPS — Bashkar Station

Estado al 7-sep-2026 (código en sesión 66).

## Siguiente tarea concreta

**Convertir las citas del paper de APA a MLA y ampliar el resumen a tres
lenguas.**

Está *decidido*, solo falta ejecutarlo — es lo único de la lista que no depende
de ninguna otra cosa. Revista objetivo confirmada por Fabián el 2-sep-2026:
***Literatura: teoría, historia, crítica***, Departamento de Literatura,
Universidad Nacional de Colombia (ISSN 0123-5931 / 2256-5450).

Normas verificadas en `revistas.unal.edu.co/index.php/lthc/about/submissions`:

- **6.000-12.000 palabras**, referencias incluidas
- **Citación MLA, no APA** — el esqueleto actual usa `(Autor, año, p. XX)`,
  calibrado contra la tesis de 2018. Hay que convertirlo.
- Resumen en **español, inglés Y portugués** (máx. 150 palabras cada uno), no
  solo bilingüe como asumía el esqueleto
- 3-6 palabras clave · evaluación doble ciego · envío por OJS o correo
- Word editable, tablas y figuras **editables** (no imágenes), ≥300 dpi
- Licencia final CC BY-NC-ND 4.0

El detalle vive en `PAPER_METODOLOGICO_ESQUELETO.md`.

## Después

2. **Implementar la detección de fragmentación de OCR y su abstención.** Varía
   de 2,6% a 35,6% entre corpus y **nada la detecta ni la reporta hoy**. Umbral
   empírico propuesto: por encima de ~10%, el documento no es utilizable sin
   revisión. Es el hallazgo más accionable de la prueba de generalización.
3. **Decidir la ruta de OCR por página**, no por la declaración de la fuente
   (D-09). *El Día* lo demuestra: declara capa oculta y solo 2 de 16 páginas la
   tienen.
4. **Instalar el paquete español de Tesseract** y desbloquear ***El Gráfico***,
   que es el contraste principal del plan de la beca y la única publicación sin
   capa de texto.
5. **Decidir si se adopta el contrato A1** (`core/identidad_articulo.py`) en
   `app.py`. Arregla una pérdida real del 15% de artículos, pero cambia los ids
   de proyectos existentes y exige migración (D-07).
6. **Refactor de `app.py`** (~14.500 líneas + estado global): es la causa raíz
   reconocida de los bugs recurrentes. Pendiente desde hace muchas sesiones.
7. Roadmap FineReader: diccionario de corpus para verificación de OCR ⭐⭐⭐⭐,
   detección de negrita/cursiva desde spans de PyMuPDF, mejora del detector de
   columnas con `HoughLinesP`, exportación DOCX con layout preservado.

## Al llegar al MSI

- **Clonar a disco local** (`C:\dev\bashkar_station`), no trabajar desde `I:\`.
  Medido: 6 min 01 s en disco local frente a 6 min 33 s desde `I:\` (~9%).
  La ganancia real no es la suite, es no competir con la sincronizacion.
- **Kraken 7.0.2 está en `D:\kraken_env`** — esa unidad no existirá. Hay que
  reinstalarlo y actualizar la ruta.
- **Instalar Tesseract con el idioma español** (ver paso 4; ya bloqueó una
  medición).
- Correr `python instalar.py` para dependencias y modelos.
- Las credenciales van a `~/.bashkar/credenciales.json`, a mano. No al repo.
- Copiar `~/.bashkar/` completo: lleva `bashkar.db` y `auditoria_agente.jsonl`.
- Borrar o sincronizar el clon viejo de `C:\Users\Lenovo\Bashkar-Station` para
  no acabar trabajando en dos sitios (limitación 7).
