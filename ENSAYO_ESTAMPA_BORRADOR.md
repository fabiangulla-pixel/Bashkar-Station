> **Nota para Fabián (borrar antes de someter):** segundo borrador. El primero
> centraba el argumento en Hitler/Mussolini/Franco/López; a tu pedido, este
> lo reemplaza por completo con el eje literario/cultural: qué escritores
> aparecen, con qué frecuencia, en qué secciones, y qué tan integrados o
> marginales están en la red del corpus frente al núcleo político-internacional.
> Sigue el mismo registro calibrado contra tu tesis de 2018 (primera persona
> puntual, "se+verbo" impersonal, citas APA, notas al pie). Todos los datos
> son reales de la corrida del 30-ago-2026 (ver `REPORTE_ANALISIS_ESTAMPA.md`
> para las tablas políticas que ya no son el centro del argumento, y el script
> de esta sesión para las cifras literarias nuevas, aún no volcadas al
> reporte técnico). `[cita pendiente: ...]` marca donde falta tu criterio o
> una fuente secundaria que no tengo verificada — no inventé ninguna.

---

# [Título provisional] Letras sin firma: el campo literario en *Estampa* (1939) bajo lectura distante

Fabián Andrés Gullaván Vera¹

¹ *(nota al pie: afiliación institucional, financiamiento — Beca a Nuevos
Investigadores en Estudios Editoriales, MinCultura 2025, Instituto Caro y
Cuervo)*

## Resumen

Este artículo examina la presencia de escritores y del campo literario dentro
del corpus completo de la revista ilustrada colombiana *Estampa*
correspondiente a cinco números de 1939 (enero-mayo, 792 páginas, 636
unidades editoriales), a partir de un análisis distante sobre 7.652 entidades
nombradas identificadas automáticamente. Se identifica un conjunto de
escritores colombianos, latinoamericanos y españoles mencionados a lo largo
del corpus —encabezado por Germán Arciniegas (11 artículos, presente en los
cinco números) y León de Greiff (7)—, y se muestra que, salvo tres
excepciones, estas figuras aparecen de forma dispersa y poco conectada dentro
de la red de co-ocurrencia del corpus, en contraste con el núcleo denso que
forman los actores de la política internacional de 1939. Las tres
excepciones —Arciniegas, Manuel Chaves Nogales y García Lorca— sí logran
integrarse a esa red, y lo hacen precisamente a través de su vínculo con la
Guerra Civil española y sus consecuencias, no de una red literaria autónoma.
El corpus dedica secciones explícitas a la vida literaria (Libros, 8
artículos; Poema/Verso, 5; Cuento, 2) pero estas son minoritarias frente al
volumen general de la revista, y el 99,8% de todo el corpus —incluidas estas
piezas— carece de atribución de autoría identificable.

**Palabras clave:** prensa ilustrada colombiana, campo literario, humanidades
digitales, *Estampa*, análisis de redes, generación de "Los Nuevos".

## Abstract / Key Words
*(traducir una vez cerrado el texto en español)*

---

## Introducción: escritores sin firma en una revista de masas

*[Sección que más necesita tu marco teórico. Sugerencia de andamiaje, a
completar o descartar:]*

Que una revista ilustrada de circulación masiva mencione con frecuencia a
escritores no implica que funcione como órgano del campo literario: puede
citarlos como referencia de prestigio cultural mientras dedica la mayor parte
de sus páginas a la moda, el cine o la crónica social. *Estampa*, en sus
cinco números de 1939 aquí analizados, ofrece un caso donde ambas cosas
conviven de forma medible: escritores como Germán Arciniegas o León de Greiff
—ambos activos en Colombia por esos años dentro de lo que la historiografía
literaria ha llamado la generación de "Los Nuevos"
[cita pendiente: fuente sobre "Los Nuevos" y la generación literaria
colombiana de los años 20-30 —debo pedirte la referencia exacta o que la
confirmes]— circulan por el corpus con una frecuencia que ningún lector
casual notaría sin un índice completo, y sin embargo ninguna de sus
apariciones lleva su firma como autores de lo que se publica: el corpus
entero es, en un 99,8%, anónimo. Este artículo pregunta, con la totalidad del
corpus y no con una muestra, dónde y cómo aparece lo literario dentro de una
revista que no se presenta a sí misma como una publicación literaria, y qué
tan integrado o marginal es ese campo dentro de la red temática general de la
revista.

## 1. Quiénes aparecen: un inventario real, no una lista de nombres esperados

*(cifras verificadas, corrida propia de esta sección)*

Sobre las 7.652 entidades identificadas en el corpus completo, se
seleccionaron manualmente las que corresponden a escritores reconocibles,
agregando variantes de un mismo nombre (p. ej. "Germán Arciniegas" y
"Arciniegas" a secas)¹. El resultado, ordenado por número de artículos en que
aparece cada figura:

| Escritor | Artículos | Números en que aparece |
|---|---|---|
| Germán Arciniegas | 11 | ene, feb, mar, abr, may (los 5) |
| León de Greiff | 7 | ene, feb, abr |
| Manuel Chaves Nogales (España) | 6 | ene, feb, mar, abr |
| García Lorca (España) | 5 | ene, feb, may |
| Guillermo Valencia | 4 | mar, abr, may |
| Vargas Vila | 4 | feb, abr, may |
| Eduardo Caballero Calderón | 4 | ene, may |
| Tomás Carrasquilla | 3 | ene, abr |
| Baldomero Sanín Cano | 2 | abr |
| Pablo Neruda (Chile) | 2 | feb, mar |
| Diego Rivera (México) | 2 | ene, abr |
| Jorge Zalamea | 1 | feb |
| José Asunción Silva | 1 | mar |
| Rómulo Gallegos (Venezuela) | 1 | may |
| Miguel Otero Silva (Venezuela) | 1 | may |
| Miguel de Unamuno (España) | 1 | abr |
| Pío Baroja (España) | 1 | feb |

*(nota al pie 1: esta selección se hizo a mano sobre el índice automático de
personas —el NER no distingue "escritor" como categoría propia; la
categoría `obras_publicaciones` del esquema de Bashkar Station, pensada para
detectar títulos de libros, quedó en cero en esta corrida porque el motor
RoBERTa usado solo reconoce cuatro categorías nativas —persona, lugar,
organización, misceláneo— sin ese nivel de detalle histórico; ver
`REPORTE_ANALISIS_ESTAMPA.md`, §7, para la limitación completa. Esto significa
que el inventario de arriba es necesariamente parcial: cualquier escritor no
reconocido por el modelo como "persona" con ese nombre exacto, o mencionado
solo por seudónimo o alias no catalogado, no aparece aquí.)*

Dos observaciones sobre esta lista antes de leerla en conjunto. Primera:
domina de forma clara el campo literario colombiano de entreguerras sobre
cualquier otra procedencia latinoamericana —Neruda, Gallegos y Otero Silva
suman apenas 4 menciones combinadas frente a las 11 de Arciniegas en
solitario—, lo que sugiere una revista más orientada a su propio campo
literario nacional que a proyectarse como vitrina de las letras
latinoamericanas en su conjunto. Segunda: la presencia española —Chaves
Nogales, Lorca, Unamuno, Baroja— es comparable en volumen a la colombiana, y
no por casualidad: como se muestra en la sección siguiente, esa presencia
está fuertemente asociada a la cobertura de la Guerra Civil española, no a
una sección literaria separada del acontecer internacional.

## 2. Un campo disperso, con tres excepciones que se conectan por la guerra

*(cifras verificadas, corrida propia de esta sección)*

La red de co-ocurrencia completa del corpus —300 nodos, 4.083 aristas,
construida con un umbral mínimo de dos co-apariciones para formar una
arista²— deja fuera a la mayoría de los escritores del inventario anterior:
de dieciséis nombres literarios identificados, solo tres —Germán Arciniegas,
Manuel Chaves Nogales y García Lorca— logran suficiente co-ocurrencia con
otras entidades como para integrarse a la red. Los trece restantes —León de
Greiff, Guillermo Valencia, Vargas Vila, Carrasquilla, Sanín Cano, Neruda,
Gallegos, Otero Silva, Diego Rivera, Zalamea, Silva, Unamuno, Baroja—
aparecen en el corpus pero de forma demasiado aislada, sin acompañarse
repetidamente de ninguna otra entidad concreta, como para dejar huella
estructural en la red temática de la revista.

*(nota al pie 2: `peso_minimo=2`, el valor por defecto de
`network_engine.construir_grafo`; un escritor mencionado en cuatro artículos
distintos, cada uno junto a una entidad diferente, no necesariamente genera
ninguna arista si ninguna de esas coincidencias se repite dos veces.)*

De los tres que sí se integran, ninguno lo hace por una razón puramente
literaria. Germán Arciniegas —el escritor más mencionado del corpus, con 18
conexiones en la red— se vincula sobre todo con Colombia, América, Bogotá y
Europa: una centralidad amplia y genérica, consistente con la de una figura
pública reconocida más que con un perfil temático específico. Manuel Chaves
Nogales, en cambio, se conecta con Francia, España, Franco y Cataluña³ —su
red es, literalmente, la red de la derrota republicana y el exilio. García
Lorca se conecta con Madrid, Granada y España —su propia biografía
(fusilado en Granada en 1936) hace que su sola mención arrastre esa
geografía. Es decir: los tres escritores que la revista termina tejiendo
dentro de su red temática general no lo hacen por pertenecer a un campo
literario que la revista narre como tal, sino porque su nombre ya está
adherido, en 1939, a la actualidad política española que domina el resto del
corpus (ver Sección 2 del reporte técnico completo sobre esa red política).

*(nota al pie 3: Manuel Chaves Nogales, cronista y periodista español exiliado
tras la guerra civil —autor de crónicas de la contienda que circularon en
prensa hispanoamericana [cita pendiente: fuente biográfica/bibliográfica
sobre Chaves Nogales y su circulación en la prensa colombiana, si la tienes
o si quieres que la busque]—, es un caso especialmente ilustrativo: no es un
literato "puro" en el sentido de Arciniegas o De Greiff, sino un periodista
cuya obra está genéricamente a caballo entre el reportaje y la literatura, lo
que podría explicar por qué es, de los tres, el que más se integra
estructuralmente a la red política del corpus.)*

## 3. Dónde vive lo literario dentro de la revista: secciones minoritarias

*(cifras verificadas, corrida propia de esta sección)*

De las 636 unidades editoriales del corpus, la revista clasifica
explícitamente solo 15 bajo secciones de contenido estrictamente literario:
8 en "Libros", 5 en "Poema/Verso", 2 en "Cuento" —un 2,4% del corpus—, frente
a 265 en "General", 76 en "Política", 42 en "Modas/Hogar" y 39 en
"Internacional". La sección "Libros" incluye, entre otras piezas, un artículo
dedicado explícitamente a León de Greiff (con ese nombre como título) y otro
titulado "Los Intelectuales"; la cobertura de la ceremonia de entrega de los
Premios Nobel de Literatura y Física de 1938 también aparece ahí, señal de
que la revista sigue el circuito de reconocimiento literario internacional
además del campo nacional.

Esta cifra —2,4% del corpus en secciones literarias dedicadas— no debe
leerse como el techo real de la presencia literaria: como muestra la Sección
1, escritores como Arciniegas aparecen en secciones tan disímiles como
"General", "Sociedad" o "Cine", fuera de cualquier rótulo literario
explícito. Lo literario en *Estampa*, con la evidencia de este corpus, no
vive concentrado en una sección propia sino disperso a través de toda la
revista —una observación que matiza cualquier lectura que buscara "la
sección literaria" de *Estampa* como si fuera un compartimento estanco.
[Argumento a desarrollar con tu criterio: ¿es esto un rasgo genérico de la
revista ilustrada de entreguerras frente al suplemento literario del
periódico diario, o una particularidad editorial de *Estampa*?]

## Conclusiones: [subtítulo a definir con el argumento final]

*(a redactar una vez cerrado el argumento central — posible síntesis a
partir de lo ya evidenciado: *Estampa* sostiene un campo literario activo y
reconocible —encabezado con claridad por Arciniegas y De Greiff, dos nombres
de "Los Nuevos"— pero lo hace de forma difusa, sin sección ni firma estables,
y su único punto de conexión estructural con el resto de la revista pasa,
paradójicamente, por la guerra europea antes que por una red literaria
autónoma. Qué implica esto para entender el lugar del escritor en la prensa
ilustrada colombiana de los años 30 es la pregunta que este artículo deja
planteada más que resuelta, y que tu criterio de investigador debe cerrar.)*

## Referencias

*(APA — agregar aquí toda fuente secundaria real que uses, especialmente
sobre "Los Nuevos" y sobre Chaves Nogales; ninguna incluida en este borrador
para no fabricar citas)*
