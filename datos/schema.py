"""
datos/schema.py — DDL SQL completo para Bashkar Station.

Dos bases de datos:
  - proyecto.db   (por proyecto) — artículos, OCR, entidades, zonas, etc.
  - bashkar.db    (~/.bashkar/bashkar.db) — conocimiento global compartido
"""

# ── Schema por proyecto ────────────────────────────────────────────────────────

SCHEMA_PROYECTO = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Artículos / unidades de contenido
CREATE TABLE IF NOT EXISTS articulos (
    id              TEXT PRIMARY KEY,
    archivo_origen  TEXT,
    numero          TEXT,
    pagina_inicio   INTEGER,
    pagina_fin      INTEGER,
    tipo            TEXT DEFAULT 'articulo',
    titulo          TEXT,
    autor           TEXT,
    fecha_publicacion TEXT,
    seccion         TEXT,
    palabras        INTEGER DEFAULT 0,
    estado          TEXT DEFAULT 'pendiente',
    -- estados: pendiente | procesando | completo | error
    creado          TEXT DEFAULT (datetime('now')),
    modificado      TEXT DEFAULT (datetime('now'))
);

-- Texto OCR por artículo
CREATE TABLE IF NOT EXISTS ocr (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id     TEXT NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,
    texto_crudo     TEXT,
    texto_limpio    TEXT,
    confianza       REAL DEFAULT 0.0,
    motor           TEXT DEFAULT 'tesseract',
    version_motor   TEXT,
    creado          TEXT DEFAULT (datetime('now'))
);

-- Entidades NER
CREATE TABLE IF NOT EXISTS entidades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id     TEXT NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,
    texto           TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    -- categorías: personas | organizaciones | lugares | obras | eventos | cargos | otros
    inicio          INTEGER,
    fin             INTEGER,
    confianza       REAL DEFAULT 0.0,
    fuente          TEXT DEFAULT 'spacy',
    -- fuentes: spacy | roberta_bne | claude_api | manual
    wikidata_id     TEXT,
    wikidata_uri    TEXT,
    verificada      INTEGER DEFAULT 0
);

-- Zonas de anotación visual (etiquetador)
CREATE TABLE IF NOT EXISTS zonas_anotacion (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id     TEXT NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL,
    -- tipos: articulo | titulo | foto | publicidad | pie_foto | numero_pag | cabecera | indice | colofon
    x1              REAL NOT NULL,
    y1              REAL NOT NULL,
    x2              REAL NOT NULL,
    y2              REAL NOT NULL,
    -- coordenadas normalizadas 0.0-1.0
    texto_ocr       TEXT,
    texto_manual    TEXT,
    confianza_ocr   REAL DEFAULT 0.0,
    fuente_det      TEXT DEFAULT 'manual',
    -- fuentes: manual | opencv | layoutparser | claude_api
    verificada      INTEGER DEFAULT 0,
    creado          TEXT DEFAULT (datetime('now'))
);

-- Análisis de tono editorial por artículo
CREATE TABLE IF NOT EXISTS tono (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id     TEXT NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,
    tono_principal  TEXT,
    tono_secundario TEXT,
    confianza       REAL DEFAULT 0.0,
    resumen         TEXT,
    indicadores     TEXT,
    -- JSON list de frases indicadoras
    fuente          TEXT DEFAULT 'claude_api',
    creado          TEXT DEFAULT (datetime('now'))
);

-- Tópicos por artículo (BERTopic / LDA)
CREATE TABLE IF NOT EXISTS topicos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id     TEXT NOT NULL REFERENCES articulos(id) ON DELETE CASCADE,
    topico_id       INTEGER,
    palabras_clave  TEXT,
    -- JSON list
    peso            REAL DEFAULT 0.0,
    motor           TEXT DEFAULT 'bertopic',
    creado          TEXT DEFAULT (datetime('now'))
);

-- Co-ocurrencias de entidades (para grafos)
CREATE TABLE IF NOT EXISTS coocurrencias (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad_a       TEXT NOT NULL,
    entidad_b       TEXT NOT NULL,
    categoria       TEXT,
    peso            INTEGER DEFAULT 1,
    articulo_ids    TEXT,
    -- JSON list de artículo_ids donde co-ocurren
    UNIQUE(entidad_a, entidad_b, categoria)
);

-- ── Capa de grafo: entidades canónicas + relaciones (tripletas) ──────────────
-- Una entidad canónica funde múltiples menciones (tabla `entidades`) bajo un id
-- estable. El grafo de conocimiento se modela como tripletas en `relaciones`,
-- SIN triplestore aparte (todo en este SQLite). Cada aserción guarda procedencia
-- y confianza para trazabilidad metodológica ("Assertive Edition").
CREATE TABLE IF NOT EXISTS entidades_canonicas (
    id              TEXT PRIMARY KEY,
    -- id estable: <tipo>:<slug_nombre_norm>  p.ej. "persona:francisco-franco"
    tipo            TEXT NOT NULL,
    -- tipo: persona | institucion | lugar | publicacion | seccion | obra | evento | otro
    nombre          TEXT NOT NULL,
    nombre_norm     TEXT NOT NULL,
    -- nombre canónico en minúsculas sin tildes (para fusión y búsqueda)
    atributos       TEXT DEFAULT '{}',
    -- JSON libre: alias, fechas, cargo, coordenadas (lat/lon), etc.
    wikidata_id     TEXT,
    wikidata_uri    TEXT,
    confianza       REAL DEFAULT 1.0,
    fuente          TEXT DEFAULT 'manual',
    -- proceso que la generó: ocr | heuristica | ner | revision_manual | wikidata
    n_menciones     INTEGER DEFAULT 0,
    creado          TEXT DEFAULT (datetime('now')),
    modificado      TEXT DEFAULT (datetime('now')),
    UNIQUE(tipo, nombre_norm)
);

-- Puente mención (entidades.id) → entidad canónica. Una mención pertenece a lo
-- sumo a una canónica; permite re-fundir sin perder la mención original.
CREATE TABLE IF NOT EXISTS menciones_canonicas (
    mencion_id      INTEGER NOT NULL REFERENCES entidades(id) ON DELETE CASCADE,
    canonica_id     TEXT NOT NULL REFERENCES entidades_canonicas(id) ON DELETE CASCADE,
    fuente          TEXT DEFAULT 'auto',
    -- auto (fusión por nombre_norm/wikidata) | manual
    PRIMARY KEY (mencion_id)
);

-- Relaciones como tripletas (sujeto, predicado, objeto) entre entidades canónicas.
-- El objeto puede ser otra entidad (objeto_id) o una página/artículo (objeto_pagina).
CREATE TABLE IF NOT EXISTS relaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    origen_id       TEXT NOT NULL REFERENCES entidades_canonicas(id) ON DELETE CASCADE,
    predicado       TEXT NOT NULL,
    -- mencionado_en | colaboro_con | dirigio | publico_en | ubicado_en | aliado_de | etc.
    destino_id      TEXT REFERENCES entidades_canonicas(id) ON DELETE CASCADE,
    destino_pagina  TEXT,
    -- art_id o "<numero>:<pagina>" cuando el objeto NO es una entidad
    evidencia       TEXT,
    -- art_id o fragmento que respalda la aserción
    confianza       REAL DEFAULT 1.0,
    fuente          TEXT DEFAULT 'manual',
    -- ner | heuristica | revision_manual | wikidata | importado
    creado          TEXT DEFAULT (datetime('now'))
    -- unicidad vía índice sobre COALESCE (NULL≠NULL en SQLite rompería un UNIQUE normal)
);

-- destino_id se deja NULL cuando el objeto es una página (la FK ignora NULL);
-- la unicidad de la tripleta se garantiza con COALESCE para que NULL cuente.
CREATE UNIQUE INDEX IF NOT EXISTS idx_relaciones_unica
    ON relaciones(origen_id, predicado,
                  COALESCE(destino_id, ''), COALESCE(destino_pagina, ''));

-- Intertextualidad detectada entre artículos
CREATE TABLE IF NOT EXISTS intertextualidad (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_a      TEXT REFERENCES articulos(id) ON DELETE CASCADE,
    articulo_b      TEXT REFERENCES articulos(id) ON DELETE CASCADE,
    similitud       REAL DEFAULT 0.0,
    tipo            TEXT,
    -- cita_directa | parafraseo | tema_compartido
    fragmento_a     TEXT,
    fragmento_b     TEXT,
    fuente          TEXT DEFAULT 'faiss',
    creado          TEXT DEFAULT (datetime('now'))
);

-- Historial de llamadas IA (para trazabilidad y costo)
CREATE TABLE IF NOT EXISTS historial_ia (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id     TEXT,
    etapa           TEXT,
    -- ocr_mejora | ner | deteccion | tono | narrativas | asistente
    proveedor       TEXT,
    modelo          TEXT,
    tokens_entrada  INTEGER DEFAULT 0,
    tokens_salida   INTEGER DEFAULT 0,
    costo_usd       REAL DEFAULT 0.0,
    ok              INTEGER DEFAULT 1,
    creado          TEXT DEFAULT (datetime('now'))
);

-- Bitácora de investigación (notas del investigador situadas en corpus)
CREATE TABLE IF NOT EXISTS notas_investigacion (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT NOT NULL DEFAULT 'libre',
    -- libre | hipotesis | cita
    estado          TEXT DEFAULT NULL,
    -- hipotesis: abierta | confirmada | descartada | revisada
    texto           TEXT NOT NULL DEFAULT '',
    etiquetas       TEXT DEFAULT '[]',
    -- JSON list de strings
    ref_numero      TEXT DEFAULT '',
    ref_pagina      TEXT DEFAULT '',
    ref_art_id      TEXT DEFAULT '',
    modulo_origen   TEXT DEFAULT '',
    creado          TEXT DEFAULT (datetime('now')),
    modificado      TEXT DEFAULT (datetime('now'))
);

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_entidades_categoria ON entidades(categoria);
CREATE INDEX IF NOT EXISTS idx_entidades_texto ON entidades(texto);
CREATE INDEX IF NOT EXISTS idx_entidades_articulo ON entidades(articulo_id);
CREATE INDEX IF NOT EXISTS idx_zonas_articulo ON zonas_anotacion(articulo_id);
CREATE INDEX IF NOT EXISTS idx_tono_articulo ON tono(articulo_id);
CREATE INDEX IF NOT EXISTS idx_coocurrencias_ab ON coocurrencias(entidad_a, entidad_b);
CREATE INDEX IF NOT EXISTS idx_articulos_estado ON articulos(estado);
CREATE INDEX IF NOT EXISTS idx_articulos_numero ON articulos(numero);
CREATE INDEX IF NOT EXISTS idx_notas_tipo ON notas_investigacion(tipo);
CREATE INDEX IF NOT EXISTS idx_notas_estado ON notas_investigacion(estado);
CREATE INDEX IF NOT EXISTS idx_canonicas_tipo ON entidades_canonicas(tipo);
CREATE INDEX IF NOT EXISTS idx_canonicas_norm ON entidades_canonicas(nombre_norm);
CREATE INDEX IF NOT EXISTS idx_canonicas_wd ON entidades_canonicas(wikidata_id);
CREATE INDEX IF NOT EXISTS idx_menciones_canonica ON menciones_canonicas(canonica_id);
CREATE INDEX IF NOT EXISTS idx_relaciones_origen ON relaciones(origen_id);
CREATE INDEX IF NOT EXISTS idx_relaciones_destino ON relaciones(destino_id);
CREATE INDEX IF NOT EXISTS idx_relaciones_predicado ON relaciones(predicado);
"""

# ── Schema global (~/.bashkar/bashkar.db) ─────────────────────────────────────

SCHEMA_GLOBAL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Entidades verificadas entre proyectos
CREATE TABLE IF NOT EXISTS entidades_globales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    nombre_norm     TEXT NOT NULL,
    -- nombre en minúsculas para búsqueda
    categoria       TEXT NOT NULL,
    descripcion     TEXT,
    wikidata_id     TEXT,
    wikidata_uri    TEXT,
    nacimiento      TEXT,
    muerte          TEXT,
    ocupacion       TEXT,
    pais            TEXT,
    fuente          TEXT DEFAULT 'manual',
    confianza       REAL DEFAULT 1.0,
    creado          TEXT DEFAULT (datetime('now')),
    modificado      TEXT DEFAULT (datetime('now')),
    UNIQUE(nombre_norm, categoria)
);

-- Correcciones OCR acumuladas (aprendizaje continuo)
CREATE TABLE IF NOT EXISTS correcciones_ocr (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    texto_ocr       TEXT NOT NULL,
    texto_correcto  TEXT NOT NULL,
    frecuencia      INTEGER DEFAULT 1,
    motor_ocr       TEXT,
    creado          TEXT DEFAULT (datetime('now')),
    UNIQUE(texto_ocr, texto_correcto)
);

-- Glosario histórico global
CREATE TABLE IF NOT EXISTS glosario_global (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    termino         TEXT NOT NULL UNIQUE,
    definicion      TEXT,
    categoria       TEXT,
    -- arcaismo | neologismo | colombianismo | extranjerismo | cargo | institucion
    periodo         TEXT,
    ejemplo         TEXT,
    fuente          TEXT DEFAULT 'manual',
    creado          TEXT DEFAULT (datetime('now'))
);

-- Relaciones entre entidades (grafo de conocimiento)
CREATE TABLE IF NOT EXISTS relaciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad_a       TEXT NOT NULL,
    entidad_b       TEXT NOT NULL,
    tipo_relacion   TEXT NOT NULL,
    -- colaboro_con | publico_en | dirigio | fue_director_de | etc.
    evidencia       TEXT,
    fuente          TEXT DEFAULT 'manual',
    confianza       REAL DEFAULT 1.0,
    creado          TEXT DEFAULT (datetime('now'))
);

-- Registro de proyectos recientes
CREATE TABLE IF NOT EXISTS proyectos_recientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta            TEXT NOT NULL UNIQUE,
    nombre          TEXT,
    publicacion     TEXT,
    ultimo_acceso   TEXT DEFAULT (datetime('now'))
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ent_glob_nombre ON entidades_globales(nombre_norm);
CREATE INDEX IF NOT EXISTS idx_ent_glob_cat ON entidades_globales(categoria);
CREATE INDEX IF NOT EXISTS idx_corr_ocr ON correcciones_ocr(texto_ocr);
CREATE INDEX IF NOT EXISTS idx_glosario ON glosario_global(termino);
"""
