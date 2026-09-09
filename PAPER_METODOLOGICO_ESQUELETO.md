# Nota de calibración de estilo (borrar antes de someter)

Calibrado contra: Gullaván Vera, Fabián Andrés. *La Biblioteca de Literatura Colombiana
de la editorial La Oveja Negra. Contribuciones para el estudio bibliográfico de
colecciones editoriales*. 2018. Instituto Caro y Cuervo, trabajo de grado,
https://bibliotecadigital.caroycuervo.gov.co/id/eprint/1337/.

Rasgos observados a replicar:
- Resumen en español + Palabras clave, luego Abstract + Key Words en inglés.
  ⚠️ La tesis de 2018 admitía 250 palabras; *Literatura: teoría, historia, crítica*
  exige **máx. 150 palabras** y **tres lenguas** (español, inglés, portugués).
- Voz mixta: mayoría "se + verbo" impersonal, con primera persona singular puntual
  cuando se describe una decisión metodológica propia ("para este estudio he
  realizado una matriz...", "no puedo dejar pasar...").
- Citas largas en bloque, sangradas, sin comillas.
- ⚠️ **Estilo de citación: MLA 9, no APA** (la tesis de 2018 usa APA; la revista
  objetivo exige MLA). Lo que cambia al escribir la prosa:
  - En texto: `(Apellido 23)` — apellido y número de página, **sin coma y sin año**.
    Con el apellido ya nombrado en la frase, solo el número: "Bhaskar sostiene (23)".
    Dos autores: `(Rodríguez Morales y Sierra Restrepo 5)`. Tres o más: `(Apellido et al. 5)`.
    Dos obras del mismo autor: `(Apellido, *Título abreviado* 23)`.
  - Sin fuente paginada (sitio, base de datos, salida de software): solo `(Apellido)`.
  - La lista final se rotula **Obras citadas**, no "Referencias", en orden
    alfabético y con sangría francesa.
  - Patrón de entrada MLA: Apellido, Nombre. "Título del artículo". *Título de la
    publicación*, vol. X, no. Y, año, pp. 00-00. *Base de datos*, URL o DOI.
- Notas al pie numeradas para digresiones/aclaraciones que no caben en el cuerpo.
- No hay sección rotulada "Metodología" aparte — el método se narra dentro de la
  prosa, en el punto donde se aplica ("Para este estudio bibliográfico he
  realizado una matriz en la que he consignado datos de interés...").
- Subtítulos temáticos descriptivos, no genéricos (no "Resultados" sino, p. ej.,
  "Cubiertas", "Otros aspectos de diseño y conclusiones previas").
- Cierre de sección con una síntesis interpretativa que conecta el dato material
  con la pregunta más amplia del campo editorial/histórico.

**Marco teórico secundario — decidido (2-sep-2026):** grupo generacional
**Los Nuevos** (revista homónima, Bogotá, 6-jun-1925 — junta editorial: Felipe
y Alberto Lleras Camargo, Rafael Maya, Germán Arciniegas, Eliseo Arango, José
Enrique Gaviria, Abel Botero, Jorge Zalamea, León de Greiff, Francisco Umaña
Bernal, José Mar, Manuel García Herreros, Luis Vidales; influencia de "Ariel"
de Rodó y de las ideas socialistas de posguerra; reacción contra el modernismo
y la generación centenarista). Fuente académica a citar:
Rodríguez Morales, [nombre de pila], y [nombre de pila] Sierra Restrepo. "Los Nuevos: entre la
tradición y la vanguardia". *Boletín Cultural y Bibliográfico*, vol. 42, no. 69,
2005, pp. 2-23,
https://publicaciones.banrepcultural.org/index.php/boletin_cultural/article/view/707
(también indexado en Dialnet y en la Biblioteca Virtual Miguel de Cervantes;
verificar acceso al PDF completo antes de citar página exacta. ⚠️ **Verificar
además los nombres de pila completos de ambos autores antes de someter**: la
entrada MLA los exige y aquí están reconstruidos a partir de las iniciales de
la referencia APA original, no confirmados contra la fuente).

**Puente real con el corpus (no fabricado — verificar antes de usarlo como
argumento fuerte):** los dos escritores literarios que dominan el índice de
personas de *Estampa* 1939 (Germán Arciniegas, 11 artículos, presente en los
5 números; León de Greiff, 7 artículos) fueron miembros fundadores de la
junta editorial de *Los Nuevos* en 1925. Catorce años después, en *Estampa*,
esa misma generación aparece ya consolidada como referencia cultural — puede
leerse como el momento en que el proyecto generacional de los años 20 se
volvió canon citable en la prensa ilustrada de circulación masiva, o como
continuidad de red social/editorial entre publicaciones. Esto SÍ requiere
lectura historiográfica propia (no basta con la coincidencia de nombres); el
esqueleto no la redacta por ti.

**Veta central del artículo — decidida (2-sep-2026):** el campo literario
(eje ya trabajado en `ENSAYO_ESTAMPA_BORRADOR.md`), leído ahora en diálogo
con Los Nuevos como antecedente generacional inmediato de esos mismos
nombres.

Lo que este esqueleto todavía NO puede resolver por ti (requiere tu criterio
de investigador): bibliografía crítica secundaria sobre *Estampa*/prensa
ilustrada colombiana 1930s más allá de Los Nuevos, y el argumento
historiográfico central completo del artículo (la relación entre Los Nuevos
y *Estampa* es una pista, no una tesis ya armada).

---

# [TÍTULO PROVISIONAL]

*Bashkar Station: infraestructura computacional para el estudio bibliográfico y
editorial de publicaciones periódicas históricas. El caso de* Estampa *(1930-1940)*

*(ajustar título — el de la tesis sigue el patrón "Objeto de estudio. Subtítulo
metodológico"; este esqueleto lo replica pero puede no ser el mejor título real)*

Fabián Andrés Gullaván Vera¹

¹ *(nota al pie: afiliación, financiamiento — Beca a Nuevos Investigadores en
Estudios Editoriales, MinCultura 2025; Instituto Caro y Cuervo)*

## Resumen
*(**máx. 150 palabras**, español — borrador de contenido, no de redacción final.
Las normas de la revista exigen que cubra cuatro cosas: propósito, desarrollo
lógico, punto de vista del autor y conclusiones.)*

- Objeto: revista *Estampa* (Colombia, 1930-1940), corpus de 5 números
  digitalizados por la Biblioteca Nacional de Colombia (ene-may 1939, 792
  páginas, ~567.000 palabras extraídas).
- Problema: el corpus digitalizado por la BNC no es directamente utilizable para
  análisis textual/bibliográfico a escala — capa OCR de baja calidad, sin
  reconstrucción de orden de lectura multi-columna, sin segmentación en unidades
  editoriales (artículo/publicidad/sección).
- Aporte: se presenta Bashkar Station, software desarrollado para resolver ese
  problema de forma reproducible y auditable, y se expone como caso de estudio
  el análisis del corpus completo de *Estampa* obtenido con él.
- Método: [síntesis de una frase de la cadena OCR→segmentación→NER→análisis, ver
  cuerpo].
- Hallazgo destacado: [elegir 1-2 hallazgos de contenido, no solo técnicos —
  ver banco de hallazgos abajo].

## Palabras clave
*(3-6, según normas de la revista; estas son 6, el tope)*
Humanidades digitales, prensa ilustrada colombiana, estudios editoriales,
reconocimiento de entidades nombradas, OCR histórico, *Estampa*.

## Abstract
*(**máx. 150 palabras**, inglés — traducir el resumen final una vez fijado en
español; no traducir antes de cerrar el texto en español, como se hizo en la
tesis de referencia)*

## Keywords
*(traducción de las palabras clave; conservar *Estampa* sin traducir)*

## Resumo
*(**máx. 150 palabras**, portugués — tercera lengua exigida por la revista, que
la tesis de 2018 no tenía. Traducir al final, junto con el Abstract, no antes.
Conviene revisión de un lector nativo o competente en portugués: es un resumen
que va publicado con la firma del autor.)*

## Palavras-chave
*(traducción de las palabras clave al portugués)*

---

## Introducción: [subtítulo temático — ver ejemplo de la tesis: "Introducción: estudiar una colección"]

Punto de partida narrativo sugerido (a redactar con tu marco teórico real):

- La tesis de 2018 abrió con Bhaskar (2014) y el problema de filtrado/enmarcado/
  amplificación de una colección editorial. Este artículo puede abrir de forma
  simétrica con el problema equivalente para la prensa periódica: ¿qué significa
  editar, diagramar y hacer circular una revista ilustrada semanal en la
  Colombia de los años 30? ¿Qué papel jugó *Estampa* en la construcción de un
  público lector de clase media urbana? — **[esto requiere tu marco teórico
  sobre historia de la prensa colombiana; no lo puedo redactar sin tus fuentes]**
- Puente metodológico propio de este artículo (a diferencia de la tesis de
  2018, que trabajaba con ejemplares físicos en mano): el corpus de *Estampa*
  solo existe en un archivo digital de calidad heterogénea. El estudio
  bibliográfico/material de una colección periódica exige aquí, como paso
  previo obligatorio, resolver el acceso computacional confiable al texto y al
  layout — ese es el problema que Bashkar Station ataca y que este artículo
  documenta como aporte metodológico para otros investigadores del campo.

---

## [Sección 1 — descriptiva, ver patrón "Cubiertas" de la tesis]
### El corpus y sus condiciones de producción digital

Contenido factual disponible (real, de la bitácora del proyecto):

- 5 números: enero-mayo 1939. Páginas por número: ene 138, feb 178, mar 89,
  abr 214, may 173 (total 792).
- Los PDF de la BNC están generados con Adobe Acrobat **Paper Capture**
  (fuente oculta `HiddenHorzOCR`) — el texto embebido no respeta el orden de
  columnas del layout de prensa.
- Diagnóstico empírico de calidad OCR sobre enero 1939 (138 páginas): solo 5%
  de páginas con OCR "bueno" (texto fluido), 62% "ilegible/fragmentado"
  (>70% líneas cortas) — dato para argumentar por qué el estudio bibliográfico
  de un periódico digitalizado exige una capa metodológica previa que la
  bibliografía material clásica no necesita con el objeto físico en mano.
- Consecuencia metodológica adoptada: **página como unidad atómica** de
  segmentación (no sub-segmentación intra-página), decisión documentada como
  hallazgo sobre las condiciones de producción del corpus, no como limitación
  técnica menor — *(este es exactamente el tipo de nota que tu tesis hace con
  el dato material: convertir una restricción técnica en evidencia sobre el
  objeto de estudio)*.
- Vision OCR (modelo de lenguaje multimodal) sobre las 792 páginas reales
  como ruta de mayor fidelidad frente a Tesseract/capa BNC — trade-off de
  costo vs. calidad documentado.

## [Sección 2]
### La cadena de reconstrucción: de la imagen a la unidad editorial

- Pipeline real: OCR (3 rutas: Tesseract propio / IA de visión / texto BNC +
  reconstrucción de líneas) → normalización (preserva arcaísmos ortográficos
  de los años 30, "habia", "fué", "á" — decisión deliberada, no corrección) →
  segmentación en unidades (artículo/publicidad/sección/colofón) → NER
  (6 categorías históricas: personas, organizaciones, lugares, obras, eventos,
  cargos).
- Resultado cuantitativo del corpus completo procesado — **cifra FINAL,
  30-ago-2026, corrida con RoBERTa real** (reemplaza una corrida previa con
  fallback spaCy que daba 11.688 entidades — no comparable, distinto motor):
  636 artículos segmentados, **7.652 entidades nombradas únicas**, exportación
  TEI P5 válida (636 elementos), **~36 min** de procesamiento sobre 792
  páginas (RoBERTa es más lento que spaCy pero mejor calidad de
  categorización).
- Nota metodológica sobre reproducibilidad y trazabilidad: cada unidad
  conserva metadatos de procedencia (número, página, método de OCR,
  confianza) — permite auditar la calidad del análisis por tramos del corpus,
  algo que el objeto físico analógico no ofrece de forma nativa.

## [Sección 3]
### Lectura distante del corpus: redes, encuadres y polaridad

*(esta es la sección más "de contenido histórico" y la que más depende de tu
interpretación — aquí van los datos, la lectura es tuya)*

- **Red de co-ocurrencia de entidades — cifra FINAL, corpus completo
  (30-ago-2026):** 300 nodos, 4.083 aristas, **8 comunidades, modularidad
  0.218**. *(Ojo: la cifra de 0.67 que circulaba en la bitácora venía de un
  análisis sobre un subconjunto curado de solo 43 nodos en sesión 36 — no es
  comparable con esta, que es la red completa del corpus real con 300 nodos.
  0.218 es una modularidad más débil: sugiere una red menos segmentada en
  bloques temáticos nítidos de lo que sugería el análisis parcial anterior —
  esto en sí es un hallazgo a discutir, no un error.)*
- **Distribución de polaridad — cifra FINAL, corpus completo:** 278 artículos
  positivos, 189 negativos, 169 neutros. Índice de polarización afectiva
  **IPA = 0.594**.
- **Encuadres dominantes — cifra FINAL, corpus completo:** distribución
  completa: nación 148, mujer_social 117, política 91, modernidad 64,
  cultura 54, internacional 51, guerra 39, economía 29, religión_moral 25,
  ciencia 13 (de 636 artículos). Frame "nación" dominante, pero "mujer_social"
  en segundo lugar es un dato con más peso del que sugería la mención anterior
  (solo citaba el dominante) — posible eje de lectura para el artículo.
- **Estilometría de autoría — resultado real, no lo que se esperaba:**
  635 de 636 artículos (**99.8%**) figuran "Anónimo / Sin atribuir"; un único
  artículo con autoría firmada real (Alfonso Fuenmayor). No hay base
  estadística para atribución comparativa (`atribuir_autoria` exige 2+ textos
  firmados por autor) — el hallazgo relevante para el artículo NO es un
  resultado de estilometría, es el dato mismo: la práctica editorial de
  *Estampa* en 1939 era casi totalmente anónima. Esto es coherente con el
  patrón ya visto en corpus previos del proyecto (~74-92% anónimo en muestras
  parciales) pero ahora está medido sobre el corpus completo real.
- **Pendiente de tu criterio:** ¿qué entidades/ejes merecen foco interpretativo
  para el argumento del artículo? El sistema puede producir la red completa,
  pero la lectura histórica de por qué esos nodos importan es tuya.

## [Sección 4]
### Validación y límites del método

Siguiendo el mismo gesto autocrítico que la tesis de 2018 hace sobre la
materialidad de la BLC ("para el lector desprevenido de hoy es necesario
mencionar que los libros de LON... fueron fuertemente criticados"), este
artículo debería ser igual de explícito sobre los límites del método
computacional:

- Ground truth de OCR: juicio de un evaluador (LLM) sobre una muestra,
  accuracy real medida 0.69 (46/47 páginas evaluadas) — cifra a citar con su
  método de validación (Kappa de Cohen disponible en `validacion_engine.py`
  para codificación inter-anotador, si se hizo o se planea hacer con un
  segundo codificador humano).
- Limitaciones conocidas y declaradas: bylines con iniciales ("Por JGS") no
  resolubles a nombre completo sin fuente externa; corpus mayoritariamente
  anónimo (~74-92% según el número); fechas/obras/eventos históricos con
  cobertura limitada en el modelo NER más liviano.
- Nota de honestidad metodológica (recomendado, en línea con tu voz):
  documentar aquí que el software mismo tuvo errores de producción corregidos
  durante el desarrollo (fragmentos de OCR fallando en silencio, ventanas de
  segmentación mal calibradas) — es información legítima sobre la fiabilidad
  de cualquier resultado cuantitativo que el artículo cite, y coincide con el
  tipo de transparencia metodológica que ya practicas en la tesis de 2018.

## Conclusiones: [subtítulo temático a definir]

*(a redactar — depende del argumento final)*

## Obras citadas

*(MLA 9, orden alfabético, sangría francesa. Agregar aquí Bhaskar, Mollier y
cualquier fuente sobre prensa/revistas ilustradas colombianas de los años 30 que
uses; **no fabricar ninguna**. Las dos entradas de abajo son las únicas ya
verificadas del esqueleto; el resto lleva marcador `[ ]` hasta que se compruebe
el dato contra la fuente.)*

Gullaván Vera, Fabián Andrés. *La Biblioteca de Literatura Colombiana de la
  editorial La Oveja Negra. Contribuciones para el estudio bibliográfico de
  colecciones editoriales*. 2018. Instituto Caro y Cuervo, trabajo de grado,
  https://bibliotecadigital.caroycuervo.gov.co/id/eprint/1337/.

Rodríguez Morales, [nombre de pila], y [nombre de pila] Sierra Restrepo. "Los
  Nuevos: entre la tradición y la vanguardia". *Boletín Cultural y
  Bibliográfico*, vol. 42, no. 69, 2005, pp. 2-23,
  https://publicaciones.banrepcultural.org/index.php/boletin_cultural/article/view/707.

*(Pendientes de verificar antes de redactar: Bhaskar — la tesis de 2018 lo cita
como 2014, falta el título y la editorial exactos de la edición usada; Mollier
2017, ídem. En MLA el año va después del título, así que la ficha APA de la
tesis no se puede convertir sin tener el registro completo delante.)*

*(Si el artículo cita el software como fuente, la entrada MLA del depósito
Zenodo es la vía correcta — DOI de concepto `10.5281/zenodo.21939404` —, no una
nota al pie. Ver `CITATION.cff` del repo, que ya trae los metadatos.)*

---

## Banco de hallazgos reales disponibles (para elegir, no para copiar todos)

Todos verificables en `memory/project_bashkar_station.md` y el `CHANGELOG.md`
del repo. Antes de citar cualquier cifra en el artículo, **recórrela sobre el
corpus completo actual** (792 páginas, pipeline post-sesión 64) — varias de
las cifras de redes/polaridad de arriba vienen de corridas parciales
anteriores, no de la corrida completa más reciente.

- Tamaño y calidad del corpus (arriba).
- Pipeline y resultado cuantitativo (arriba).
- Wikidata: desambiguación de entidades — 6/7 correctas en muestra de prueba
  (Franco→dictador, España→país, Bogotá, Mussolini, Cataluña, Goethe); un caso
  parcial (Alfonso López, requiere contexto histórico que Wikidata no tiene).
- Análisis estilométrico de autoría: solo 1 autor con 2+ textos firmados
  reales en la muestra revisada — corpus mayoritariamente anónimo, lo cual es
  en sí mismo un dato sobre las prácticas editoriales de la revista (paralelo
  directo con el "83% anónimo justifica estilometría" que ya razonaste en
  sesión 33).
- Densidad de arcaísmos/marcadores históricos: baja en muestras revisadas
  (~0.6%) — indicio de que el español de *Estampa* en 1939 ya era
  relativamente moderno; dato con lectura histórica interesante si se cruza
  con la época y el público objetivo de la revista.

## Próximos pasos concretos antes de escribir prosa final

1. **Revista candidata identificada (2-sep-2026, sin confirmar aún):**
   *Literatura: teoría, historia, crítica* — Departamento de Literatura,
   Universidad Nacional de Colombia (ISSN 0123-5931 impreso / 2256-5450 en
   línea, desde 1997, Latindex/Redalyc/Dialnet). Normas reales verificadas en
   revistas.unal.edu.co/index.php/lthc/about/submissions:
   - Extensión: **6.000-12.000 palabras** para artículos (incluye referencias).
   - **Citación en MLA, NO APA** — ⚠️ discrepancia con el patrón calibrado
     contra la tesis de 2018 (que usa APA). **Resuelto: se convirtió a MLA 9**
     (9-sep-2026); el patrón en texto está en la nota de calibración del inicio.
     La alternativa que se descartó era someter al Boletín Cultural y
     Bibliográfico, que acepta APA.
   - Resumen en **español, inglés Y portugués** (máx. 150 palabras cada uno,
     no solo bilingüe como asumía el esqueleto original) — debe cubrir
     propósito, desarrollo lógico, punto de vista del autor y conclusiones.
   - 3-6 palabras clave.
   - Primera persona: sin restricción explícita en las normas.
   - Evaluación doble ciego; envío por OJS (literaturathc.unal.edu.co) o
     correo (revliter_fchbog@unal.edu.co); requiere CV y perfil institucional
     del autor adjuntos.
   - Formato: Word editable, tablas/figuras editables (no imágenes), imágenes
     ≥300 dpi si aplica.
   - Licencia final: CC BY-NC-ND 4.0.
   **Confirmado por el usuario (2-sep-2026): revista objetivo = esta, citación
   en MLA** (no APA). ~~Pendiente de ejecución: convertir las citas a MLA y
   ajustar el resumen a 3 lenguas~~ — **HECHO 9-sep-2026**: la nota de
   calibración documenta el patrón MLA 9 en texto, "Referencias" pasó a
   "Obras citadas" con las dos fuentes ya verificadas convertidas, el resumen
   bajó de 250 a 150 palabras y se añadieron los bloques de Abstract/Keywords
   y Resumo/Palavras-chave. Queda abierto solo lo que exige consultar fuentes:
   los nombres de pila de Rodríguez Morales y Sierra Restrepo, y las fichas
   completas de Bhaskar y Mollier (MLA pone el año tras el título, así que la
   ficha APA de la tesis de 2018 no basta para convertirlas).
2. ~~Recorrer el pipeline completo sobre el corpus actual~~ — **HECHO
   30-ago-2026**, cifras finales ya incorporadas arriba (7.652 entidades,
   red 300 nodos/0.218 modularidad, IPA 0.594, encuadres, 99.8% anónimo).
3. ~~Definir marco teórico secundario y veta central~~ — **HECHO
   2-sep-2026**: Los Nuevos (Rodríguez Morales y Sierra Restrepo, 2005) +
   campo literario. Falta todavía el argumento histórico completo (la
   relación Los Nuevos↔*Estampa* es una pista real, no una tesis redactada).
4. Redactar la prosa final en tu voz sobre esta estructura (yo puedo ayudar
   sección por sección una vez tengas 2-3 lo suficientemente decididas para
   calibrar contra ellas, igual que se hizo aquí con la tesis de 2018).
