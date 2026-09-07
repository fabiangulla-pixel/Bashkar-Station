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
