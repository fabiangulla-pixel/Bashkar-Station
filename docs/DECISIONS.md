# DECISIONS — Bashkar Station

Decisiones vigentes con su porqué. `CLAUDE.md` sigue siendo el contexto maestro
(reglas de oro, trampas del código, disciplina de trabajo); esto fija lo que ya
se decidió para que no se re-litigue.

---

### D-01 — Escritorio, offline, Tkinter
App de escritorio que corre 100% offline tras la instalación. Solo la
descripción de imágenes con IA y la extracción de metadatos por URL usan
internet, y son **opcionales**. El público objetivo trabaja con corpus
patrimoniales, muchas veces sin conexión fiable.

### D-02 — El código en disco manda sobre la documentación
Regla de la sección 0 de `CLAUDE.md`. Si `CLAUDE.md` y el repo discrepan, gana
el repo. **Hoy quedó demostrado:** la sección 8 decía "sesión 14, 499 tests"
mientras el repo iba por la 66 con 1.587.

### D-03 — Verificar contra datos reales, no contra fixtures
Los cinco bugs de la sesión 66 aparecieron todos así. El caso más claro: un
fixture reproducía una forma de proyecto **que ningún proyecto tuvo**, y los 12
tests de migración pasaban ejercitando solo la rama que nunca corre con un
proyecto de usuario. Un test verde sobre un fixture inventado no prueba nada.

### D-04 — Un test que "cubre" un módulo debe cubrirlo de verdad
El segfault de CHURRO reapareció porque la lógica está copiada en tres módulos y
el test que la guardaba cubría dos, mientras **su docstring daba por bueno el
tercero**. Desde entonces: prueba negativa verificada, no docstring optimista.

### D-05 — Texto en el SQLite, no en el `.bashkar` (desde v11)
Y las correcciones manuales del usuario van en la tabla `normalizaciones`
(numero, pagina, ocr_crudo, norm_usuario, ts_usuario), **no** en `ocr`, que solo
guarda salida de motores. Confundirlas hizo que los parches de colaboración
salieran vacíos.

### D-06 — Contrato A1: el id de artículo se deriva del contenido
`<numero>_p<pagina>_<orden>`, no de un contador global, para que reprocesar el
mismo PDF devuelva los mismos ids. Verificado: 138 de 138, cero colisiones.
**Por qué importa:** con el título como id y `ON CONFLICT DO UPDATE`, dos
artículos homónimos se pisaban en silencio — 21 de 138 perdidos (15%). Los que
se repiten son justo lo que se repite en una revista ("Especial para ESTAMPA").

### D-07 — `identidad_articulo.py` queda aislado hasta decidir la migración
Adoptarlo en `app.py` cambia los ids de proyectos existentes. Es una decisión
aparte, con migración, y **no está tomada**. No integrarlo por iniciativa propia.

### D-08 — El orden de import decide si el proceso vive o muere
`HF_HUB_OFFLINE` debe fijarse antes de **cualquier** cosa que toque
torch/transformers, y `importlib.util.find_spec()` cuenta como "tocar": ejecuta
el módulo. "Justo antes del import" ya es tarde. Regla general: sospechar de
`find_spec` con paquetes pesados.

### D-09 — La ruta de OCR se decide por página, no por la fuente
*El Día* declara capa oculta de Paper Capture y solo tiene 2 de 16 páginas
OCR-izadas. **Nunca confiar en la declaración de la fuente**: comprobar
presencia real de texto, página por página.

### D-10 — Sin triplestore aparte
El grafo de entidades y relaciones vive en el mismo SQLite del proyecto
(`entidades_canonicas`, `menciones_canonicas`, `relaciones`), como pedía el
encargo. Unicidad de tripletas por índice de expresión.

### D-11 — La capa DH es incremental y opt-in
Reutiliza el NER, el editor de anotaciones y el entity_linker existentes. **No
es una migración** del proyecto.

### D-12 — El roadmap de reorganización es dirección, no obligación
La propuesta de migrar a `modulos/` + `exportadores/` + `conocimiento/` se
decide con Fabián antes de mover nada.

### D-13 — Herramienta genérica, no específica de *Estampa*
Se decidió que Bashkar sea una herramienta genérica de análisis de publicaciones
periódicas históricas. La prueba de generalización de la sesión 66 sobre 9
publicaciones de la BNC es el primer paso medido en esa dirección.

### D-14 — Revista objetivo del paper: MLA, no APA *(2-sep-2026)*
*Literatura: teoría, historia, crítica* (Universidad Nacional de Colombia).
Confirmado por Fabián. Implica convertir las citas de APA a MLA y ampliar el
resumen a tres lenguas. Ver NEXT_STEPS.

### D-15 — Archivo de bloqueo de dependencias *(9-sep-2026)*
`requirements.txt` sigue declarando rangos `>=` (instala lo último compatible),
pero se agrega `requirements.lock.txt` con las versiones exactas verificadas en
verde. Motivo medido, no teórico: al montar el equipo MSI, pip resolvió
matplotlib 3.11, que eliminó el argumento `labels` de `boxplot`, y el gráfico de
confianza de OCR reventaba con el código intacto. Al actualizar dependencias a
propósito: correr la suite y regenerar el lock en el mismo commit.

### D-16 — El diccionario Hunspell español se instala, no se supone *(9-sep-2026)*
`spylls` empaqueta inglés, ruso y sueco, no español. Hasta hoy el corrector solo
miraba los datos internos de `spylls`, así que en cualquier máquina recién
instalada quedaba inerte **sin avisar**. Ahora `core/spell_corrector.py` busca en
`~/.bashkar/diccionarios/` (y en `BASHKAR_DICCIONARIO_ES`), `instalar.py` lo
descarga en el paso 2b y la verificación final lo reporta.

### D-17 — La CI local elige intérprete, nunca `python` a secas *(9-sep-2026)*
`check.bat` resuelve `BASHKAR_PYTHON` → venv activo → `.venv`/`venv` del repo →
PATH, y distingue "entorno mal montado" de "código roto". Antes, el hook
`pre-commit` lo invocaba desde `cmd.exe`, que no hereda el venv de la consola:
en el equipo nuevo eso daba "[FALLO] hay tests en rojo" sin haber corrido un
solo test.

### D-18 — La calidad del OCR se mide y el sistema se abstiene *(10-sep-2026)*
`core/calidad_ocr.py` es el único sitio donde se decide si un texto sirve. Tres
veredictos: `utilizable`, `revisar`, `no_utilizable`. El umbral de
fragmentación está en **10 %** y no está calibrado contra un caso frontera: cae
en el hueco vacío entre las cinco publicaciones aceptables de la BNC (hasta
7,4 %) y las dos críticas (desde 20,8 %). *Estampa*, el corpus sobre el que está
hecho todo el análisis publicado, queda dentro con margen, y hay un test que lo
exige: **un umbral que se abstenga de la línea base está mal puesto**.

Una muestra por debajo de 200 tokens nunca se declara `utilizable`; se marca
`revisar` diciendo que la muestra es insuficiente. Callarse ante poca evidencia
es el mismo fallo silencioso que el módulo existe para evitar.

Validado contra los nueve PDF reales, no solo con texto sintético
(`scripts/_experimentos/generalizacion_20260903/validar_calidad_ocr.py`):
ninguna publicación cruza de bando. Primer uso en producción, sobre los 82
números de *El Gráfico*: marcó dos números degradados que habrían entrado al
análisis sin que nadie se enterara.

### D-19 — La ruta de OCR se decide por página, y ejecutarlo así *(10-sep-2026)*
D-09 lo decidió en septiembre de 2026 y el código seguía sin hacerlo.
`ocr_engine.analizar_pdf` censa **todas** las páginas —`get_text` no rasteriza,
cuesta poco— y devuelve `modos_pagina`; `cli.py` y el worker de `app.py`
enrutan página a página. Una página sin texto embebido va a Tesseract; si
tampoco se puede OCR-izar, **se avisa y se omite**, nunca se escribe un `.txt`
vacío que la haga pasar por procesada. Las páginas rellenadas quedan con
`metodo="tesseract_relleno"` y `revision=True`.

### D-20 — El OCR por visión se implementa una sola vez *(10-sep-2026)*
En `core/ocr_llm.py`. `app.py` tenía su propia copia, y la Ruta 2 de la interfaz
—la que consume API de pago— llamaba a ella: sin el prompt calibrado contra el
juez de ground truth, sin registrar el gasto de IA, sin filtrar los rechazos del
modelo y devolviendo `""` en silencio ante un proveedor desconocido.
`tests/test_ocr_vision_sin_duplicado.py` impide que vuelva.

La lección general, que vale para el refactor pendiente de `app.py`: **cada
trozo de lógica duplicado dentro del monolito es un sitio donde una mejora
medida no llega al usuario.**

### D-21 — Los commits de este repo van de uno en uno *(10-sep-2026)*
El hook `pre-commit` corre la suite completa (4-5 min, más si la máquina está
ocupada). Lanzar dos `git commit` a la vez **no da error**: los dos hooks
corren, los dos dicen "todo en verde" y ninguno de los dos commits queda en el
historial. Se descubrió al ver que `git log` no había avanzado con los cambios
todavía en el árbol de trabajo. Encadenar commits en segundo plano: esperar a
que el anterior aparezca en `git log` antes de lanzar el siguiente.
