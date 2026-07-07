# PROMPT SISTEMA — Bashkar Station v1.1
## Replicación completa del programa

Este documento describe en detalle todo lo que hace Bashkar Station, de modo que
cualquier persona o IA pueda reconstruirlo desde cero o extenderlo.

---

## ¿Qué es Bashkar Station?

Bashkar Station es una herramienta de escritorio para **análisis editorial computacional
de publicaciones históricas digitalizadas** (revistas, periódicos, boletines).
Corre 100% offline tras la instalación inicial, salvo las funciones opcionales
que requieren internet (descripción de imágenes con IA, extracción de metadatos desde URL).

Está escrita en Python 3.11+, con interfaz gráfica en Tkinter.

---

## Arquitectura del proyecto

```
bashkar_station/
├── app.py                  — Aplicación principal (GUI Tkinter, 7 pestañas)
├── instalar.py             — Instalación de dependencias y modelos
├── Ejecutar.bat            — Lanzador Windows
├── ejecutar.sh             — Lanzador Linux/macOS
├── README.md               — Guía de usuario
├── PROMPT_SISTEMA.md       — Este documento
└── core/
    ├── ocr_engine.py       — Motor OCR (PyMuPDF + Tesseract)
    ├── text_extractor.py   — Extracción de texto de PDF/imágenes
    ├── analysis_engine.py  — NER, LDA, layout, red de autoría
    ├── article_segmenter.py— Segmentación de artículos y atribución de autoría
    ├── word_vectors.py     — Word2Vec: entrenamiento y expansión semántica
    ├── visual_analyzer.py  — Tipografía y análisis de imágenes por OpenCV
    ├── image_describer.py  — Descripción de imágenes con Claude AI (opcional)
    ├── metadata_fetcher.py — Extracción de metadatos desde URLs
    ├── comparative_analyzer.py — TF-IDF, log-likelihood G², comparativo
    └── excel_export.py     — Exportación a Excel con 10 hojas y gráficas
```

---

## Dependencias

```
pymupdf>=1.23          Lectura de PDFs (texto + imágenes)
pytesseract>=0.3.10    OCR para PDFs escaneados
Pillow>=10.0           Manipulación de imágenes
spacy>=3.7             NLP: NER, tokenización, lematización
gensim>=4.3            Word2Vec
numpy<2                Álgebra lineal
pandas>=2.0            Tablas de datos
scikit-learn>=1.4      TF-IDF, LDA
matplotlib>=3.8        Gráficas
seaborn>=0.13          Heatmaps
networkx>=3.2          Red de colaboración
openpyxl>=3.1          Exportación Excel
opencv-python-headless>=4.9   Análisis visual de imágenes
scipy>=1.12            Estadística (entropía, etc.)
```

Modelos externos (se instalan con instalar.py):
- Tesseract 5+ (OCR)
- Poppler (renderizado de PDF a imagen)
- spaCy `es_core_news_sm` (o md/lg según configuración)

---

## Flujo completo de trabajo

### PASO 1 — Configuración (pestaña ⚙️ Configuración)

El usuario define:
1. **Nombre y período** de la publicación
2. **Carpeta de entrada**: PDFs o imágenes sueltas
3. **Carpeta de salida**: donde se guardan todos los resultados
4. **Archivos a procesar**: lista con detección automática de tipo
5. **Calidad de lectura**: DPI (100/150/200/300), idioma OCR
6. **Módulos activos**: segmentación, vectores, tipografía, layout, red
7. **Ajuste fino**: precisión del NLP (sm/md/lg), N temas LDA, mínimo apariciones red
8. **Corpus de referencia** (opcional): carpeta con subcarpetas por publicación
9. **Colaboradores conocidos**: lista de nombres esperados
10. **Campos temáticos de interés**: diccionario JSON con semillas

### PASO 2 — Extracción OCR (pestaña 📄 Extracción)

Para cada PDF o imagen seleccionada:
1. **Detección automática de tipo**:
   - PDF con texto embebido (PyMuPDF directo) → extracción inmediata
   - PDF escaneado (sin texto) → renderizado como imágenes + Tesseract OCR
   - Imagen suelta → Tesseract OCR directamente
2. **Procesamiento página a página** para eficiencia de memoria
3. **Indicadores en tiempo real**: N archivos, páginas, palabras, confianza OCR, páginas para revisar
4. **Estructura de salida**:
   - `02_imagenes/{nombre_numero}/p0001.png, p0002.png…` — imágenes de páginas escaneadas
   - `03_ocr/{nombre_numero}/p0001.txt, p0002.txt…` — textos extraídos por página

### PASO 3 — Segmentación de artículos (pestaña 📝 Artículos)

**Estrategia dual según tipo de PDF:**

#### Para PDFs digitales (PyMuPDF):
- Calcula el tamaño de fuente mediano del número completo
- Detecta títulos como líneas con fuente ≥ 135% del tamaño mediano
- Condiciones adicionales: 2–12 palabras, 4–120 caracteres, sin punto/coma al final
- Nuevo artículo se abre solo cuando el bloque previo tiene ≥60 palabras
- Mínimo 60 palabras por artículo para considerarlo válido

#### Para textos OCR (heurísticas):
- Filtra watermarks: "Digitalizado Biblioteca Nacional", "HathiTrust", etc.
- Filtra ruido OCR: líneas con >45% caracteres especiales, palabras demasiado cortas
- Detecta títulos: ALL CAPS (2–12 tokens, 8–100 chars) o Mixed Case sin punto final
- Condición obligatoria: ≥60 palabras en el cuerpo previo antes de cortar
- Mínimo 80 palabras por artículo; los más cortos se fusionan con el anterior
- Consolida cortes de página: si el bloque siguiente empieza con minúscula → fusionar

**Atribución de autoría (3 niveles de confianza):**
- 0.92: Byline explícita "Por Nombre Apellido" en los primeros 700 chars
- 0.80: Firma final en MAYÚSCULAS (2–5 tokens en los últimos 500 chars)
- 0.65: Inicial + apellido al final ("J. García")
- 0.00: "Anónimo / Sin atribuir"

**Detección de sección**: 16 categorías por coincidencia de palabras clave en título+cuerpo:
Editorial, Crónica, Reportaje, Cuento, Poema/Verso, Humor/Sátira, Cine, Teatro,
Libros, Sociedad, Política, Internacional, Modas/Hogar, Publicidad, Deportes, Notas.

**Salida**: CSV `articulos_segmentados.csv` + tabla interactiva en la app.

### PASO 4 — Análisis textual (pestaña 🔍 Análisis textual)

Para cada número:
1. **NER con spaCy**: extrae entidades PER (personas), ORG, LOC, GPE
   - Filtra por colaboradores conocidos y umbrales de longitud
   - Produce lista de firmas con frecuencia
2. **LDA (Latent Dirichlet Allocation)**:
   - Corpus completo tokenizado con spaCy (lematización, sin stopwords)
   - N temas configurable (3–20)
   - Produce: palabras clave por tema, distribución por número
3. **Campos semánticos**:
   - Si Word2Vec activo: entrena modelo sobre todos los textos del corpus
     - vector_size=150, window=6, sg=1 (skip-gram), min_count=3, epochs=12
     - Para cada semilla, busca top-15 términos más cercanos (umbral sim=0.35)
     - Los términos expandidos se añaden al campo
   - Calcula densidad: menciones_campo / palabras_totales × 1000
4. **Red de colaboración**:
   - Nodos: autores con ≥ N_min apariciones
   - Aristas: dos autores conectados si comparten número
   - Exporta `.graphml` compatible con Gephi
5. **Layout de página** (si activo):
   - Análisis de bloques PyMuPDF: proporción texto/imagen por página
   - Número de columnas, estimación de márgenes

### PASO 5 — Análisis visual y tipográfico (pestaña 🖼️ Visual & Tipografía)

#### Sub-pestaña Tipografía (PDFs con texto digital):
- Extrae todos los spans de PyMuPDF con: fuente, tamaño, flags (bold/italic), color
- Normaliza nombres de fuente internos a nombres legibles (ej. "ABCDEF+TimesNewRomanPSMT" → "Times New Roman · Negrita")
- Clasifica en: Romana, Palo seco, Egipcia, Monoespaciada, Caligráfica
- Calcula por número: fuente principal, N fuentes, tamaño cuerpo (mediana), tamaño titular (percentil 90), interlineado relativo, N columnas, % negrita, % cursiva, imágenes embebidas

#### Sub-pestaña Elementos gráficos (PDFs escaneados / imágenes):
Para cada página PNG:
1. Umbralización adaptativa (ADAPTIVE_THRESH_GAUSSIAN_C)
2. Dilatación morfológica con kernel grande para agrupar regiones
3. Detección de contornos → bounding boxes
4. Clasificación de cada región:
   - **Fotografía**: varianza>1200 AND rango_dinámico>130 AND tonos_medios>25% AND entropía>3.0
   - **Ilustración/caricatura**: fondo_blanco>45% AND gradiente>15 AND bimodal (bins_activos<45%)
   - **Publicidad**: densidad_negro_y_blanco alta OR fondo_oscuro
   - **Decorativo**: aspecto>8 o <0.12 (elementos muy alargados)
   - **Mixto**: fallback con varianza moderada
5. Por cada elemento detectado:
   - Tipo + confianza (0–1)
   - Tamaño en mm (a partir de DPI configurado)
   - Posición en la página: coordenadas relativas + zona (9 zonas: superior/centro/inferior × izq/centro/der)
   - Pie de foto si existe (banda horizontal bajo el elemento con densidad de tinta 4–30%)
6. **Diagrama de layout** por página: figura matplotlib con rectángulos coloreados por tipo, dimensiones en mm, numeración, leyenda

#### Descripción con IA (opcional, requiere API key de Anthropic):
- Para cada elemento de tipo Fotografía, Ilustración o Publicidad
- Envía el recorte a `claude-sonnet-4-20250514` con prompt específico
- Obtiene JSON con: tipo_ai, descripción, personas (total/hombres/mujeres), texto_visible, autor_firma, temática, calidad_imagen, notas investigación

### PASO 6 — Análisis comparativo (pestaña 📊 Comparativo)

Requiere carpeta de referencia con estructura:
```
referencia/
  El_Tiempo/
    numero_01.txt
    numero_02.txt
  Cromos/
    numero_01.txt
```

Para cada publicación (incluyendo la principal):
1. **Perfil TF-IDF**: peso de cada término en cada corpus (discriminante)
2. **Similitud coseno**: qué tan parecida es la publicación a cada referencia (0–1)
3. **Palabras distintivas (log-likelihood G²)**:
   - Para cada referencia, calcula qué palabras son estadísticamente más frecuentes
     en la publicación principal vs. esa referencia
   - G² = 2 × Σ observed × log(observed/expected)
   - Positivo = más frecuente en publicación principal
   - Muestra top 30 palabras con mayor G²
4. **Comparación de campos semánticos**: densidad de cada campo en cada corpus

### PASO 7 — Resultados y exportación (pestaña 📈 Resultados)

**Indicadores globales**: Números procesados, páginas, palabras, artículos, autores, firmas NER

**9 sub-pestañas con gráficas**:
- Secciones: barras horizontales con paleta variada
- Firmas: barras horizontales con diferenciación documentado/NER
- Campos semánticos: gráfico de áreas con líneas (evolución temporal)
- Artículos: barras horizontales + donut de secciones
- Temas LDA: heatmap YlOrRd
- Red de autoría: grafo spring layout
- Visual: barras de conteo + área de evolución
- Comparativo: barras agrupadas + radar/spider
- Layout: área apilada texto/imagen

**Excel con 10 hojas** (`{Publicacion}_Analisis_Editorial.xlsx`):
1. `Páginas` — tabla completa de extracción con métricas OCR
2. `Firmas` — entidades detectadas por número
3. `Campos` — densidad semántica por número y campo
4. `Layout` — proporción texto/imagen por página
5. `Red` — tabla de nodos y aristas del grafo de autoría
6. `Temas_LDA` — distribución de temas por número
7. `Hoja_KWIC` — concordancias de palabras clave seleccionadas
8. `Resumen` — indicadores globales consolidados
9. `Artículos` — tabla de artículos con autor, confianza, sección
10. `Visual_Tipografía` — métricas tipográficas + elementos visuales por página
11. `Análisis_Comparativo` — matriz de similitud + palabras distintivas + perfil campos

---

## Función de extracción de metadatos desde URL

M�dulo `core/metadata_fetcher.py`.

Acepta cualquier URL de archivo digitalizado en la web y extrae:
- Título, autor, fecha, institución, descripción, idioma
- Temas/palabras clave, tipo de documento, derechos
- Editorial, lugar, número, volumen, ISSN

**Estrategias** (en orden de prioridad):
1. Detección de catálogos específicos:
   - Biblioteca Nacional de Colombia (Sirsi/Dynix): parsea ID del fichero, intenta API
   - HathiTrust: extrae JSON de HTApp.setMetadata()
   - Internet Archive: extrae window.__INITIAL_STATE__
2. Estándares semánticos:
   - Dublin Core (dc.title, dc.creator, dc.date…)
   - Open Graph (og:title, og:description…)
   - Schema.org / JSON-LD (Book, Periodical, Article…)
3. Extracción heurística del DOM: `<title>`, `<h1>`, meta description, author

---

## Paleta de colores y tipos de gráficas

Paleta de 14 colores claramente diferenciados:
`#4E79A7` (azul acero), `#F28E2B` (naranja ámbar), `#E15759` (rojo coral),
`#76B7B2` (verde agua), `#59A14F` (verde musgo), `#EDC948` (mostaza),
`#B07AA1` (malva), `#FF9DA7` (rosa), `#9C755F` (marrón tabaco),
`#BAB0AC` (gris cálido), `#17BECF` (cian), `#8C6D31` (bronce),
`#D62728` (rojo vivo), `#AECBAC` (verde salvia).

Tipos de gráfica utilizados:
- **Barras horizontales**: secciones, firmas, autores (top N)
- **Áreas apiladas con líneas**: campos semánticos (evolución temporal)
- **Área apilada**: distribución texto/imagen
- **Donut/anillo**: secciones de artículos
- **Heatmap**: temas LDA (seaborn, cmap YlOrRd)
- **Grafo (spring layout)**: red de colaboración
- **Barras agrupadas**: comparativo de campos semánticos
- **Radar/spider**: perfil temático comparativo
- **Barras verticales + áreas**: elementos visuales
- **Diagrama de layout** (matplotlib figuras separadas por página)

---

## Prompt para Claude AI (descripción de imágenes)

```
Sistema: Eres un experto en análisis de prensa histórica hispanoamericana
de la primera mitad del siglo XX. Analizas imágenes recortadas de páginas
de revistas y periódicos digitalizados. Respondes SIEMPRE en español y
SOLO con JSON válido.

Usuario: [imagen en base64] + "Analiza este elemento visual extraído de
una página de revista histórica." → JSON con: tipo, confianza_tipo,
descripcion, personas {total, hombres_estimados, mujeres_estimadas},
texto_visible, autor_firma, tematica, epoca_estimada, calidad_imagen, notas
```

Modelo: `claude-sonnet-4-20250514`
M�x. tokens: 600 por elemento

---

## Parámetros clave del modelo Word2Vec

- `vector_size`: 150 (dimensiones del espacio vectorial)
- `window`: 6 (ventana de contexto: 6 palabras a cada lado)
- `sg`: 1 (skip-gram, mejor para corpus pequeños)
- `min_count`: 3 (mínimo de apariciones para incluir una palabra)
- `epochs`: 12 (pasadas de entrenamiento)
- `workers`: 4 (paralelismo)
- Umbral de similitud para expansión: 0.35 (coseno)
- Top-N vecinos explorados: 30; retenidos por umbral: ≤15

---

## Parámetros del algoritmo de segmentación

- Umbral de título para PDF digital: fuente ≥ mediana × 1.35
- Mínimo palabras en cuerpo previo para cortar artículo: 60
- Mínimo palabras en artículo resultante: 80 (OCR) / 60 (PDF digital)
- Watermarks filtrados: "Digitalizado Biblioteca Nacional", "HathiTrust", etc.
- Ruido OCR: líneas con >45% caracteres especiales, palabras <2 chars, fragmentos
- Consolidación: fusiona si el siguiente bloque empieza con minúscula (corte de página)

---

## Cómo reproducir el programa

1. Crea la estructura de carpetas indicada en "Arquitectura"
2. Implementa cada módulo siguiendo las descripciones de este documento
3. Instala las dependencias con `pip install -r requirements.txt`
4. Descarga los modelos: `python -m spacy download es_core_news_sm`
5. Para Windows: instala Tesseract 5+ y Poppler y registra sus rutas en .txt
6. Ejecuta `python app.py`

El estado global de la aplicación se mantiene en la clase `Estado` (singleton `ST`).
Los workers (OCR, segmentación, análisis, visual, comparativo) corren en hilos
separados y comunican progreso vía `queue.Queue`.

---

*Bashkar Station — Instituto Caro y Cuervo / Universidad de los Andes*
*Versión 1.1 — Generado automáticamente*
