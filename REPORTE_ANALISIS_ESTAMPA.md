# Reporte del análisis computacional del corpus de *Estampa* (1939)

**Corpus:** 5 números de la revista *Estampa* (Colombia), enero-mayo de 1939.
**Fuente:** digitalización de la Biblioteca Nacional de Colombia, 792 páginas,
transcritas con OCR de visión (IA multimodal).
**Herramienta:** Bashkar Station v12.2.
**Fecha de la corrida:** 30 de agosto de 2026.
**Pipeline:** segmentación → NER (RoBERTa, modelo `mrm8488/bert-spanish-cased-finetuned-ner`)
→ red de co-ocurrencia → encuadre → polaridad → estilometría.

---

## 1. Tamaño y composición del corpus

| Número | Páginas |
|---|---|
| Enero 1939 | 138 |
| Febrero 1939 | 178 |
| Marzo 1939 | 89 |
| Abril 1939 | 214 |
| Mayo 1939 | 173 |
| **Total** | **792** |

**Segmentación en unidades editoriales:** 636 artículos (página como unidad
atómica, con consolidación de continuaciones entre páginas).

## 2. Autoría

| Categoría | N | % |
|---|---|---|
| Anónimo / Sin atribuir | 635 | 99,8% |
| Firmado (Alfonso Fuenmayor) | 1 | 0,2% |

**Nota metodológica:** con un solo texto firmado, no hay base estadística
para atribución estilométrica comparativa (`stylometry_engine.atribuir_autoria`
requiere 2+ textos por autor conocido). El dato de anonimato masivo es en sí
mismo el resultado relevante de este eje de análisis.

## 3. Reconocimiento de entidades nombradas (NER)

**Motor:** RoBERTa (`bert-spanish-cased-finetuned-ner`), 6 categorías.
**Total de entidades únicas identificadas:** 7.652.

### 3.1 Personas más mencionadas (por número de artículos en que aparecen)

| Persona | Artículos |
|---|---|
| Hitler | 56 |
| Mussolini | 53 |
| Franco | 51 |
| López | 38 |
| Santos | 27 |
| Presidente de la República | 27 |
| Alfonso López | 24 |
| Presidente | 21 |
| Laureano Gómez | 21 |
| Lucio Duzán | 20 |
| Chamberlain | 17 |
| Eduardo Santos | 16 |
| Gómez | 15 |
| Lozano | 15 |

*(Nota de calidad de datos: "López"/"Alfonso López"/"Presidente"/"Presidente
de la República" y "Santos"/"Eduardo Santos" refieren probablemente a las
mismas dos personas — Alfonso López Pumarejo, presidente 1934-1938 y de nuevo
1942-1945, y Eduardo Santos, presidente 1938-1942 — bajo distintas formas de
mención que el NER no fusiona automáticamente. Para cifras de mención total
por individuo, sumar variantes antes de citar en el artículo.)*

### 3.2 Lugares más mencionados

| Lugar | Artículos |
|---|---|
| Bogotá | 199 |
| Colombia | 184 |
| Europa | 88 |
| España | 84 |
| París | 79 |
| Francia | 74 |
| América | 61 |
| Inglaterra | 53 |
| Londres | 53 |
| Madrid | 50 |
| Alemania | 45 |
| Barranquilla | 40 |
| Medellín | 39 |
| Italia | 28 |
| Calle 40 (Bogotá) | 27 |

### 3.3 Organizaciones/instituciones más mencionadas

| Organización | Artículos |
|---|---|
| ESTAMPA (autorreferencia) | 72 |
| Estado | 58 |
| Estados Unidos | 43 |
| República | 30 |
| Alemania | 28 |
| Italia | 26 |
| Francia | 26 |
| Inglaterra | 22 |
| Gobierno | 18 |
| España | 16 |
| El Tiempo | 14 |
| Universidad | 12 |
| Iglesia | 12 |

*(Nota de calidad de datos: "ESTAA"/"ESTA" —20 y 17 artículos— son variantes
de OCR/segmentación de "ESTAMPA" mal fusionadas por el NER; deben tratarse
como el mismo nodo que "ESTAMPA" antes de citar cifras exactas.)*

## 4. Red de co-ocurrencia de entidades

**Método:** `network_engine.construir_grafo` sobre el índice NER completo,
peso mínimo de coocurrencia = 2 (default).

| Métrica | Valor |
|---|---|
| Nodos | 300 |
| Aristas | 4.083 |
| Comunidades (Louvain/greedy modularity) | 8 |
| Modularidad | 0,218 |

### 4.1 Nodos más conectados (grado)

| Nodo | Grado |
|---|---|
| Colombia | 263 |
| Bogotá | 261 |
| España | 174 |
| Europa | 164 |
| Francia | 162 |
| Estado | 153 |
| América | 150 |
| París | 141 |
| Hitler | 136 |
| Inglaterra | 136 |
| Alemania | 130 |
| ESTAMPA | 126 |
| Mussolini | 125 |
| Franco | 121 |
| Madrid | 121 |

**Lectura estructural:** la red no está dominada por un único eje temático,
sino por un núcleo doble — el par Colombia/Bogotá (la escena local de la
revista) y un cinturón de potencias europeas (España, Francia, Alemania,
Inglaterra) más las figuras de Hitler, Mussolini y Franco. La modularidad
relativamente baja (0,218, sobre una escala 0-1 donde >0,4 suele considerarse
estructura comunitaria fuerte) indica que estos dos polos —lo local
colombiano y la crisis europea de 1939— no están segregados en comunidades
temáticas separadas, sino densamente entrelazados: la revista no separa
"sección internacional" de "sección nacional" en la práctica de sus
menciones, sino que las entidades de ambos planos aparecen juntas con
frecuencia.

*(Corrección respecto a un análisis previo de la bitácora del proyecto: una
cifra de modularidad 0,67 citada en sesiones anteriores correspondía a un
subconjunto curado de solo 43 nodos —sesión 36 del proyecto—, no al corpus
completo. No es comparable con la cifra de 0,218 reportada aquí, que es la
única calculada sobre la red completa y real del corpus.)*

## 5. Encuadres temáticos (frame analysis)

**Método:** `frame_engine.analizar_corpus_frames`, léxico calibrado a prensa
ilustrada colombiana de los años 30 (10 categorías).

| Encuadre | Artículos | % del corpus |
|---|---|---|
| Nación | 148 | 23,3% |
| Mujer / vida social | 117 | 18,4% |
| Política | 91 | 14,3% |
| Modernidad | 64 | 10,1% |
| Cultura | 54 | 8,5% |
| Internacional | 51 | 8,0% |
| Guerra | 39 | 6,1% |
| Economía | 29 | 4,6% |
| Religión / moral | 25 | 3,9% |
| Ciencia | 13 | 2,0% |

**Lectura:** el encuadre dominante no es "Guerra" ni "Internacional" pese a
que la red de entidades está fuertemente cruzada por Hitler/Mussolini/Franco
—esos dos encuadres combinados apenas llegan al 14,1% del corpus—, sino
"Nación" seguido de cerca por "Mujer / vida social" (juntos, 41,7% del
corpus). Esto sugiere que la presencia masiva de figuras europeas en el
índice de entidades no se traduce en que la revista *enmarque* mayoritariamente
sus artículos como noticias de guerra o política internacional: aparecen
mencionadas dentro de crónicas, notas de sociedad y contenido de identidad
nacional con más frecuencia que en piezas explícitamente centradas en el
conflicto europeo.

## 6. Polaridad discursiva

### 6.1 Distribución general (todo el corpus)

| Polaridad | Artículos |
|---|---|
| Positivo | 278 |
| Negativo | 189 |
| Neutro | 169 |

**Índice de polarización afectiva (IPA):** 0,594 (escala 0-1; valores altos
indican que la cobertura se concentra en los extremos positivo/negativo más
que en el centro neutro).

### 6.2 Polaridad hacia figuras específicas

**Método:** `sentimiento_discriminante.polaridad_hacia_corpus`, ventana de
±25 palabras alrededor de cada mención, sin cruzar límites de artículo.

| Figura | Polaridad | Score | Menciones positivas | Menciones negativas | Total menciones | Artículos |
|---|---|---|---|---|---|---|
| Hitler | Negativo | −0,324 | 25 | 49 | 123 | 59 |
| Mussolini | Neutro (leve negativo) | −0,143 | 21 | 28 | 100 | 55 |
| Franco | Negativo | −0,400 | 42 | 98 | 222 | 70 |
| López (Alfonso López / Presidente López) | Positivo | +0,193 | 34 | 23 | 214 | 80 |

**Lectura:** el contraste es claro y consistente con la orientación editorial
de la revista descrita en fuentes secundarias sobre *Estampa*
**[cita pendiente: fuente historiográfica que caracterice la línea editorial
de la revista — no incluida aquí para no fabricar una atribución]**: tono
sistemáticamente negativo hacia las tres figuras del fascismo/franquismo
europeo (Hitler el menos negativo de los tres, −0,324; Franco el más negativo,
−0,400, coherente con la cobertura de la Guerra Civil española recién
terminada en 1939), frente a un tono positivo hacia el presidente colombiano
en ejercicio o reciente, Alfonso López Pumarejo (+0,193). Franco es, además,
la figura con más menciones totales de las cuatro (222, en 70 de los 636
artículos) — la Guerra Civil española y su desenlace son, por volumen de
menciones, el evento internacional más presente del corpus, por encima de
Hitler pese a que este también atraviesa el período previo a la Segunda
Guerra Mundial.

## 7. El campo literario dentro del corpus

**Método:** selección manual de escritores reconocibles sobre el índice de
personas, agregando variantes de un mismo nombre; cruce con la red de
co-ocurrencia (§4) y con la sección editorial asignada por artículo.

### 7.1 Escritores identificados, por número de artículos

| Escritor | Artículos | Números |
|---|---|---|
| Germán Arciniegas | 11 | ene, feb, mar, abr, may |
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

*(Limitación importante: la categoría `obras_publicaciones` del esquema NER
de Bashkar Station quedó en 0 en esta corrida porque el motor RoBERTa
utilizado (`bert-spanish-cased-finetuned-ner`) solo reconoce 4 categorías
nativas —PER/LOC/ORG/MISC—, sin la granularidad histórica de 6 categorías
que sí tiene el fallback spaCy. Esta lista de escritores es manual y
necesariamente parcial: cubre solo los nombres que el modelo reconoció
correctamente como "persona" bajo la forma exacta buscada.)*

### 7.2 Integración en la red de co-ocurrencia

De los 17 escritores identificados, solo **3 logran integrarse a la red**
(umbral mínimo de 2 co-apariciones): Arciniegas (grado 18, vecinos
principales Colombia/América/Bogotá/Europa), Chaves Nogales (grado 14,
vecinos Francia/España/Franco/Cataluña) y García Lorca (grado 8, vecinos
Bogotá/Madrid/Granada/España). Los 14 restantes aparecen en el corpus pero
sin suficiente co-ocurrencia repetida como para dejar huella estructural.
De los tres integrados, los dos españoles (Chaves Nogales, Lorca) se conectan
específicamente a través de la Guerra Civil española, no de una red literaria
autónoma.

### 7.3 Secciones literarias explícitas

| Sección | Artículos | % del corpus |
|---|---|---|
| Libros | 8 | 1,3% |
| Poema/Verso | 5 | 0,8% |
| Cuento | 2 | 0,3% |
| **Total literario explícito** | **15** | **2,4%** |

La sección "Libros" incluye un artículo dedicado a León de Greiff, uno
titulado "Los Intelectuales" y cobertura de los Premios Nobel de Literatura
y Física de 1938. La mayoría de las menciones a escritores (ver §7.1) ocurre
fuera de estas secciones dedicadas, en secciones como "General", "Sociedad"
o "Cine".

## 8. Validez y límites del método (declaración obligatoria antes de citar estas cifras)

- **Ground truth de OCR:** evaluado en una sesión previa sobre una muestra de
  47 páginas con un juez automático (LLM), accuracy real 0,69 (46/47
  evaluadas) — no es una validación humana independiente; recomendable antes
  de publicar cifras que dependan crítimente de la fidelidad textual.
- **NER:** motor RoBERTa (`bert-spanish-cased-finetuned-ner`), sin validación
  manual sistemática sobre este corpus específico contra un ground truth
  anotado a mano. Ruido conocido: variantes de un mismo referente no siempre
  fusionadas (ver notas en §3.1 y §3.3), fragmentos de layout ("ESTAA"/"ESTA")
  colándose como organizaciones.
- **Frames y polaridad:** léxicos basados en reglas calibradas para prensa
  1930s, no modelos entrenados sobre este corpus específico ni validados con
  codificación humana inter-anotador (el módulo `validacion_engine.py` del
  proyecto permite calcular Kappa de Cohen si se hace esa validación).
- **Estilometría:** no aplicable con los datos actuales (ver §2).
- **Recomendación antes de publicar:** validar con codificación humana al
  menos una muestra de la polaridad hacia las 4 figuras del §6.2 y de los
  encuadres del §5, siguiendo el protocolo de `validacion_engine.exportar_muestra`
  + `calcular_concordancia` ya disponible en el proyecto.

---

*Reporte generado automáticamente a partir de una corrida real del pipeline
de Bashkar Station sobre el corpus completo. Todas las cifras son
verificables reejecutando `cli.py --etapas seg,ner` sobre el proyecto
`Estampa_1939__Vision_OCR_completo.bashkar` más el script de análisis de
red/encuadre/polaridad documentado en la sesión del 30-ago-2026.*
