# NEXT_STEPS — Bashkar Station

Estado al 9-sep-2026 (código en sesión 67).

## Siguiente tarea concreta

**Redactar el artículo.** Es lo único que ya no depende de que el software
haga nada más. La revista objetivo está confirmada, el esqueleto está en MLA y
con los resúmenes en tres lenguas, y la medición de *El Gráfico* —que era el
contraste que faltaba— ya está hecha.

De la bibliografía queda **una sola ficha**: Mollier. La tesis de 2018 lo cita
como "Mollier 2017" sin título, y la obra suya que encaja con ese uso es de
2015 (*Une autre histoire de l'édition française*, La Fabrique). O la tesis
citó mal el año o citó otra obra; hay que mirar su bibliografía en el
repositorio del Caro y Cuervo. **No inventar la ficha.**

~~Medir *El Gráfico* con Tesseract en español~~ — **HECHO el 10-sep-2026**,
los 85 archivos (82 números), no una cata de dos. 6.382 páginas, 196.947 tokens medidos, 0 errores. Copiados a disco local con
verificación de truncamiento (85/85 íntegros, abriendo la última página de
cada uno) y medidos con 4 páginas repartidas por ejemplar, en paralelo.

| | El Gráfico | Estampa (línea base) |
|---|---:|---:|
| Confianza Tesseract | 89,4 % | — |
| Fragmentación | **3,0 %** | 4,7 % |
| Fusión | **0,03 %** | 0,16 % |
| Números utilizables sin revisión | **99 %** (84 de 85) | — |

**El Gráfico es mejor que el corpus sobre el que está hecho todo el análisis
publicado del proyecto.** No necesita CHURRO (7 GB, ~34 min/página): el
contraste colombiano del plan de la beca se resuelve por la ruta barata.

Dos hallazgos que no se buscaban:

1. **La abstención evitó publicar una cifra falsa.** Marcó cinco números, pero
   **ninguno por texto degradado**: los cinco cayeron en la regla de muestra
   insuficiente (62-197 tokens frente a ~2.200 de media), porque *El Gráfico* es
   una revista gráfica y la muestra fija de cuatro páginas cayó en planas de
   fotografía de 5 a 40 tokens.

   Lo importante: el número que el primer informe daba como **el peor de la
   colección** —*ago 1919*, 17,89 % de fragmentación— resulta ser, con evidencia
   suficiente, **el mejor: 1,58 %**. Aquella cifra salía de 95 tokens. Sin la
   regla de muestra insuficiente habría entrado al informe de la beca como dato
   bueno.

   El arreglo no era el obvio: muestrear más páginas en los números largos
   arregla los de 221 y no hace nada por los de 101, porque el problema es
   **dónde** cae la muestra, no cuántas páginas tiene el ejemplar. El medidor
   amplía ahora la muestra hasta reunir los 200 tokens que `calidad_ocr` exige
   para opinar.
2. **Indicio de degradación con los años**: 2,8 % de fragmentación en los 74
   números de los 1910 frente a 4,4 % en los 11 de los 1920. No es una
   conclusión —son once números—, es una pregunta que vale la pena mirar: si se
   confirma, el corpus no es homogéneo en el tiempo y cualquier serie temporal
   sobre él necesita controlarlo.

   Tras corregir la muestra queda **un solo número** marcado en toda la
   colección: *may 1925*, 11,3 % de fragmentación. Ese parece degradado de
   verdad, y conviene mirarlo a ojo antes de incluirlo.

Reproducir: `scripts/_experimentos/generalizacion_20260903/`
(`medir_elgrafico_completo.py` mide con checkpoint reanudable,
`informe_elgrafico.py` resume).

~~Convertir las citas del paper de APA a MLA y ampliar el resumen a tres
lenguas~~ — **HECHO el 9-sep-2026**. Del paper queda solo lo que exige
consultar fuentes: ninguno de ficha: Rodríguez Morales (autor único), Bhaskar
(FCE, 2014, la traducción que citó la tesis) y Mollier (prólogo a *La colección*,
2017) quedaron verificados el 29-sep-2026 contra la bibliografía de la tesis de
2018; solo falta el rango de páginas del prólogo. Revista objetivo confirmada
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

2. ~~Detección de fragmentación y abstención~~ — **HECHO 10-sep-2026**,
   `core/calidad_ocr.py`. Umbral en 10 %, que no está calibrado contra ningún
   caso frontera: cae en el hueco vacío entre las cinco publicaciones
   aceptables (hasta 7,4 %) y las dos críticas (desde 20,8 %). Validado contra
   los nueve PDF reales: ninguno cruza de bando. Cableado en `cli.py` y en el
   worker de `app.py`.
3. ~~Ruta de OCR por página~~ — **HECHO 10-sep-2026**. `analizar_pdf` censa el
   documento entero en vez de las cinco primeras páginas y devuelve
   `modos_pagina`; `cli.py` y `app.py` enrutan página a página, y una página
   sin texto que tampoco se pueda OCR-izar se avisa y se omite en vez de
   escribirse vacía.
4. ~~Instalar el paquete español de Tesseract~~ — **HECHO 9-sep-2026**. Queda
   correr *El Gráfico*, que es ahora la tarea de arriba.
5. **Decidir si se adopta el contrato A1** (`core/identidad_articulo.py`) en
   `app.py`. Sigue siendo decisión de Fabián (D-07), pero el 10-sep-2026 se
   midió sobre el proyecto real (`Proyecto_04_Mar_2026.db`, el de las 183
   revisiones manuales) y ya no es una decisión a ciegas:

   - **Los 351 ids de la base son literalmente el título del artículo**,
     incluidos "Sin titulo" y cadenas de basura de OCR. Es exactamente el
     problema que A1 describe, confirmado sobre los datos de trabajo.
   - Adoptarlo cambiaría los 351 ids: el 100 %, no una parte.
   - Las tablas `entidades` (115 filas) y `ocr` (505) referencian el artículo
     por `articulo_id`, así que la migración tiene que reescribirlas a la vez.
   - **Faltaba un prerrequisito que ya está resuelto**: `pagina_inicio` estaba
     en NULL en las 351 filas, así que A1 producía ids `..._p0000_NN` —un
     contador global disfrazado de referencia bibliográfica, sin la estabilidad
     que el módulo promete. Arreglado (ver `rango_paginas`), pero la base
     existente necesita rederivar la página antes de migrar.

6. **Refactor de `app.py`.** Medido el 10-sep-2026 con AST, no a ojo: **21.487
   líneas, 794 funciones, 50 asignaciones a nivel de módulo**. Lo que pesa son
   los constructores de interfaz (`_build_cfg` 662 líneas, `_build_ling` 549,
   `_build_etz` 486, `_build_ocr` 426…), que son UI pura y moverlos no arregla
   nada. Lo que **sí** hay que sacar son las ~830 líneas de lógica con densidad
   de Tk casi cero que están atrapadas ahí dentro: `_construir_contexto_ia` +
   `_llamar_ia_texto` (129), `_bench_correr_ruta` (69), `_valid_calcular` (67),
   `_norm_render_pagina` (73), `_etz_redibujar_zonas` (103)…

   Esa lista ya dio su primer resultado: `_ocr_vision_multiproveedor` resultó
   ser una **copia divergente y peor** de `core.ocr_llm.ocr_con_vision` a la
   que llamaba la Ruta 2 —la que se paga—, sin el prompt calibrado, sin
   registrar el gasto y sin filtrar los rechazos del modelo. Eliminada. La
   conclusión operativa es que el refactor no es higiene: en este monolito,
   cada trozo de lógica duplicada es un sitio donde una mejora medida no llega
   al usuario.
7. **Roadmap FineReader**, con una línea menos:

   - ~~Detección de negrita/cursiva desde spans de PyMuPDF~~ — **cerrada con
     evidencia el 10-sep-2026**, y no como se esperaba. Ya estaba implementada
     en `alto_reconstructor` (los campos `bold` e `italic` de cada línea); lo
     que faltaba era un consumidor. Medido sobre las nueve publicaciones
     (`senal_tipografica.py`): **no vale la pena cablearla**. `italic` marca
     hasta el 26,6 % de las líneas de *Estampa* — es cómo el OCR clasificó la
     tipografía, no cursiva de la página. Y `bold` es preciso pero inútil: los
     títulos que señala son los que el umbral de tamaño ya detecta (11 de 11 en
     *Estampa*), así que no rescata ninguno, mientras que en *La Semana Cómica*
     marcaría 21 líneas que no son título. Volver a esto exigiría primero una
     verdad de referencia humana de títulos.
   - Diccionario de corpus para verificación de OCR ⭐⭐⭐⭐ — sigue siendo lo
     más valioso que queda del roadmap.
   - Mejora del detector de columnas con `HoughLinesP`.
   - Exportación DOCX con layout preservado.

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
