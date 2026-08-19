# Auditoría de motores IA — Bashkar Station

**Fecha:** 2026-08-19
**Origen:** `INSTRUCCIONES_CLAUDE_CODE_ACTUALIZACION_MOTORES_IA_2026-08-18.md`
**Fase ejecutada:** A (auditoría). Sin cambios de código en este documento.

---

## Estado actual

**Motores de OCR (7 rutas, `core/`):**
| Ruta | Módulo | Tipo | Costo |
|---|---|---|---|
| 1 | `layout_tesseract.py` (Tesseract PSM3 + heurística de bloques) | determinista, local | $0 |
| 2 | `ocr_llm.py` (Claude/GPT/Gemini/Ollama Vision) | LLM, nube u local | variable |
| — | `conversor_pdf_a_word.py` (PyMuPDF, texto embebido) | determinista, local | $0 |
| — | Kraken/CATMuS-print-fondue-large | red neuronal local (`venv-kraken`) | $0 |
| 6 | `ocr_churro.py` — CHURRO-3B (Stanford OVAL / Qwen2.5-VL) | VLM local, `transformers` | $0 |
| 7 | `ocr_pero.py` — PERO-OCR (DCGM Brno) | especializado microfilm, local | $0 |
| — | LM Studio (servidor OpenAI-compatible local) | LLM local | $0 |

**Proveedores LLM (`core/costos.py`, `core/ocr_llm.py`, `core/ner_engine.py`, `core/extractor_multimodal.py`):**
`claude` (default) · `openai` · `gemini` · `ollama` · `lmstudio`. Selección por parámetro `proveedor` string en cada llamada — **no hay interfaz `InferenceProvider` unificada**, es un branching disperso por módulo (mismo patrón repetido en 4 archivos).

**Catálogo de modelos hardcodeado** en `costos.py::PRECIOS` (fecha de verificación de precios: `2026-06-27`, ya desactualizada — faltan `claude-sonnet-4-6`→revisar contra catálogo vigente, `gpt-5.5`, `gemini-3.1-flash` recién listados sin fecha de verificación reciente) y en `app.py::_OPCIONES_MODELO` (combobox por etapa). Los ids de modelo viven en código Python, no en un archivo de configuración externo.

**NLP/análisis:** spaCy es_core_news_sm/md/lg, BERT-NER (mrm8488), sentence-transformers+FAISS, Word2Vec (backend PyTorch propio porque gensim no compila en Py3.14), Wikidata entity linking v3 (contextual).

**Dependencias críticas (`requirements.txt`):** `torch>=2.0.0`, `transformers>=4.40.0`, `accelerate>=0.30.0` (para CHURRO), `anthropic>=0.25.0`, `google-generativeai>=0.8.0` (SDK deprecado por Google a favor de `google-genai`, mantenido "por consistencia" — deuda ya documentada en el propio archivo). `pero-ocr` opcional, no instalado por defecto.

**Permisos y superficie de riesgo:**

| Permiso | Necesario | Dónde | Riesgo | Mitigación actual |
|---|---|---|---|---|
| leer archivos | sí | todo el pipeline | bajo | — |
| escribir | sí | `datos/`, exportadores | bajo | proyecto por SQLite, no sobreescribe sin acción del usuario |
| borrar | sí (acotado) | `core/local_cache.py` | bajo | solo caché de derivados, nunca el proyecto |
| shell/subprocess | sí | `ocr_kraken.py` (`ketos`), `requisitos.py`, `project_manager.py`, `plataforma.py`, `layout_neural.py`, `methods_reporter.py` | medio | guard `sys.frozen` desde el incidente de fork bomb (sesión 43); no relanza el propio intérprete en producción |
| red | sí | proveedores LLM en la nube, Wikidata, descarga de modelos HF | medio | proveedor `ollama`/`lmstudio` para trabajo 100% local si se prefiere |
| GitHub | sí, manual | releases/DOI Zenodo | bajo | token vive en el gestor de credenciales de Windows, nunca en archivo del repo |
| correo | no | — | — | — |
| Drive | sí (indirecto) | el repo vive en `I:\` (Google Drive) | medio | venvs y builds siempre en disco local (`C:\build_rf`), nunca en `I:\` — lección ya aprendida |
| credenciales | sí | `core/user_prefs.py::guardar_credenciales/cargar_credenciales` | bajo | separadas del archivo de proyecto desde sesión 43 (fix de seguridad real) |

**Aprobación humana ya exigida** para: gasto de IA antes de ejecutar (estándar costo-IA transversal), commits (hook pre-commit corre la suite completa), release de GitHub (manual, dispara el DOI).

---

## Riesgos detectados

1. **Lock-in de proveedor de facto** — aunque hay 5 proveedores intercambiables, el *patrón* de selección está copiado en 4 módulos distintos en vez de una interfaz común. Cambiar la forma de invocar un proveedor implica tocar 4 archivos.
2. **Catálogo de precios desactualizado** — `PRECIOS_VERIFICADOS_EL = "2026-06-27"`, casi 2 meses antes de esta auditoría; con 3 modelos nuevos reales publicados en agosto (Qwen3.8-27B, LFM2.5-VL-3B) el catálogo no los conoce.
3. **`google-generativeai` es SDK deprecado** — riesgo de mantenibilidad ya anotado en el propio código, sin ticket de migración a `google-genai`.
4. **Sin benchmark propio reutilizable** — hay `benchmark_ocr.py` (CER/WER/Levenshtein) pero es ad hoc para las 7 rutas actuales, no una estructura `benchmark/dataset+engines+metrics+reports` versionada que facilite añadir un motor nuevo sin tocar código de la app.
5. **Ground truth insuficiente (ya conocido, no nuevo)** — sin estándar de oro transcrito a mano, cualquier benchmark nuevo (incluido uno con Nemotron Parse o LFM2.5-VL-3B) mediría contra una referencia igual de floja que la actual.

---

## Novedades aplicables

| Novedad | Aplica a Bashkar | Evidencia | Decisión |
|---|---|---|---|
| **NVIDIA Nemotron Parse 2.0** | No, por hardware — la ficha del modelo en HuggingFace (código de ejemplo oficial) exige GPU CUDA (Ampere/Hopper/Blackwell/Turing) y no documenta ruta de CPU: `model.to("cuda:0")` es parte del snippet canónico, y `trust_remote_code=True` indica capas propias (probablemente con kernels CUDA, como es común en cabezas de detección de bboxes) que no tienen por qué tener fallback a CPU. Este equipo (Ryzen 5 5500U, sin GPU dedicada) es la misma máquina donde CHURRO-3B corre en CPU precisamente porque esa ruta SÍ lo permite — Nemotron Parse no ofrece esa alternativa según su documentación. | Verificado real en HuggingFace (nvidia/NVIDIA-Nemotron-Parse-2.0): modelo <1B parámetros pero GPU obligatoria según ficha oficial | **DESCARTAR** — decisión del usuario 2026-08-19, sin necesidad de descargar el modelo para confirmarlo: la documentación oficial ya es evidencia suficiente de incompatibilidad de hardware. Revisar de nuevo solo si NVIDIA publica una ruta CPU, o si el proyecto adquiere GPU. |
| **LFM2.5-VL-3B** | Parcial — 3.1B, ~3GB RAM, corre en el hardware real del usuario (Ryzen 5 5500U, 20GB, sin GPU — igual que CHURRO). Sirve para OCR auxiliar/grounding pero Bashkar ya tiene CHURRO-3B cumpliendo ese rol y medido (1121 s/página CPU tras la optimización de sesión 55). | Verificado real (Liquid AI, 13-ago-2026) | **PILOTO** — comparar tiempo/CER contra CHURRO-3B específicamente (mismo orden de magnitud de parámetros); promover solo si es más rápido o más preciso, no ambos a la vez porque sí. |
| **Qwen3.8-27B** | No aplica como motor de OCR/análisis de Bashkar hoy — es un modelo generalista 27B/18GB GGUF pensado para razonamiento multietapa y agentes con herramientas. Bashkar ya usa Ollama/LM Studio como proveedores locales intercambiables; añadirlo es cuestión de descargarlo, no de programarlo. | Verificado real (Alibaba, 14-ago-2026) | **BACKLOG** — anotar como opción de modelo en `_OPCIONES_MODELO`/`_MMX_MODELOS["ollama"]` cuando el usuario quiera un modelo local más capaz para NER/extracción multimodal; 18GB de RAM/VRAM es razonable en la máquina del usuario pero no se instala por decisión de la sesión, no automáticamente. |
| **Agent Plugins 1.0** | No aplica a Bashkar Station (es una app de escritorio Tkinter, no una skill de agente). Sí aplica a **Auto ISBN Chile** — ver Prioridad 2 del documento fuente, fuera del alcance de esta auditoría. | Verificado real (shipped 6-ago-2026; Amazon/Cursor/Microsoft/OpenAI/Vercel mantenedores, Anthropic no mantenedor pero Claude Code lo traduce vía CLI) | **NO APLICA** a este proyecto. |
| **Capa `InferenceProvider` propia** | Sí aplica — es el Riesgo #1 de esta auditoría (lock-in disperso en 4 módulos). | Código propio revisado | **BACKLOG PRIORITARIO** — refactor de bajo riesgo (mismo comportamiento, nueva interfaz) pero toca 4 archivos calientes (`ocr_llm.py`, `ner_engine.py`, `extractor_multimodal.py`, `costos.py`); requiere su propia sesión con suite completa en verde antes y después. |
| **Patrón multiagente lectores/escritor** | No urgente — Bashkar es un proyecto de una sola persona trabajando con un agente a la vez; el riesgo que mitiga (varias sesiones escribiendo el mismo repo) ya está cubierto por [[feedback_sesiones_paralelas_mismo_repo]] en memoria. | — | **NO APLICA** por ahora. |

---

## Matriz de puntuación (0–5, máx. 50)

| Novedad | Impacto | Calidad | Velocidad | Costo | Privacidad | Mantenib. | Portab. | Madurez | Esfuerzo* | Riesgo regresión | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Nemotron Parse 2.0 (descartado) | 4 | 4 | 0 | 4 | 3 | 4 | 0 | 3 | 3 | 4 | **29 → backlog**, pero vetado por hardware (GPU CUDA obligatoria, no disponible) — decisión: DESCARTAR |
| LFM2.5-VL-3B (piloto) | 2 | 3 | 4 | 5 | 5 | 4 | 4 | 3 | 4 | 4 | **38 → piloto prioritario** (por bajo riesgo/esfuerzo, no por impacto) |
| Qwen3.8-27B (backlog) | 2 | 3 | 2 | 4 | 5 | 5 | 5 | 3 | 5 | 5 | **39 → piloto**, pero se degrada a BACKLOG por decisión de producto (no forzar hardware, ver arriba) |
| Capa InferenceProvider (backlog prioritario) | 3 | 4 | 3 | 5 | 5 | 5 | 5 | 4 | 2 | 3 | **39 → piloto prioritario** |

*Esfuerzo puntuado alto = poco esfuerzo (según la escala 0–5 "mejor puntaje = mejor", igual que las demás columnas).

---

## Decisión

**Actualizado 2026-08-19 — implementado tras la auditoría, a petición del usuario:**

1. **Capa `InferenceProvider` — IMPLEMENTADA.** `core/inference_provider.py` (nuevo): dos funciones de despacho puras, `generate_text()` y `generate_vision()`, que unifican el árbol `if proveedor == "claude": ... elif "openai": ...` antes copiado por separado en `core/ocr_llm.py`, `core/ner_engine.py` y `core/extractor_multimodal.py` (y ya divergente: `ner_engine.validar_con_llm` no soportaba openai/gemini). Diseño deliberado: la capa NO posee las fábricas de cliente (`_cliente_claude`/`_cliente_openai`/`_cliente_lmstudio` siguen en `ocr_llm.py`, inyectadas por parámetro en cada llamada) para no romper los tests que hacen `monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", stub)`. Los tres módulos llamantes quedaron con el mismo comportamiento externo (mismos defaults de modelo por proveedor, mismo registro de `usage` para el estándar de costo-IA, mismos mensajes de error) — verificado con la suite completa antes y después del refactor, sin cambios de resultado.
2. **Nemotron Parse 2.0 — DESCARTADO**, sin necesidad de descargarlo: su ficha oficial en HuggingFace (`nvidia/NVIDIA-Nemotron-Parse-2.0`) exige GPU CUDA en el snippet de uso canónico (`model.to("cuda:0")`) y no documenta ruta de CPU, a diferencia de CHURRO-3B (que sí corre en CPU en este mismo equipo, con overhead medido y aceptado). Sin GPU dedicada en la máquina del proyecto, instalar el modelo para "probar si igual carga" no habría sido evidencia real — la documentación del propio proveedor ya certifica la incompatibilidad. Revisar de nuevo solo si NVIDIA publica soporte CPU o el proyecto suma una GPU.

LFM2.5-VL-3B y Qwen3.8-27B quedan en **BACKLOG**: no hay evidencia de que superen a CHURRO-3B/Ollama actuales para el caso de uso concreto sin medir, y el principio rector del documento fuente es no modernizar por acumulación.

**Próximo paso real, sin depender de esta auditoría:** transcribir el estándar de oro (~14 zonas ya etiquetadas en `C:\build_rf\estampa_paginas\`) — sin eso ningún benchmark nuevo (con Nemotron, LFM o el motor actual) mide nada distinto de lo que ya se sabe.
