# Plan hacia el MVP público — Bashkar Station

Versión 1 del 14 de noviembre de 2026, **aprobada el 14-nov**. Se basa en
[ESTADO_MVP.md](ESTADO_MVP.md) y en las respuestas del responsable del proyecto.

## Avance (15-nov-2026)

Rama `mvp/bloque-a-datos`, sin publicar en GitHub. Suite completa en verde en
cada commit.

| Hito | Estado | Commit / evidencia |
|---|---|---|
| A0 Reconstruir el proyecto | Hecho | `8b6d595`, `806c59d` |
| A1 Todas las entidades en SQLite | Hecho | `cd0cad0` |
| A2 TEI con entidades, ids estables | Hecho | `ab26d58` |
| A3 Metadatos reales en exportaciones | Hecho | `f456caf` |
| A4 Grafo sin reabrir | Hecho | `78d6576` |
| A5 Una sola fuente de entidades | Hecho | `5150468` |
| A6 Reprocesar y verificar cifras | Hecho | `99cf337`; [docs/verificacion_corpus_estampa.md](docs/verificacion_corpus_estampa.md) |
| B1 Rescatar de Drive y archivar | Hecho | `f504996`; ZIP verificado fuera del repositorio |
| B2 Sesión 74 y paquete E-RIHS | Hecho | `f504996` |
| B3 DERECHOS.md y avisos | Parcial: falta el enlace de cada número en la BNC y el aviso en la *pre-release* | `23a8916` |
| B4 LICENCIAS_DE_TERCEROS.md | Hecho | `23a8916` |
| B5 Modelos sin licencia | En curso: candidato con licencia Apache-2.0 (GLiNER multi v2.1) y hoja de anotación a ciegas lista; falta anotarla | — |
| B6 Encuadre institucional y cifras | Hecho | `598cde4` |
| C1 README de instalación | Hecho | `494569a` |
| C2 instalar.py con el lock, solo CPU | Hecho | `494569a` |
| C3 Verificación en Windows limpio sin GPU | Hecho en este equipo (clon limpio, Python 3.12, CUDA oculta: instalación 6 min 42 s, recorrido E2E 9/9). Falta que corra el trabajo `instalacion_limpia` de la CI, que exige publicar la rama | `494569a` |
| C4 CI semanal | Corregida; se confirma al correr en GitHub | `494569a` |

**Decisión tomada por defecto el 15-nov** (el responsable pidió seguir sin
responder): la segmentación oficial es la v1 sobre texto normalizado, que da
las 639 unidades publicadas; el escritorio pasó a usarla por defecto.

## Decisiones ya tomadas

| Tema | Decisión |
|---|---|
| MVP | Opción (c): demo pública de solo lectura con *Estampa* + instalación para usuarios avanzados |
| Corpus | Enero–mayo de 1939: 5 números, 792 páginas, 639 unidades editoriales. Junio, después del lanzamiento |
| Derechos | Hay autorización de la BNC. La *pre-release* se queda. La demo muestra imágenes y transcripciones |
| Historial de git | No se reescribe |
| Instituto Caro y Cuervo | «Mentor de la beca, sin afiliación» (fórmula del documento E-RIHS del 14-oct) |
| Usuario típico | Windows sin GPU. Por defecto, solo CPU; CHURRO y los motores GPU son complementos opcionales |
| CHURRO-3B | No se distribuye; cada quien lo descarga desde su origen y acepta su licencia |
| Copias | Se muestran las diferencias, usted decide, la de Drive se archiva en ZIP y queda solo `C:\dev` |

## Comprobaciones hechas antes de escribir este plan (solo lectura)

**Tamaño del repositorio.** `.git` ocupa 23 MB y clonar desde GitHub tarda 3,7 s.
Los ZIP de la *pre-release* (~293 MB) no se descargan al clonar. **El historial no
dificulta clonar ni instalar**, así que no hace falta ninguna alternativa.

**Diferencias de la copia de Drive frente a `C:\dev`.** Drive no tiene commits
propios: está 4 commits atrás de `origin/main`. Fuera de git tiene:

| Elemento | Qué es | ¿Está en `C:\dev`? | Mi sugerencia |
|---|---|---|---|
| `paneles/resultados.py` «modificado» | Solo cambian los finales de línea (CRLF); el contenido es idéntico a su commit | Sí, en una versión más nueva | Nada que rescatar |
| `docs/e-rihs-2026-evidence/` | Paquete E-RIHS | Sí, idéntico byte a byte | Nada que rescatar |
| `vision_ocr/muestras_corpus/Corpus_ESTAMPA_1939_muestra.docx` | Documento del 7-oct (81 KB, 882 párrafos): muestra de 5 páginas por número, de ene a may, con transcripción y tipología editorial | **No** | **Rescatar**: parece material de referencia para el benchmark |

**Dónde están las cifras equivocadas.** «973 páginas» no aparece en el repositorio.
«Enero–junio» aparece en dos sitios de código: un texto de ejemplo en
`app.py:3416` y **un valor fijo en `core/excel_export.py:262`**, que escribe
«Corpus: enero–junio 1939» en todo Excel exportado, sea cual sea el corpus. Es
el mismo tipo de fallo que el 3 y se corrige con él.

## Cómo se trabaja cada hito

- Cada hito es un commit (o pocos) con un **criterio de aceptación verificable**.
  No se marca como hecho sin ejecutar ese criterio y dejar la salida.
- Todo fallo corregido lleva una prueba que **falla antes** del arreglo y **pasa
  después**; se muestran las dos ejecuciones.
- Suite completa en verde antes de cada commit (el *hook* tarda unos 5 minutos).
- `git push` solo con su confirmación, como hasta ahora.
- **Costo de IA del plan completo: USD 0.** El reprocesado del corpus parte de las
  transcripciones de Vision OCR que ya están en `vision_ocr/salida/`: no se vuelve
  a hacer OCR pagado. El NER corre en local. Si algún hito necesitara llamar a una
  API, se estimará el costo y se le pedirá confirmación antes.

---

## Bloque A — Corrección de datos (va antes que todo)

**A0. Reconstruir el proyecto *Estampa* completo en `C:\dev`.**
El proyecto procesado de 792 páginas quedó en el equipo anterior (Lenovo). Se
reconstruye a partir de lo que ya está en el repositorio: las transcripciones de
`vision_ocr/salida/` y las imágenes de la *pre-release*.
*Criterio:* existe un `.bashkar` con 5 números y 792 páginas con texto, y
`cli.py --info` lo confirma. Se guarda una copia de seguridad antes de procesar.

**A1. Fallo 1: guardar todas las entidades, no una por artículo**
(`core/project_manager.py:330-337`).
*Criterio:* una prueba de integración con las 161 entidades reales de la muestra
de abril de 1939 guarda, reabre y encuentra **161 en la tabla `entidades` y 161 en
el `.bashkar`**. Una segunda prueba cubre artículos con muchas entidades y
entidades repetidas en varios artículos. Las dos fallan con el código actual.

**A2. Fallo 2: el TEI con sus entidades, e identificadores de artículo estables.**
Hoy el NER indexa por **título**, y dos artículos con el mismo título (secciones
fijas como «Moda») se confunden. Se adopta un único identificador estable por
artículo, compartido por la segmentación, el NER, SQLite y el TEI.
*Criterios:* (1) el TEI de la muestra contiene las 161 entidades
(`persName`/`placeName`/`orgName` y `standOff`); (2) `validar_tei()` **falla** si
el proyecto tiene entidades y el TEI sale con cero; (3) una prueba con dos
artículos del mismo título conserva entidades distintas para cada uno.

**A3. Fallo 3: metadatos reales en las exportaciones.**
La cabecera del TEI toma título, publicación, período, institución y herramientas
de los datos del proyecto. Solo declara IA si se usó, con el proveedor real
registrado en la proveniencia. La institución usa la fórmula de mentoría, sin
afiliación. Se aplica también al encabezado del Excel (`excel_export.py:262`).
*Criterio:* en dos proyectos distintos (*Estampa* y otro inventado en la prueba),
el TEI y el Excel muestran sus propios metadatos. Ninguna exportación contiene
«spaCy + Claude», «Corpus Estampa» ni «enero–junio» si no corresponde a los datos.

**A4. Fallo 4: el grafo se activa al guardar un proyecto nuevo.**
`guardar_proyecto()` asigna `ST.ruta_db`, y los errores de sincronización con
SQLite se registran en el log en vez de tragarse con `except: pass`.
*Criterio:* prueba de GUI sin pantalla: crear proyecto → NER → guardar → fundir
entidades canónicas, **sin reabrir**, produce entidades canónicas. Otra prueba
fuerza un error de SQLite y comprueba que queda en el registro de errores.

**A5. Una sola fuente para las entidades.**
SQLite pasa a ser la fuente única. El índice NER del `.bashkar` se deriva de ahí
al cargar, y los proyectos antiguos (que solo traen el índice en JSON) se migran
la primera vez que se abren, con copia de seguridad, como ya se hace de v10 a v11.
*Criterios:* el panel NER, el grafo canónico y el TEI muestran el mismo total de
entidades del mismo proyecto; un `.bashkar` antiguo de prueba se abre, se migra y
conserva todas sus entidades.

**A6. Reprocesar los 5 números y verificar cifras completas.**
Segmentar → NER → grafo → TEI → BibTeX/CSV con el código corregido, desde las
transcripciones existentes.
*Criterio:* un informe `docs/verificacion_corpus_estampa.md` con cifras medidas,
no escritas a mano: 792 páginas; unidades editoriales (se espera 639, y **cualquier
diferencia se explica antes de aceptar el hito**, no se ajusta a la cifra);
entidades totales iguales en SQLite, el `.bashkar`, el grafo canónico y el TEI;
el TEI pasa la validación.

**Estimación del bloque A: 5–6 días.**

---

## Bloque B — Derechos, licencias y copias

**B1. Rescatar de Drive y archivarla.**
Rescatar lo que usted decida de la tabla de arriba, comprimir la carpeta de Drive
en un ZIP con fecha, verificar el ZIP abriéndolo (comparando cantidad de archivos
y suma de verificación) y solo entonces dejar `C:\dev` como única copia.
*Criterio:* ZIP íntegro verificado; memoria y `CLAUDE.md` apuntan solo a `C:\dev`.
**La carpeta de Drive no se borra**; si quiere retirarla después del ZIP, me lo
indica.

**B2. Subir la entrada de la sesión 74 y el paquete E-RIHS.**
Se añade junto a la página de *Estampa* del paquete una nota de autorización de
la BNC.
*Criterio:* commit en `main` con `CHANGELOG.md` y `docs/e-rihs-2026-evidence/`,
incluida la nota; gitleaks sin hallazgos nuevos.

**B3. `DERECHOS.md` y avisos visibles.**
Aviso de procedencia con crédito a la BNC y la frase acordada («las imágenes y los
textos de *Estampa* se publican con autorización de la Biblioteca Nacional de
Colombia»), con enlace a la fuente de cada uno de los 5 números. El aviso va en
`DERECHOS.md`, el README, la descripción de la *pre-release* y la demo (bloque D).
La redacción es **provisional** hasta el hito E2.
*Criterio:* los 5 enlaces abren el registro correcto en la BNC; el aviso aparece
en los cuatro lugares. *Necesito de usted:* los enlaces de cada número en la BNC,
si los tiene; si no, los busco en el catálogo y se los presento para confirmar.

**B4. `LICENCIAS_DE_TERCEROS.md`.**
Cada modelo y dependencia con su licencia, su origen y si se distribuye, se
descarga al instalar o es opcional. Incluye las dependencias de Python del *lock*,
Tesseract, Poppler, los modelos de Hugging Face, el modelo de spaCy (que se
descarga al instalar y no va en el repositorio), CHURRO (no se distribuye) y los
motores GPU.
*Criterio:* un script compara el archivo con `requirements.lock.txt` y la lista de
modelos del código, y avisa si falta alguno; se ejecuta en la CI.

**B5. Sustituir o rotular los modelos sin licencia declarada.**
Evaluar un equivalente con licencia para el NER (candidato a verificar:
`PlanTL-GOB-ES/roberta-base-bne-capitel-ner`) y para el análisis de sentimiento.
*Criterio:* comparación sobre las mismas páginas de *Estampa*, con la referencia de
NER que defina el hito. Si un sustituto iguala o mejora la calidad, reemplaza al
modelo y este queda como opcional. Si no, el modelo actual queda **opcional y
desactivado por defecto**, con una advertencia visible en la interfaz y en el
README. La decisión se documenta con las cifras.

**B6. Encuadre institucional y cifras del corpus en toda la documentación.**
Fórmula de mentoría en README, CITATION.cff, `.zenodo.json`, NOTICE, manual y
créditos. «Enero–mayo de 1939, 5 números, 792 páginas, 639 unidades editoriales»
en todos los textos.
*Criterio:* una búsqueda en el repositorio no encuentra «enero–junio», «973» ni
fórmulas de afiliación al ICyC, salvo en el CHANGELOG histórico.

**Estimación del bloque B: 4–5 días.**

---

## Bloque C — Instalación (Windows sin GPU por defecto)

**C1. README de instalación para usuarios avanzados.**
Cómo descargar el código (ZIP o `git clone`), instalar Python 3.12 (versión exacta
y por qué), crear y activar el entorno virtual, instalar, arrancar y comprobar con
`--diagnostico`. CHURRO y los motores GPU se documentan aparte como complementos
opcionales.
*Criterio:* alguien que no participó sigue el README tal cual, sin ayuda, y llega
al primer TEI exportado (se verifica en E3).

**C2. `instalar.py` coherente con `requirements.txt`.**
Añadir los 8 paquetes que hoy faltan (`anthropic`, `google-generativeai`,
`accelerate`, `wordcloud`, `python-louvain`, `spylls`, `fastapi`, `uvicorn`),
instalar desde el *lock* con versiones fijas, usar **torch solo CPU** por defecto,
y no terminar con `EOFError` cuando no hay consola.
*Criterio:* prueba automática que compara la lista del instalador con
`requirements.txt`; tras instalar, el mismo chequeo de importaciones de esta
sesión da 0 faltantes; código de salida 0.

**C3. Verificación en un Windows limpio sin GPU.**
Este equipo es Windows 11 Home: no tiene Windows Sandbox. Se usan dos vías
complementarias: (1) un trabajo de CI en un runner de Windows de GitHub (máquina
nueva y sin GPU) que instala siguiendo el README y ejecuta el recorrido completo
de la GUI de esta sesión; (2) en este equipo, un clon nuevo con un perfil de
usuario aislado y la GPU oculta (`CUDA_VISIBLE_DEVICES=""`).
*Criterio:* las dos vías completan crear proyecto → OCR → segmentar → NER → grafo
→ TEI → guardar y reabrir, sin errores y con las cifras del bloque A.

**C4. Reparar la CI semanal.**
Excepción acotada de gitleaks para `vis-network.min.js` y arreglo de la
instalación del *lock* en el runner.
*Criterio:* una corrida programada lanzada a mano termina en verde.

**Estimación del bloque C: 3–4 días.**

---

## Bloque D — Demo pública de solo lectura

Sitio estático generado por un script del repositorio
(`scripts/generar_demo.py`), sin servidor ni base de datos, publicado en GitHub
Pages. Se puede regenerar desde el proyecto reprocesado en A6.

**D1. Generador y modelo de datos.**
*Criterio:* el script produce el sitio desde el `.bashkar` y su `.db`; las cifras
que muestra el sitio coinciden con el informe de A6; una prueba lo verifica.

**D2. Números y páginas: imagen junto a la transcripción.**
Imágenes en tamaño web (estimado: ~150 KB por página, ~120 MB en total; dentro del
límite de 1 GB de GitHub Pages).
*Criterio:* las 792 páginas se pueden abrir; cada una muestra imagen,
transcripción, número y enlace a la fuente en la BNC.

**D3. Unidades editoriales y entidades.**
Lista de las 639 unidades con su sección y sus entidades, e índice de entidades
con las unidades donde aparecen.
*Criterio:* los totales coinciden con A6; una entidad elegida al azar enlaza a
todas sus apariciones.

**D4. Grafo de conocimiento.**
Visualización de la red de entidades canónicas, con enlace a cada unidad.
*Criterio:* se carga en menos de 5 s en un portátil sin GPU; los nodos coinciden
con `entidades_canonicas`.

**D5. Descargas y avisos.**
TEI, CSV y BibTeX del corpus; aviso de derechos (B3) y de licencias (B4) en cada
página; enlace al instalador para usuarios avanzados.
*Criterio:* el TEI descargado pasa `validar_tei()` y trae las entidades; el aviso
es visible sin desplazarse en la portada.

**D6. Publicación y revisión.**
*Criterio:* la URL pública funciona en Chrome, Edge y Firefox, y en un teléfono;
no hay enlaces rotos (comprobación automática); se mide el tiempo de carga de la
portada.

**Estimación del bloque D: 7–8 días.**

---

## Bloque E — Lanzamiento

**E1. Versión y DOI.**
Versión nueva (propuesta: 14.0, porque cambia el formato de las entidades en A5),
coherente en `gui_comun.py`, `app.py`, README, CITATION.cff y `.zenodo.json`;
*release* en GitHub, que genera el DOI de versión en Zenodo.
*Criterio:* el DOI resuelve a la versión nueva y la cita del README coincide.

**E2. Ajuste del aviso de derechos a la autorización de la BNC.**
*Depende de usted:* el documento de autorización. Se ajustan `DERECHOS.md`, el
README, la *pre-release* y la demo al alcance, el crédito exigido y las condiciones
de reutilización por terceros.
*Criterio:* cada condición del documento queda reflejada en el aviso, en una tabla
condición → texto → lugar donde aparece, que usted revisa.

**E3. Prueba con investigadores externos.**
Una o dos personas usan la demo y siguen la instalación avanzada sin ayuda, y
anotan dónde se traban.
*Criterio:* completan la tarea definida (encontrar una entidad, descargar el TEI,
instalar y procesar un PDF propio); todo bloqueo que reporten queda corregido o
documentado antes de E4. *Depende de usted:* conseguir a esas personas.

**E4. Anuncio.**
*Criterio:* README con enlace a la demo y al DOI; texto de anuncio revisado por
usted.

**Estimación del bloque E: 2–3 días de trabajo, más una semana de calendario para E3.**

---

## Estimación total y calendario propuesto

**20–25 días de trabajo.** Es más que los 15–22 del diagnóstico. Retirar
contenido ya no hace falta, pero eso solo ahorraba horas. En cambio entraron
trabajos nuevos: unificar las entidades (A5), reconstruir el proyecto (A0),
evaluar modelos sustitutos (B5), las licencias de terceros (B4) y la verificación
en CI (C3).

Calendario a un ritmo realista de 3–4 días efectivos por semana, con la pausa de
fin de año:

| Semana | Fechas | Trabajo |
|---|---|---|
| 1 | 16–20 nov | A0–A4 |
| 2 | 23–27 nov | A5–A6 (cifras verificadas del corpus) · B1–B2 |
| 3 | 30 nov–4 dic | B3–B6 |
| 4 | 7–11 dic (8-dic festivo) | Bloque C |
| 5 | 14–18 dic | D1–D3 |
| 6 | 21–23 dic | D4 |
| — | 24 dic–11 ene | Pausa (festivos) |
| 7 | 12–15 ene 2027 (11-ene festivo) | D5–D6 · arranca E3 (necesita la autorización BNC para E2) |
| 8 | 18–22 ene 2027 | E1–E4 · **lanzamiento propuesto: viernes 22 de enero de 2027** |

A ritmo de tiempo completo (5 días por semana) cabría antes de la pausa, hacia el
18 de diciembre, siempre que el documento de la BNC y las personas para E3 estén
disponibles a tiempo.

**Lo que depende de usted y marca la ruta crítica:** su decisión sobre el `.docx`
de Drive (B1), los enlaces de la BNC (B3), el documento de autorización (E2) y los
investigadores para la prueba (E3).

---

## Después del lanzamiento

- Número de junio de 1939: procesarlo y ampliar el corpus (y la demo) a enero–junio.
- Ejecución real de PERO-OCR de punta a punta (nunca se ha ejecutado en este equipo).
- Instalable para Windows con asistente (opción a), sobre las correcciones de este plan.
- Referencia humana del benchmark de OCR y calibración de los umbrales de `config/ocr.toml`.
- Probar el dictado de la referencia humana con voz real.
- Elegir un solo backend web (`api/` o `servidor_web.py`) y retirar el otro.
- No crear proyectos vacíos automáticamente al abrir la app.
- Ocultar o rotular las categorías NER que el modelo no produce (obras, eventos).
- Kraken y soporte formal de Python 3.14.
- Menores: `--port` de la API, voseo en tres mensajes, aviso de `fitz` obsoleto,
  acciones de GitHub en Node 20, actualizar `CLAUDE.md` y `docs/PROJECT_STATE.md`.
- `.exe` con GPU (3,6 GB) para equipos con NVIDIA.
