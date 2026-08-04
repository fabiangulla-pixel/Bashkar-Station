"""Guías de módulos de Bashkar Station — qué es cada herramienta, para qué
sirve, qué tipo de resultado entrega y CÓMO interpretar los datos.

Datos puros (sin dependencias de UI). La GUI los consume en `_page_header`
para mostrar, bajo el título de cada panel, un resumen siempre visible más
una sección colapsable «Cómo interpretar los resultados» con la guía
profunda orientada a investigación en Humanidades Digitales.

Cada entrada es un dict con cuatro claves:
  - "que_es"       : qué es la herramienta (1-2 frases).
  - "para_que"     : para qué sirve en una investigación.
  - "resultado"    : qué tipo de salida produce (tablas, cifras, figuras…).
  - "interpretar"  : guía de lectura rigurosa — qué significan las cifras,
                     supuestos del método, umbrales de referencia, trampas
                     comunes y cómo llevarlo al paper.

La clave de cada entrada es el `id` de página de `_PAGINAS` en app.py.
Acceder con `guia_modulos.obtener(page_id)`; devuelve None si no existe.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Guías por panel (clave = id de página en app.py _PAGINAS)
# ---------------------------------------------------------------------------

GUIA_MODULOS: dict[str, dict[str, str]] = {

    # ───────────────────────── FLUJO PRINCIPAL ─────────────────────────────
    "cfg": {
        "que_es": "Punto de partida del proyecto: define el corpus (carpetas "
                  "de imágenes/PDF), las claves de API y el modelo de IA que "
                  "usará cada etapa del análisis.",
        "para_que": "Dejar reproducible de dónde sale el material y con qué "
                    "herramientas se procesa. Es la base de la trazabilidad "
                    "metodológica que exige una revista.",
        "resultado": "Un proyecto .bashkar con rutas, claves y preferencias "
                     "persistentes. No produce análisis todavía.",
        "interpretar": "No hay cifras que interpretar aquí, pero sí decisiones "
                       "que documentar en el paper: qué proveedor de IA se usó "
                       "(local Ollama vs. nube), qué modelo y por qué. El modelo "
                       "elegido afecta costo, privacidad (los datos salen a un "
                       "tercero salvo Ollama) y reproducibilidad (los modelos de "
                       "nube cambian con el tiempo; anota la fecha y la versión). "
                       "Para corpus histórico en español, los modelos grandes de "
                       "visión (Gemini/Claude/GPT) superan a Tesseract en "
                       "microfilm degradado.",
    },

    "etz": {
        "que_es": "Editor manual de zonas: marcas sobre la imagen qué región "
                  "es título, cuerpo, foto, pie, publicidad o filete, y en qué "
                  "orden de lectura van.",
        "para_que": "Enseñar al OCR la estructura de la página (prensa "
                    "ilustrada multicolumna) para que el texto salga en orden "
                    "y sin mezclar columnas ni pies de foto con el cuerpo.",
        "resultado": "Un mapa de zonas con tipo y orden, que alimenta el OCR "
                     "por regiones y la segmentación posterior.",
        "interpretar": "El orden de lectura es lo crítico: si los badges de "
                       "orden saltan de columna incorrectamente, el texto "
                       "OCR saldrá desordenado y contaminará todo el análisis "
                       "textual aguas abajo. Revisa que las fotos estén "
                       "marcadas como tales (su 'texto' OCR es ruido) y que "
                       "los pies de foto NO se fundan con el cuerpo del "
                       "artículo. En layouts tipo 'marco' (texto rodeando una "
                       "ilustración) el orden automático suele fallar: corrígelo "
                       "a mano. Una buena zonificación es la diferencia entre un "
                       "corpus limpio y uno irrecuperable.",
    },

    "ocr": {
        "que_es": "Reconocimiento óptico de caracteres: convierte la imagen "
                  "de cada página en texto editable, por varias rutas "
                  "(Tesseract local, IA de visión, Kraken/HTR, texto embebido).",
        "para_que": "Obtener el texto del corpus, materia prima de todo el "
                    "análisis. Sin texto fiable no hay NER, ni tópicos, ni "
                    "sentimiento que valgan.",
        "resultado": "Archivos de texto por página, con un índice de confianza "
                     "del reconocimiento.",
        "interpretar": "Vigila la CONFIANZA: páginas por debajo de ~30 % suelen "
                       "estar tan degradadas que su texto es ruido (palabras "
                       "partidas, 'pofftica' por 'política'). El microfilm de la "
                       "BNC con grano e inclinación da 0 palabras útiles en "
                       "Tesseract sin deskew+denoise; ahí conviene la ruta de IA "
                       "de visión. Regla de oro de HD: la calidad del OCR pone el "
                       "techo a TODO el análisis posterior. Antes de sacar "
                       "conclusiones, mide la tasa de error sobre una muestra "
                       "transcrita a mano (CER/WER) y repórtala — es el dato que "
                       "una revista te va a pedir para confiar en el resto.",
    },

    "conv": {
        "que_es": "Conversor masivo de PDF a texto/Word extrayendo el texto "
                  "YA embebido (PDFs con capa OCR previa, p. ej. Adobe Paper "
                  "Capture de la BNC), sin re-reconocer.",
        "para_que": "Aprovechar OCR ya hecho: rapidísimo (48 págs en segundos) "
                    "y sin costo, cuando el PDF trae texto detrás de la imagen.",
        "resultado": "Archivos .txt/.docx por página, limpios de coordenadas "
                     "XY del OCR de origen, listos para Normalizar.",
        "interpretar": "Útil sólo si el PDF tiene capa de texto: si el conversor "
                       "saca poco o nada, el PDF es imagen pura y necesitas la "
                       "ruta de OCR/IA. El texto embebido de la BNC suele ser de "
                       "calidad media (OCR antiguo): trátalo como punto de "
                       "partida a revisar en Normalizar, no como verdad final. "
                       "Conserva nota de la procedencia (OCR de origen vs. propio) "
                       "porque mezclar OCR de distinta calidad introduce sesgos "
                       "difíciles de rastrear después.",
    },

    "mmx": {
        "que_es": "Extracción multimodal con IA de visión: la IA 'lee' la "
                  "página y devuelve su estructura en JSON (artículo "
                  "jerárquico, fotos con sus pies, bloques de publicidad), no "
                  "sólo texto plano.",
        "para_que": "Rescatar páginas que el OCR clásico no recupera (microfilm "
                    "degradado) Y obtener de una vez la estructura editorial, "
                    "separando cuerpo, pies de foto y anuncios.",
        "resultado": "Un JSON por página + Markdown legible; alimenta el corpus "
                     "textual con el cuerpo del artículo (excluyendo pies y "
                     "publicidad) y registra el costo real de IA.",
        "interpretar": "La gran ventaja sobre el OCR plano es que la salida "
                       "viene ya SEPARADA por función editorial: el cuerpo del "
                       "artículo no se contamina con texto de anuncios. Pero la IA "
                       "de visión puede 'alucinar' (inventar texto plausible donde "
                       "no lo lee); por eso conserva la ortografía de época y "
                       "DEBES validar una muestra contra la imagen original. "
                       "Estima siempre el costo antes de lanzar el lote (se "
                       "muestra el desglose tokens/USD) y registra el costo real "
                       "post-lote: es parte del estándar de transparencia. Para el "
                       "paper, reporta proveedor, modelo y fecha: estos modelos "
                       "evolucionan y el resultado no es perfectamente "
                       "reproducible.",
    },

    "norm": {
        "que_es": "Revisión y normalización del texto OCR: corriges errores, "
                  "eliges entre versiones (cruda / manual / IA), y comparas "
                  "diferencias antes de fijar el texto definitivo.",
        "para_que": "Producir la versión del texto sobre la que correrá el "
                    "análisis, decidiendo cuánto normalizar sin borrar rasgos "
                    "históricos que son objeto de estudio.",
        "resultado": "El texto 'de trabajo' del corpus, versionado y "
                     "persistente, más un diccionario de corpus opcional.",
        "interpretar": "Decisión metodológica central: ¿normalizas la "
                       "ortografía de época (p. ej. acentuación antigua) o la "
                       "conservas? Si tu objeto de estudio ES la lengua de los "
                       "años 30, normalizar de más BORRA tu evidencia. Si te "
                       "interesa el contenido (temas, actores), normalizar ayuda a "
                       "que NER y tópicos agrupen variantes. Documenta qué "
                       "criterio usaste y aplícalo de forma consistente a todo el "
                       "corpus. El diff visual rojo/verde te muestra el impacto de "
                       "cada cambio: úsalo para no introducir errores nuevos al "
                       "'corregir'.",
    },

    "seg": {
        "que_es": "Segmentación: parte el texto continuo de cada número en "
                  "artículos individuales y los tipifica (artículo, índice, "
                  "publicidad, portada, colofón).",
        "para_que": "Convertir un flujo de páginas en unidades de análisis "
                    "(el artículo), que es lo que se cuenta, compara y clasifica "
                    "en el resto del estudio.",
        "resultado": "Una lista de artículos con su tipo, longitud y texto, "
                     "base de todos los análisis por documento.",
        "interpretar": "La unidad de análisis condiciona todo: si la "
                       "segmentación une dos artículos, sus temas y entidades se "
                       "mezclan; si parte uno en dos, infla los conteos. Revisa "
                       "que los textos muy cortos (<20 palabras) no estén "
                       "inflando la categoría 'Portada' por diseño del "
                       "clasificador. Comprueba el reparto de tipos: un corpus de "
                       "prensa ilustrada con 0 % de publicidad detectada es "
                       "sospechoso. El recuento de artículos por número y por "
                       "tipo es un dato descriptivo que conviene reportar como "
                       "primera caracterización del corpus.",
    },

    "anal": {
        "que_es": "Análisis textual y semántico de base: frecuencias, "
                  "n-gramas, palabras clave, y expansión semántica con "
                  "Word2Vec entrenado sobre tu propio corpus.",
        "para_que": "Una primera lectura cuantitativa del vocabulario: qué se "
                    "nombra mucho, qué palabras aparecen juntas, qué campos "
                    "semánticos estructura el corpus.",
        "resultado": "Tablas de frecuencias y n-gramas, y vecinos semánticos "
                     "por palabra (p. ej. guerra → hitlerianos, mujer → modas).",
        "interpretar": "Las frecuencias crudas están dominadas por palabras "
                       "vacías y por el RUIDO de OCR: filtra stopwords y "
                       "fragmentos antes de concluir nada. Los n-gramas "
                       "(bigramas/trigramas) revelan fórmulas y colocaciones de "
                       "la época. En la expansión semántica (Word2Vec), los "
                       "'vecinos' reflejan co-aparición en contextos similares, "
                       "NO sinonimia ni causalidad: que 'guerra' y 'hitlerianos' "
                       "estén próximos describe el discurso de 1939, no una "
                       "opinión. Vecinos raros ('túon', 'pofftica') son síntoma "
                       "de OCR sucio, no hallazgos. Necesitas suficiente corpus "
                       "(miles de palabras) para que los vectores sean estables.",
    },

    "res": {
        "que_es": "Centro de resultados y exportación: reúne las salidas del "
                  "proyecto y las empaqueta en formatos estándar (TEI, BibTeX, "
                  "CSV, Markdown, ZIP de publicación).",
        "para_que": "Sacar el material del programa hacia el paper, el "
                    "repositorio de datos (Zenodo/DOI) y otras herramientas.",
        "resultado": "Ficheros estándar interoperables y un paquete de "
                     "publicación reproducible.",
        "interpretar": "No interpretas cifras aquí, sino que garantizas "
                       "interoperabilidad: el TEI P5 permite que otros "
                       "humanistas reusen tu corpus; el BibTeX cita las fuentes; "
                       "el CSV (utf-8-sig) abre bien en Excel español. Antes de "
                       "publicar, valida el TEI (debe dar 0 errores) y revisa "
                       "que los identificadores sean estables. Publicar el "
                       "paquete con DOI es lo que convierte tu software y tus "
                       "datos en un objeto citable y reproducible.",
    },

    # ───────────────────────── ANÁLISIS ────────────────────────────────────
    "ner": {
        "que_es": "Reconocimiento de Entidades Nombradas (NER): detecta y "
                  "clasifica personas, lugares y organizaciones en el texto, "
                  "combinando spaCy, un modelo BERT y opcionalmente un LLM.",
        "para_que": "Saber QUIÉN, DÓNDE y QUÉ instituciones aparecen en el "
                    "corpus y con qué frecuencia: el insumo de las redes de "
                    "actores, los mapas y el grafo de conocimiento.",
        "resultado": "Un índice de entidades por categoría con su frecuencia y "
                     "los artículos donde aparecen; exportable a CSV y "
                     "enlazable a Wikidata.",
        "interpretar": "El NER sobre OCR histórico tiene falsos positivos "
                       "(fragmentos OCR tomados por nombres) y falsos negativos "
                       "(nombres mal escritos no reconocidos). Una misma persona "
                       "aparece como variantes ('López', 'Alfonso López'); por "
                       "eso existe la fusión canónica y la cola de revisión "
                       "human-in-the-loop. NO leas la frecuencia como "
                       "'importancia' sin más: depende de la cobertura del "
                       "corpus. Si vas a construir redes, guarda TODAS las "
                       "entidades por artículo (no sólo la principal), o la red "
                       "saldrá trivial. Reporta precisión/recall sobre una "
                       "muestra anotada a mano: es la validación que da "
                       "credibilidad al análisis de actores.",
    },

    "anot": {
        "que_es": "Anotación semántica revisable estilo Recogito: marcas "
                  "pasajes con etiquetas, registrando QUIÉN lo anotó, con qué "
                  "confianza y con historial de cambios (Assertive Edition).",
        "para_que": "Construir interpretación trazable: cada afirmación sobre "
                    "el texto queda con su procedencia, lista para auditar o "
                    "discutir entre codificadores.",
        "resultado": "Anotaciones con fuente, confianza e historial, "
                     "exportables como Web Annotation (JSON-LD).",
        "interpretar": "La clave epistemológica es la PROCEDENCIA: una "
                       "anotación no es un hecho, es una aserción de alguien con "
                       "un grado de certeza. Aprovecha la confianza para "
                       "distinguir lo seguro de lo conjetural, y el historial "
                       "para mostrar cómo evolucionó tu lectura. En equipo, las "
                       "discrepancias entre anotadores no son errores a esconder: "
                       "son datos sobre la ambigüedad del material, y se "
                       "cuantifican con el módulo de Validación (Kappa).",
    },

    "bsem": {
        "que_es": "Búsqueda semántica por similitud: encuentra pasajes "
                  "parecidos en SIGNIFICADO a una consulta, usando embeddings "
                  "(sentence-transformers + FAISS), no coincidencia exacta de "
                  "palabras.",
        "para_que": "Localizar de qué se habla aunque no se usen tus palabras "
                    "exactas: recuperar el tratamiento de un tema disperso en el "
                    "corpus con distinto vocabulario.",
        "resultado": "Una lista de pasajes ordenados por similitud semántica "
                     "con un puntaje (0–1).",
        "interpretar": "El puntaje mide cercanía en el espacio vectorial, no "
                       "verdad ni relevancia: un valor alto significa "
                       "'parecido en uso', y puede traer falsos amigos. Es una "
                       "herramienta de EXPLORACIÓN y recuperación, no de "
                       "medición: úsala para encontrar material, luego lee los "
                       "pasajes. Los modelos de embeddings se entrenaron en "
                       "español moderno, así que en lengua de 1930 pueden perder "
                       "matices. No reportes 'similitud 0.82' como hallazgo; "
                       "repórtalo como criterio con el que reuniste un conjunto "
                       "de pasajes que luego analizaste cualitativamente.",
    },

    "coloc": {
        "que_es": "Collocates y concordancias: muestra qué palabras "
                  "acompañan habitualmente a un término (su vecindario léxico) "
                  "y en qué contextos aparece (líneas KWIC).",
        "para_que": "Estudiar el USO de una palabra: con qué se asocia "
                    "'mujer', 'guerra' o 'moderno' en la prensa de la época "
                    "—la base de la lingüística de corpus.",
        "resultado": "Tablas de colocados con medidas de asociación y "
                     "concordancias palabra-en-contexto.",
        "interpretar": "Las medidas de asociación (p. ej. información mutua) "
                       "premian co-apariciones DISTINTIVAS, no sólo frecuentes: "
                       "un colocado raro pero muy ligado puede ser más revelador "
                       "que uno común. Cuidado con la frecuencia mínima: con "
                       "pocos casos, la asociación es inestable (azar). La "
                       "ventana (cuántas palabras a cada lado) cambia el "
                       "resultado: ventanas cortas captan sintaxis, largas captan "
                       "temática. Las concordancias KWIC son la prueba "
                       "cualitativa: siempre vuelve al texto real antes de "
                       "afirmar que dos términos 'van juntos'.",
    },

    "nov": {
        "que_es": "Detección de novedad y cambio discursivo: identifica "
                  "cuándo aparecen temas o vocabulario NUEVOS respecto a lo "
                  "anterior en la secuencia temporal del corpus.",
        "para_que": "Detectar inflexiones: el momento en que el discurso de la "
                    "revista cambia de foco (irrupción de un tema, giro de "
                    "tono), útil para periodizar.",
        "resultado": "Una curva/serie de novedad por número o fecha, marcando "
                     "los picos de cambio.",
        "interpretar": "Un pico de novedad señala que ESE número introduce "
                       "léxico/temas poco vistos antes; es una pista, no una "
                       "explicación: hay que ir al material y ver qué pasó "
                       "(un acontecimiento histórico, un cambio editorial). "
                       "Distingue novedad real de artefactos: un cambio de OCR o "
                       "de fuente puede simular 'novedad' léxica. Con pocos "
                       "números el cálculo es ruidoso. Es ideal para CONTAR una "
                       "historia cronológica en el paper, anclando cada pico a "
                       "evidencia textual concreta.",
    },

    "red": {
        "que_es": "Redes de co-ocurrencia: construye un grafo donde los nodos "
                  "son entidades (o palabras) y las aristas indican que "
                  "aparecen juntas; calcula comunidades y métricas.",
        "para_que": "Ver la ESTRUCTURA relacional del corpus: qué actores y "
                    "lugares forman bloques, quién es central, cómo se agrupan "
                    "los temas.",
        "resultado": "Un grafo (visual y exportable a GEXF/Gephi) con "
                     "comunidades coloreadas y métricas: grado, centralidad, "
                     "modularidad, densidad.",
        "interpretar": "Las métricas tienen umbrales de referencia: la "
                       "MODULARIDAD > 0.3-0.4 indica que las comunidades "
                       "detectadas son reales y no azar (en este corpus se "
                       "obtuvo ~0.57, comunidades coherentes: guerra-España, "
                       "bloque anglosajón, Europa). La CENTRALIDAD señala nodos "
                       "puente, no necesariamente importancia histórica. Cuidado: "
                       "co-ocurrir en un mismo número/artículo NO es relación "
                       "social ni causal — es co-presencia textual. La densidad y "
                       "el tamaño dependen de cuántas entidades guardaste por "
                       "documento: si la base trae ~1 entidad/artículo, la red "
                       "será pobre (hace falta re-NER guardando todas). Reporta el "
                       "método de construcción (qué cuenta como arista) o la red "
                       "no será interpretable por otros.",
    },

    "ling": {
        "que_es": "Suite de lingüística computacional: sintaxis "
                  "(dependencias, SVO), correferencia, morfología histórica, "
                  "encuadre (framing), polaridad y validación inter-codificador.",
        "para_que": "Pasar del QUÉ se dice al CÓMO se dice y desde qué ÁNGULO: "
                    "estructura de las frases, arcaísmos, marcos interpretativos "
                    "y tono hacia actores concretos.",
        "resultado": "Tablas por artículo de relaciones SVO, cadenas de "
                     "correferencia, densidad de arcaísmos, frame dominante, "
                     "polaridad y, en Validación, el Kappa de concordancia.",
        "interpretar": "ENCUADRE (framing): clasifica cada artículo por el "
                       "ÁNGULO (guerra, modernidad, mujer, nación…), no por el "
                       "tema literal; el frame 'dominante' es el de mayor "
                       "léxico, pero un texto puede combinar varios. POLARIDAD: "
                       "pos/neg/neutro discriminante, mejor que el sesgo a "
                       "'confianza' del modelo de 8 emociones; 'polaridad hacia "
                       "X' mide el tono en una ventana alrededor de la entidad, "
                       "sin cruzar de un artículo a otro. MORFOLOGÍA HISTÓRICA: "
                       "una densidad de arcaísmos baja (~0.6 %) indica español ya "
                       "moderno en 1939, hallazgo en sí mismo. VALIDACIÓN: el "
                       "Kappa de Cohen mide acuerdo entre tu etiquetado "
                       "automático y uno humano sobre una muestra; >0.6 es "
                       "aceptable, >0.8 bueno. Reportar Kappa es la defensa de "
                       "fiabilidad que una revista exige antes de creer en "
                       "cualquier clasificación automática.",
    },

    "sem": {
        "que_es": "Análisis semántico de tono, léxico y estilo: emociones "
                  "(NRC), subjetividad, intensidad y rasgos estilométricos del "
                  "texto.",
        "para_que": "Caracterizar el registro de la prensa: ¿es sobrio o "
                    "exaltado?, ¿factual u opinativo?, ¿qué emociones predominan "
                    "en su retórica?",
        "resultado": "Perfiles de emoción (8 categorías), índices de "
                     "subjetividad/intensidad y métricas de estilo por artículo "
                     "o corpus.",
        "interpretar": "El léxico de emociones NRC tiende a sobre-representar "
                       "'confianza' (palabras neutras que el diccionario marca "
                       "como positivas): por eso para polaridad pura conviene el "
                       "módulo discriminante de Lingüística. Lee el perfil "
                       "emocional como RETÓRICA del texto, no como la emoción del "
                       "autor ni del lector. La subjetividad alta marca opinión/"
                       "editorial; la baja, registro informativo. Estos "
                       "diccionarios se calibraron en lengua moderna: en 1930 "
                       "algunos términos tenían otra carga, así que valida una "
                       "muestra. Un perfil 'sobrio, dominado por confianza' es un "
                       "hallazgo defendible sobre el ESTILO de la publicación.",
    },

    "top": {
        "que_es": "Topic modeling: descubre automáticamente los TEMAS "
                  "latentes del corpus agrupando palabras que tienden a "
                  "aparecer juntas (NMF/BERTopic).",
        "para_que": "Obtener un mapa temático del corpus sin leerlo entero: "
                    "qué grandes asuntos lo organizan y cómo se distribuyen "
                    "entre números.",
        "resultado": "Una lista de tópicos, cada uno descrito por sus palabras "
                     "más representativas, y el peso de cada tópico por "
                     "documento.",
        "interpretar": "Los tópicos son agrupaciones ESTADÍSTICAS de palabras, "
                       "no categorías predefinidas: tú les pones nombre leyendo "
                       "sus términos principales, y ese paso es interpretativo. "
                       "El número de tópicos es una decisión tuya: pocos = "
                       "temas vagos, muchos = temas redundantes/ruidosos; "
                       "pruébalo y justifícalo. Un tópico dominado por "
                       "fragmentos de OCR es basura, no un tema. La coherencia "
                       "del tópico (¿sus palabras 'cuelgan juntas' para un "
                       "humano?) importa más que cualquier métrica automática. "
                       "Reporta cómo elegiste el número de tópicos y qué nombre "
                       "les diste: sin eso, el modelo no es replicable.",
    },

    "viz": {
        "que_es": "Visualizaciones avanzadas: nubes de palabras limpias, "
                  "mapas de calor temporales, redes y gráficos comparativos "
                  "del corpus.",
        "para_que": "Comunicar patrones de un vistazo y explorar el corpus "
                    "visualmente, tanto para tu propio análisis como para las "
                    "figuras del paper.",
        "resultado": "Figuras (PNG/HTML) listas para incrustar: nubes, "
                     "heatmaps, redes, comparativas.",
        "interpretar": "Las visualizaciones PERSUADEN, así que sé honesto: una "
                       "nube de palabras muestra frecuencia, no importancia, y "
                       "sin limpieza léxica se llena de ruido OCR y stopwords "
                       "(aquí hay una capa de lematización + filtro). El tamaño "
                       "de fuente no es una medida precisa; para comparar usa "
                       "barras. Los heatmaps temporales revelan estacionalidad/"
                       "picos, pero su color depende de la escala elegida — "
                       "decláralo. Toda figura del paper necesita pie con la "
                       "fuente de datos y el método; una figura bonita sin "
                       "método no es evidencia.",
    },

    "comp": {
        "que_es": "Análisis comparativo interno: contrasta subconjuntos del "
                  "mismo corpus (por número, sección, periodo) en sus métricas "
                  "léxicas, temáticas o de tono.",
        "para_que": "Detectar diferencias y evolución dentro del corpus: "
                    "¿cambia el vocabulario entre números?, ¿difiere el tono "
                    "por sección?",
        "resultado": "Tablas y gráficos comparativos lado a lado de los "
                     "grupos elegidos.",
        "interpretar": "Compara grupos de tamaño parecido: un subconjunto "
                       "mucho mayor domina las frecuencias absolutas, así que "
                       "usa proporciones o medidas normalizadas. Una diferencia "
                       "visible no es necesariamente SIGNIFICATIVA: con pocos "
                       "documentos puede ser azar; si el paper lo exige, "
                       "respáldala con un test. Asegúrate de comparar lo "
                       "comparable (no mezcles publicidad con artículos). Las "
                       "diferencias más interesantes suelen ser cualitativas "
                       "(qué palabras cambian), no sólo cuantitativas.",
    },

    "comp2": {
        "que_es": "Comparación multi-corpus: contrasta ESTE proyecto con "
                  "otro distinto (otra revista, otro periodo, otro medio).",
        "para_que": "Situar tu corpus frente a un punto de referencia externo: "
                    "qué tiene de propio Estampa frente a otra publicación.",
        "resultado": "Métricas y figuras comparativas entre dos o más "
                     "corpus.",
        "interpretar": "El riesgo principal es comparar manzanas con naranjas: "
                       "corpus de distinto tamaño, época, calidad de OCR o "
                       "criterios de segmentación NO son directamente "
                       "comparables. Normaliza (proporciones, tasas por mil "
                       "palabras) y declara las diferencias de origen. Lo que "
                       "distingue a un corpus de otro puede deberse al objeto de "
                       "estudio o a un artefacto del procesamiento: descarta lo "
                       "segundo antes de afirmar lo primero. Bien hecho, el "
                       "contraste externo es lo que da relieve a tus hallazgos.",
    },

    "intxt": {
        "que_es": "Análisis intertextual: detecta pasajes que comparten texto "
                  "o citas entre artículos (la misma noticia republicada, "
                  "fuentes comunes) por similitud TF-IDF.",
        "para_que": "Rastrear circulación de textos y dependencias entre "
                    "piezas: qué se copia, qué se cita, qué se reescribe.",
        "resultado": "Pares de artículos con su grado de similitud y los "
                     "fragmentos compartidos.",
        "interpretar": "Una similitud alta sugiere reutilización, pero "
                       "distingue cita legítima de fórmula compartida de la "
                       "época (frases hechas, teletipos): no todo solapamiento "
                       "es plagio ni copia directa. Fija un umbral y justifícalo: "
                       "demasiado bajo trae coincidencias triviales, demasiado "
                       "alto sólo duplicados exactos. El OCR ruidoso BAJA las "
                       "similitudes reales (errores distintos en cada copia), así "
                       "que la herramienta subestima la intertextualidad en "
                       "corpus degradados. Verifica siempre los pares "
                       "candidatos leyendo los fragmentos.",
    },

    "meta": {
        "que_es": "Extracción de metadatos desde una URL externa: recupera "
                  "datos bibliográficos/catalográficos de un recurso en línea.",
        "para_que": "Completar la ficha del corpus o de una fuente con datos "
                    "estructurados sin teclearlos a mano.",
        "resultado": "Campos de metadatos (título, autor, fecha, "
                     "identificadores) extraídos del recurso.",
        "interpretar": "Verifica siempre los metadatos recuperados contra la "
                       "fuente: los catálogos en línea tienen errores y campos "
                       "ambiguos. Anota la fecha de captura y la URL exacta: el "
                       "recurso puede cambiar o desaparecer. Estos metadatos "
                       "alimentan tu citación y tu paquete de publicación, así "
                       "que un dato erróneo aquí se propaga a la bibliografía "
                       "final.",
    },

    "vis": {
        "que_es": "Análisis visual y tipográfico: examina la materialidad de "
                  "la página —fuentes, negritas/cursivas, número y disposición "
                  "de fotos, filetes— más allá del texto.",
        "para_que": "Estudiar el DISEÑO de la prensa ilustrada como objeto: "
                    "cómo la tipografía y la imagen construyen sentido, no sólo "
                    "las palabras.",
        "resultado": "Inventario de elementos visuales y rasgos tipográficos "
                     "por página.",
        "interpretar": "Es el puente entre el análisis textual y la cultura "
                       "visual del impreso. La detección de fotos/elementos "
                       "depende de la calidad de imagen: en microfilm saturado de "
                       "tinta el detector puede dar 0 elementos por el origen, no "
                       "por error del método; valídalo sobre imágenes limpias. La "
                       "presencia de negrita/cursiva marca jerarquías editoriales "
                       "(titulares, destacados) interpretables como énfasis. Para "
                       "una revista, el análisis de la materialidad gráfica es un "
                       "aporte distintivo frente a estudios sólo textuales.",
    },

    "imgdesc": {
        "que_es": "Descripción e iconografía de imágenes: la IA describe el "
                  "contenido de las fotos/ilustraciones etiquetadas (qué se ve, "
                  "quién, qué escena).",
        "para_que": "Hacer BUSCABLE y analizable el componente visual: "
                    "convertir fotos en texto descriptivo para estudiar la "
                    "iconografía de la revista.",
        "resultado": "Descripciones textuales por imagen, agregables en un "
                     "análisis iconográfico del corpus.",
        "interpretar": "Las descripciones son INTERPRETACIONES de un modelo "
                       "entrenado en imágenes modernas: puede no reconocer "
                       "personajes, ropa o contextos de 1930, y proyectar "
                       "categorías actuales. Trátalas como un primer índice a "
                       "verificar, no como descripción objetiva. Son muy útiles "
                       "para encontrar y agrupar imágenes (p. ej. todas las que "
                       "muestran multitudes, retratos, escenas bélicas), pero "
                       "el análisis iconográfico fino requiere tu mirada experta. "
                       "Documenta el modelo usado: distintos modelos describen "
                       "distinto.",
    },

    # ───────────────────────── SALIDA ──────────────────────────────────────
    "rep": {
        "que_es": "Reporte narrativo con IA: genera un texto que resume e "
                  "hila los hallazgos del proyecto en prosa académica.",
        "para_que": "Tener un borrador o andamiaje para la sección de "
                    "resultados/discusión, a partir de las métricas ya "
                    "calculadas.",
        "resultado": "Un documento narrativo en lenguaje natural con los "
                     "principales resultados.",
        "interpretar": "Es un BORRADOR asistido, no un resultado: la IA puede "
                       "redondear cifras, inferir relaciones que los datos no "
                       "sostienen o inventar matices. Trátalo como un "
                       "co-autor júnior al que hay que revisar línea por línea "
                       "contra los datos reales. Útil para vencer la página en "
                       "blanco y para verbalizar patrones, pero la "
                       "responsabilidad interpretativa y la verificación factual "
                       "son tuyas. No cites el reporte como evidencia: cita los "
                       "datos que lo respaldan.",
    },

    "dash": {
        "que_es": "Dashboard ejecutivo: panel con los indicadores clave del "
                  "corpus (tamaño, entidades, temas, tono, redes) en una sola "
                  "vista.",
        "para_que": "Tener una fotografía sintética del proyecto para "
                    "presentaciones, seguimiento y control de calidad.",
        "resultado": "Una vista agregada con cifras y mini-gráficos de las "
                     "métricas principales.",
        "interpretar": "Es un RESUMEN: cada indicador remite a un análisis más "
                       "detallado donde se interpreta con rigor; no saques "
                       "conclusiones sólo del número del dashboard. Úsalo para "
                       "control de calidad (un conteo de entidades=0 o un corpus "
                       "de 0 artículos delatan un problema aguas arriba) y para "
                       "comunicar el alcance del proyecto. Los KPIs orientan, "
                       "pero el argumento del paper se construye con los análisis "
                       "específicos, no con el panel.",
    },

    "bench": {
        "que_es": "Evaluación comparativa de las rutas de OCR: transcribe las "
                  "mismas páginas con varios motores y mide cuánto se aleja "
                  "cada uno de una transcripción que tú hiciste a mano (el "
                  "estándar de oro).",
        "para_que": "Justificar con datos qué motor usar, en vez de elegirlo "
                    "por impresión. Es la respuesta a la pregunta que hace "
                    "cualquier evaluador: «¿por qué este OCR y no otro?».",
        "resultado": "Una tabla con CER, WER, similitud de Levenshtein "
                     "normalizada y segundos por página para cada ruta, "
                     "exportable a CSV o como tabla Markdown lista para pegar "
                     "en el artículo.",
        "interpretar": "El CER (Character Error Rate) es la métrica principal: "
                       "es la proporción de caracteres que habría que corregir. "
                       "Por debajo de 0,05 el texto está casi limpio; hasta "
                       "0,10 es explotable para análisis léxico y NER; entre "
                       "0,10 y 0,25 exige corrección manual antes de analizar; "
                       "por encima de 0,25 el texto es inservible y cualquier "
                       "conclusión que saques de él será ruido. El WER siempre "
                       "sale más alto que el CER porque un solo carácter mal "
                       "invalida la palabra entera — es la métrica realista si "
                       "vas a hacer búsquedas o frecuencias. La similitud "
                       "normalizada (1 − CER) es la que reportan los papers de "
                       "HTR, úsala para comparar tus cifras con la literatura: "
                       "CHURRO reporta 0,823 en impreso histórico. Mira también "
                       "los segundos por página: una ruta con CER 0,02 que "
                       "tarda tres minutos por página sirve para construir el "
                       "estándar de oro, no para procesar mil páginas. Lo "
                       "habitual es usar la lenta y buena para crear la "
                       "referencia, y la rápida para el corpus completo. "
                       "Advertencia metodológica: el estándar de oro debe ser "
                       "una muestra REPRESENTATIVA (páginas limpias y sucias, "
                       "con y sin fotograbado), no las mejores; si eliges solo "
                       "páginas fáciles medirás una calidad que no tendrás en "
                       "producción.",
    },
    "valid": {
        "que_es": "Validación humana y semáforo de calidad: marca cada dato "
                  "como fiable (verde), dudoso (amarillo) o problemático (rojo) "
                  "y permite contrastar el etiquetado automático con humano.",
        "para_que": "Garantizar y DOCUMENTAR la fiabilidad de los datos antes "
                    "de publicar: separar lo confirmado de lo que falta "
                    "revisar.",
        "resultado": "Un estado de calidad por dato/entidad y métricas de "
                     "concordancia (acuerdo %, Kappa de Cohen) sobre muestras.",
        "interpretar": "El semáforo prioriza tu esfuerzo de revisión: ataca "
                       "primero el rojo. El Kappa de Cohen es el dato duro: "
                       "corrige el acuerdo esperado por azar; valores >0.6 = "
                       "aceptable, >0.8 = bueno, <0.4 = pobre (tu etiquetado "
                       "automático no es fiable y hay que mejorarlo). La muestra "
                       "de validación se extrae con semilla fija para que sea "
                       "REPRODUCIBLE. Reportar concordancia inter-codificador no "
                       "es opcional en una revista seria: es lo que separa una "
                       "afirmación cuantitativa creíble de una impresión. La "
                       "matriz de confusión te dice DÓNDE falla el método "
                       "(qué categorías confunde).",
    },

    "colab": {
        "que_es": "Colaboración y trazabilidad: registra quién hizo qué en el "
                  "proyecto y permite trabajo en equipo con historial.",
        "para_que": "Coordinar varios investigadores y dejar auditable la "
                    "cadena de decisiones sobre el corpus.",
        "resultado": "Un registro de acciones y contribuciones por persona.",
        "interpretar": "No produce análisis, sino RESPONSABILIDAD: en proyectos "
                       "colaborativos, saber quién tomó cada decisión (qué "
                       "criterio de normalización, qué anotación) es esencial "
                       "para la integridad y para los créditos de autoría. El "
                       "historial respalda la reproducibilidad: otro "
                       "investigador puede ver cómo se construyó el dato. "
                       "Acuerda con tu equipo los criterios ANTES de empezar; el "
                       "registro documenta, no sustituye, el consenso "
                       "metodológico.",
    },
}


def obtener(page_id: str) -> dict[str, str] | None:
    """Devuelve la guía del panel `page_id`, o None si no está definida."""
    return GUIA_MODULOS.get(page_id)


def resumen_visible(page_id: str) -> str:
    """Texto breve de 'qué es + para qué' para mostrar siempre bajo el título.

    Devuelve cadena vacía si no hay guía para ese panel.
    """
    g = GUIA_MODULOS.get(page_id)
    if not g:
        return ""
    return f"{g['que_es']}\n\n▸ Para qué sirve: {g['para_que']}"


def guia_interpretacion(page_id: str) -> str:
    """Texto largo 'qué resultado da + cómo interpretarlo' para la sección
    colapsable «Cómo interpretar los resultados». Vacío si no hay guía."""
    g = GUIA_MODULOS.get(page_id)
    if not g:
        return ""
    return (f"📤 Qué resultado obtienes:\n{g['resultado']}\n\n"
            f"🧭 Cómo interpretar los datos:\n{g['interpretar']}")
