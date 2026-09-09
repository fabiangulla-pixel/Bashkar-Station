# NEXT_STEPS — Bashkar Station

Estado al 9-sep-2026 (código en sesión 67).

## Siguiente tarea concreta

**[EN PROGRESO] Medir *El Gráfico* con Tesseract en español.** 
Tesseract 5.4.0 + `spa.traineddata` ya funciona en el MSI (9-sep-2026). 
Prueba rápida en `ps20_elgrafico_dic_1910.pdf` (primeras 3 páginas):
  - Confianza media: 93.2%
  - Fusión: 0.1%
  - Fragmentación: 4.3%
  
El corpus de El Gráfico vive en 
`G:\Mi unidad\1_MAIA_UniAndes\Coursera\Despliegue de soluciones\Microproyecto\Publicaciones\El Gráfico`
con 82 números (1910-1929, 2.6 GB total).

*El Gráfico* es la única de las 9 publicaciones sin capa de texto oculta y el 
contraste principal del plan de la beca. Medición de muestra en progreso.

~~Convertir las citas del paper de APA a MLA y ampliar el resumen a tres
lenguas~~ — **HECHO el 9-sep-2026**. Del paper queda solo lo que exige
consultar fuentes: los nombres de pila de Rodríguez Morales y Sierra Restrepo,
y las fichas completas de Bhaskar y Mollier (en MLA el año va después del
título, así que la ficha APA de la tesis no basta). Revista objetivo confirmada
por Fabián el 2-sep-2026:
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
4. ~~Instalar el paquete español de Tesseract~~ — **HECHO 9-sep-2026**. Queda
   correr *El Gráfico*, que es ahora la tarea de arriba.
5. **Decidir si se adopta el contrato A1** (`core/identidad_articulo.py`) en
   `app.py`. Arregla una pérdida real del 15% de artículos, pero cambia los ids
   de proyectos existentes y exige migración (D-07).
6. **Refactor de `app.py`** (~14.500 líneas + estado global): es la causa raíz
   reconocida de los bugs recurrentes. Pendiente desde hace muchas sesiones.
7. Roadmap FineReader: diccionario de corpus para verificación de OCR ⭐⭐⭐⭐,
   detección de negrita/cursiva desde spans de PyMuPDF, mejora del detector de
   columnas con `HoughLinesP`, exportación DOCX con layout preservado.

## Migración al MSI — hecha el 9-sep-2026

- ✅ Clon local en `C:\dev\bashkar_station`, traído de GitHub (desde Drive iba a
  34 MB en 15 min; desde GitHub, 52 MB en un minuto).
- ✅ Entorno virtual en `C:\dev\venv-bashkar` con **Python 3.12.10**. No 3.14:
  ni gensim ni torch tienen ruedas ahí, y 3.14 es el Python por defecto del
  equipo, así que `python` a secas apunta al intérprete equivocado.
- ✅ Tesseract 5.4.0 + `spa.traineddata`. `winget` falló primero con
  `0x8a15005e` (certificado que no coincide); se resolvió forzando
  `--source winget`. Es la intercepción TLS de Norton, ya conocida aquí.
- ✅ Diccionario Hunspell es_ES y modelo `es_core_news_sm`.
- ✅ `BASHKAR_PYTHON` en el PATH de usuario, para que el hook `pre-commit`
  encuentre el intérprete correcto.
- ✅ `~/.bashkar/` llegó completo (`bashkar.db`, `credenciales.json`,
  `auditoria_agente.jsonl`).

### Pendiente de la migración

- **Kraken 7.0.2** no está instalado (vivía en `D:\kraken_env`, unidad que aquí
  no existe). Bloquea la ruta de OCR de manuscrito e impresión antigua.
- **Poppler**: verificar que esté en `C:\poppler`.
- **El `.exe`**: no hay `C:\Programas\BashkarStation` en este equipo. Hay que
  recompilar con `--clean` y rehacer el acceso directo.
- La copia de Drive sigue existiendo. **Trabajar solo en `C:\dev`**, no en los
  dos sitios a la vez (misma trampa que la limitación 7).
