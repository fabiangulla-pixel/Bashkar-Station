# ⬡ Bashkar Station v11.7
### Plataforma de Análisis Editorial Computacional para Publicaciones Periódicas Históricas

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1070%20passing-brightgreen.svg)](#tests)

Bashkar Station es una aplicación de escritorio **100% offline** para el análisis
computacional de publicaciones periódicas históricas en español. Desarrollada para
investigadores en historia de la prensa, estudios editoriales y humanidades digitales.

**Corpus de referencia:** Revista *Estampa* (Colombia, 1930–1940), digitalizada por
la Biblioteca Nacional de Colombia (BNC).

**Institución:** Instituto Caro y Cuervo, Bogotá, Colombia.

---

## Características principales

| Módulo | Función |
|--------|---------|
| **OCR multi-ruta** | Tesseract, Kraken CATMuS, Claude Vision, Ollama local |
| **Normalización** | Post-OCR conservadora: preserva arcaísmos del español histórico |
| **Segmentación** | Artículo como unidad atómica; señales de continuación explícitas |
| **NER híbrido** | spaCy + BERT (mrm8488) + Claude API; 6 categorías históricas |
| **Análisis léxico** | Collocates (PMI), KWIC, n-gramas, dispersión, frecuencia relativa |
| **Stopwords proyecto** | Lista personalizable por investigador/corpus |
| **Topic modeling** | LDA con scikit-learn; BERTopic opcional |
| **Redes** | Co-ocurrencia de entidades (networkx + pyvis) |
| **Wikidata** | Linking de entidades a base de conocimiento global (LOD) |
| **Bitácora** | Notas situadas, hipótesis con estado, citas del corpus |
| **Timeline** | HTML interactivo con vis.js, por sección/tono/autor |
| **Export TEI P5** | XML-TEI válido con entidades en `<standOff>` |
| **Export BibTeX** | Referencias bibliográficas para gestores de citas |
| **METHODS.md** | Sección de metodología automática para papers |
| **Paquete publicación** | ZIP con TEI + BibTeX + CSV + Bitácora + Métodos |
| **CLI** | Pipeline completo sin interfaz gráfica |
| **HTR dataset** | Export de ground truth para reentrenamiento Kraken |

---

## Instalación rápida

### Requisitos previos
- Python 3.9 o superior
- pip actualizado (`python -m pip install --upgrade pip`)

### Paso 1 — Instalar dependencias
```bash
python instalar.py
```
El instalador gestiona automáticamente:
- Paquetes Python (PyMuPDF, spaCy, transformers, FAISS, etc.)
- Modelo spaCy español (`es_core_news_sm`)
- Tesseract OCR en Windows
- Poppler en Windows

### Paso 2 — Ejecutar la app
```bash
python app.py
```
O en Windows: doble clic en `Ejecutar.bat`.

### Línea de comandos (sin GUI)
```bash
python cli.py --proyecto ruta/a/proyecto.bashkar --etapas ocr,norm,seg,anal,ner
python cli.py --proyecto ruta/a/proyecto.bashkar --info
```

---

## Guía de inicio rápido

### Flujo típico de análisis

```
1. Configuración ──→ Define la publicación, carpetas, parámetros OCR
2. Extracción    ──→ OCR del corpus (Tesseract recomendado, PSM 3)
3. Normalizar    ──→ Revisar y corregir texto página por página
4. Segmentar     ──→ Detectar artículos, títulos y autores
5. Analizar      ──→ NER, LDA, campos semánticos, Word2Vec
6. Resultados    ──→ Exportar TEI, BibTeX, paquete de publicación
```

### Flujo alternativo (PDFs con texto embebido BNC)
```
1. Configuración ──→ Definir parámetros
2. Conversor PDF ──→ Extrae texto sin re-OCR (7 seg por número)
3. Normalizar    ──→ Revisar texto extraído
4. Segmentar     ──→ Artículos
5. Analizar / Resultados
```

### Análisis rápido sin proyecto
Haz clic en **⚡** en la barra superior para cargar una carpeta de TXT
directamente sin crear proyecto. Útil para demostraciones o análisis exploratorio.

---

## Versión web (segundo frontend)

Bashkar Station también puede usarse desde el navegador. No es una reescritura:
`servidor_web.py` es un segundo frontend que consume exactamente los mismos
módulos `core/` y la misma clase `Estado` (`core/estado.py`) que la app de
escritorio — ambos comparten el 100% de la lógica de negocio.

### Modo local (un solo usuario, en tu propia máquina)
```bash
python servidor_web.py
```
Abre `http://127.0.0.1:8421`. Mismo comportamiento que la app de escritorio:
estado global, acceso a las carpetas del disco, sin login.

### Modo público (multi-sesión, para desplegar y compartir)
```bash
BASHKAR_PASSWORD=tu-clave python servidor_web.py     # Windows: set BASHKAR_PASSWORD=tu-clave
```
Cada visitante recibe su propia sesión aislada (cookie `sid`, `HttpOnly`) tras
iniciar sesión con la contraseña. Ningún visitante ve los proyectos, el estado
ni las claves de API de otro. Las claves de proveedor de IA se guardan **solo
en memoria de la sesión**, nunca en disco. Las sesiones inactivas por más de
6 h se liberan automáticamente.

### Capacidades según el host
El frontend consulta `/api/capacidades` y **oculta con un aviso explícito**
lo que no esté disponible en el servidor donde corre (Tesseract, Poppler,
spaCy español) en vez de dejar que el usuario elija algo que va a fallar. En
un despliegue remoto sin Tesseract/Poppler, el **Conversor PDF** (texto
embebido vía PyMuPDF) sigue funcionando completo — es la ruta recomendada
para corpus BNC / Paper Capture en modo web.

### Qué está portado en este tramo
Configuración/proyectos, Conversor PDF, Normalizar, Segmentar, Analizar
(léxico básico), Entidades (NER con spaCy), Resultados (TEI/BibTeX/CSV) y
Dashboard. El resto de los 29 paneles del escritorio (Etiquetador, OCR
multi-ruta, Lingüística, Redes, etc.) muestran su guía HD y quedan señalados
como pendientes de portar — la lógica ya vive en `core/`, solo falta la vista.

### Desplegar en Render
Ver [`render.yaml`](render.yaml). El puerto lo inyecta Render vía `PORT`;
la contraseña se configura como variable de entorno en el dashboard (nunca
se commitea).

---

## Arquitectura técnica

```
bashkar_station/
├── app.py              # Frontend escritorio (Tkinter, ~20.000 líneas)
├── servidor_web.py     # Frontend web (http.server stdlib, sin frameworks)
├── web/                # Frontend web: HTML/CSS/JS vanilla, sin build
├── cli.py              # Interfaz de línea de comandos
├── instalar.py         # Instalador de dependencias
├── core/               # 80+ módulos de procesamiento (sin dependencia de UI)
│   ├── estado.py               # Estado del proyecto — compartido por ambos frontends
│   ├── ocr_engine.py           # Motor OCR multi-ruta
│   ├── ocr_normalizer.py       # Normalización post-OCR histórica
│   ├── article_segmenter.py    # Segmentación de artículos
│   ├── ner_engine.py           # NER híbrido spaCy+BERT+Claude
│   ├── collocation_engine.py   # Collocates, KWIC, n-gramas, dispersión
│   ├── bitacora_engine.py      # Notas de investigación situadas
│   ├── timeline_engine.py      # Timeline HTML interactiva
│   ├── tei_engine.py           # Export XML-TEI P5 + validación
│   ├── okf_export_engine.py    # Export bundle OKF (Open Knowledge Format)
│   ├── methods_reporter.py     # METHODS.md automático
│   ├── kraken_trainer.py       # Dataset HTR para reentrenamiento
│   └── voice_dictation.py      # Dictado por voz en Normalizar
├── datos/              # Capa de datos SQLite
│   ├── schema.py       # DDL: articulos, ocr, entidades, notas_investigacion…
│   └── repositorio.py  # DAO único punto de acceso
└── tests/              # 1000+ tests (pytest)
```

**Decisiones de diseño:**
- **Tkinter** — incluido con Python, cero dependencias de UI, funciona 100% offline
- **JSON + SQLite** — proyectos inspeccionables con cualquier editor o Excel
- **Offline-first** — todas las funciones analíticas funcionan sin internet; Claude/GPT son opcionales
- **Página como unidad atómica** — la sub-segmentación intra-página es imposible con el OCR de la BNC (columnas mezcladas); se documenta como decisión metodológica
- **Arcaísmos preservados** — el normalizador NO moderniza el español de los años 30

---

## Decisiones metodológicas documentadas

| Decisión | Razón |
|----------|-------|
| Página = unidad atómica | OCR BNC mezcla columnas en stream lineal sin información espacial recuperable |
| Sin lematización por defecto | Preserva variación ortográfica histórica como dato lingüístico |
| Stopwords personalizables | Corpus histórico requiere listas propias (topónimos, arcaísmos válidos) |
| Tres rutas OCR | Cada ruta tiene trade-offs documentados (tiempo, costo, calidad); el investigador elige |
| Multi-proveedor IA | Sin dependencia de un proveedor; degrada gracefully a spaCy/BERT offline |

---

## Exportación para publicación

El botón **📦 Paquete publicación** genera un ZIP con:

```
paquete_publicacion_YYYYMMDD.zip
├── corpus.xml      ← XML-TEI P5 (validado con validar_tei())
├── corpus.bib      ← BibTeX de todas las unidades
├── entidades.csv   ← Índice NER completo
├── bitacora.md     ← Notas del investigador en Markdown
├── METHODS.md      ← Sección de metodología lista para el paper
└── metadatos.json  ← Versiones de software, parámetros, estadísticas
```

---

## Reproducibilidad

Bashkar Station genera automáticamente un archivo **METHODS.md** con:
- Versiones exactas de todos los paquetes usados
- Parámetros del pipeline (DPI, idioma OCR, modelo NER, etc.)
- Estadísticas del corpus (páginas, palabras, artículos, entidades)
- Decisiones metodológicas aplicadas

Este documento está diseñado para incluirse directamente en la sección
de Metodología de papers en revistas de humanidades digitales.

---

## Citación

Si usas Bashkar Station en tu investigación, por favor cita:

```bibtex
@software{gulla_bashkar_station_2026,
  author    = {Gulla, Fabián},
  title     = {Bashkar Station: Plataforma de Análisis Editorial Computacional
               para Publicaciones Periódicas Históricas},
  year      = {2026},
  version   = {11.7},
  url       = {https://github.com/fabiangulla-pixel/Bashkar-Station}
}
```

Los metadatos de citación legibles por máquina están en
[`CITATION.cff`](CITATION.cff).

---

## Tests

```bash
# Todos los tests
python -m pytest tests/ -v

# Solo tests de integración
python -m pytest tests/test_integration_pipeline.py -v

# Tests de features v11
python -m pytest tests/test_v11_features.py -v
```

**Estado actual:** 1070 tests, 0 fallos (14 se saltan por requerir red o
dependencias opcionales). Verificado el 29-jul-2026 en Python 3.14.

---

## Licencia

**Apache License 2.0** — ver [LICENSE](LICENSE) y [NOTICE](NOTICE).

Software libre: puedes usarlo, estudiarlo, modificarlo y redistribuirlo,
incluso con fines comerciales, conservando el aviso de copyright y de licencia
e indicando los cambios que hagas. La licencia incluye una concesión expresa de
patentes. Se ofrece sin garantías.

El corpus de la revista *Estampa* **no** se distribuye con el software: fue
digitalizado por la Biblioteca Nacional de Colombia y tiene sus propias
condiciones de uso. La licencia de este repositorio cubre únicamente el código.

---

## Agradecimientos

- **Biblioteca Nacional de Colombia (BNC)** — acceso al corpus digital de la revista Estampa
- **Instituto Caro y Cuervo** — apoyo institucional y financiamiento de la investigación
- Metodología inspirada en: Impresso Project (EPFL), Newspaper Navigator (Library of Congress)
