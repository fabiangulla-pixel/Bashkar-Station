# Licencias de terceros

Bashkar Station es software libre con licencia **Apache-2.0** ([LICENSE](LICENSE)),
que cubre **solo su código fuente**. Usa modelos, programas y bibliotecas de
terceros, cada uno con su licencia. Este documento dice cuál es cada una,
de dónde se obtiene y si el proyecto la distribuye.

El corpus *Estampa* no es software: vea [DERECHOS.md](DERECHOS.md).

Las licencias se tomaron de la fuente de cada componente el 15-nov-2026 (ficha
del modelo, repositorio o metadatos del paquete). Esto es un inventario, no
asesoría legal. `scripts/verificar_licencias.py` comprueba en la CI que no
falte ninguna dependencia ni modelo.

## Lo que conviene saber antes de redistribuir

- **PyMuPDF** (`pymupdf`, lectura de PDF) tiene licencia **AGPL-3.0** (o
  comercial de Artifex). Instalar Bashkar desde el código no plantea problema:
  cada usuario descarga PyMuPDF. Pero **empaquetarlo** (un instalador o un
  `.exe` que lo incluya) u **ofrecer Bashkar como servicio web** trae las
  obligaciones de la AGPL para el conjunto. La demo pública de solo lectura se
  genera de antemano y no ejecuta PyMuPDF en un servidor.
- **CHURRO-3B** tiene licencia de investigación (`qwen-research`). **No se
  distribuye**: quien quiera usarlo lo descarga desde su origen y acepta esa
  licencia.
- **Los modelos de español de spaCy** (`es_core_news_sm/md/lg`) son **GPL-3.0**.
  No están en el repositorio: se descargan al instalar.
- **Los pesos de Surya** (motor opcional con GPU) usan una licencia «AI Pubs
  Open Rail-M» modificada: gratis para investigación, uso personal y empresas
  con menos de 5 millones de dólares de financiación o ingresos; el uso
  comercial más amplio exige licencia de pago.
- **Dos modelos no declaran licencia**: el NER `mrm8488/bert-spanish-cased-finetuned-ner`
  y el de sentimiento `pysentimiento/robertuito-sentiment-analysis`. Su
  sustitución se evalúa en el hito B5 de [PLAN_MVP.md](PLAN_MVP.md).

## Modelos

| Modelo | Uso en Bashkar | Licencia | Cómo se obtiene |
|---|---|---|---|
| `stanford-oval/churro-3B` | OCR, Ruta 6 (opcional) | `qwen-research` (derivado de Qwen2.5-VL-3B) | **No se distribuye.** Descarga opcional desde Hugging Face al usar la ruta (~7 GB) |
| `mrm8488/bert-spanish-cased-finetuned-ner` | NER | **No declarada** en su ficha | Se descarga al instalar |
| `pysentimiento/robertuito-sentiment-analysis` | Análisis de sentimiento | **No declarada** en su ficha (entrenado con TASS 2020) | Se descarga al usar el análisis |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Embeddings y búsqueda semántica | Apache-2.0 | Se descarga al instalar |
| `es_core_news_sm` | NER de respaldo, sintaxis | GPL-3.0 | Se descarga al instalar |
| `es_core_news_md`, `es_core_news_lg` | Alternativas más grandes (opcionales) | GPL-3.0 | Instalación manual opcional |
| `CATMuS-Print` (modelo de Kraken) | OCR con Kraken (opcional) | CC BY 4.0 (atribución) | Descarga opcional desde Zenodo |
| Motores entrenados de PERO-OCR | OCR, Ruta 7 (opcional) | No declarada en su sitio | Descarga manual opcional |
| Modelos de Surya | OCR con GPU (opcional) | AI Pubs Open Rail-M modificada (ver arriba) | Descarga opcional, en su propio entorno |
| Modelos de PaddleOCR / PP-Structure | OCR con GPU (opcional) | No declarada en el repositorio | Descarga opcional, en su propio entorno |

## Programas externos

| Programa | Uso | Licencia | Cómo se obtiene |
|---|---|---|---|
| Tesseract OCR | OCR por defecto | Apache-2.0 (Leptonica: tipo BSD) | El usuario lo instala (instalador de UB Mannheim en Windows) |
| Poppler | Convertir PDF en imágenes | GPL (heredada de xpdf; ver su archivo COPYING) | `instalar.py` lo descarga en la carpeta del usuario |
| Kraken | OCR (opcional) | Apache-2.0 | `pip install kraken` (opcional) |
| PERO-OCR | OCR, Ruta 7 (opcional) | BSD-3-Clause (código) | `pip install pero-ocr` (opcional) |
| Surya | OCR con GPU (opcional) | Apache-2.0 (código) | Entorno aparte (ver INSTALACION.md) |
| PaddleOCR | OCR con GPU (opcional) | Apache-2.0 (código) | Entorno aparte (ver INSTALACION.md) |
| Ollama, LM Studio | Modelos de lenguaje locales (opcional) | Las de cada programa y modelo | El usuario los instala |

Los servicios en la nube (Anthropic, OpenAI, Google Gemini) son opcionales y
se rigen por las condiciones de cada proveedor; el usuario pone su propia
clave.

## Dependencias de Python

Versiones fijadas en `requirements.lock.txt`. Licencia según los metadatos que
publica cada paquete; «no declarada» significa que el paquete no la indica en
sus metadatos, no que carezca de ella.

<!-- INICIO tabla generada por scripts/verificar_licencias.py --tabla -->
| Paquete | Versión | Licencia declarada |
|---|---|---|
| `accelerate` | 1.15.0 | Apache Software License |
| `annotated-doc` | 0.0.5 | MIT |
| `annotated-types` | 0.8.0 | MIT |
| `anthropic` | 1.4.0 | MIT License |
| `anyio` | 4.15.1 | MIT |
| `asttokens` | 3.0.2 | Apache 2.0 |
| `blis` | 1.3.3 | BSD License |
| `branca` | 0.8.2 | MIT License |
| `catalogue` | 2.0.10 | MIT License |
| `certifi` | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) |
| `cffi` | 2.1.1 | MIT-0 |
| `charset-normalizer` | 3.5.1 | MIT |
| `click` | 8.5.0 | BSD-3-Clause |
| `cloudpathlib` | 0.25.0 | MIT License |
| `cloudpickle` | 3.1.2 | BSD License |
| `colorama` | 0.4.6 | BSD License |
| `confection` | 1.3.3 | MIT License |
| `contourpy` | 1.3.3 | BSD License |
| `cryptography` | 50.0.1 | Apache-2.0 OR BSD-3-Clause |
| `cycler` | 0.12.1 | BSD License |
| `cymem` | 2.0.13 | MIT License |
| `docstring_parser` | 0.18.0 | MIT License |
| `es_core_news_sm` |  | GNU GPL 3.0 |
| `et_xmlfile` | 2.0.0 | MIT License |
| `executing` | 2.2.1 | MIT License |
| `faiss-cpu` | 1.15.0 | MIT |
| `fastapi` | 0.142.2 | MIT |
| `filelock` | 3.32.6 | MIT |
| `folium` | 0.20.0 | MIT License |
| `fonttools` | 4.64.0 | MIT |
| `fsspec` | 2026.7.0 | BSD-3-Clause |
| `google-ai-generativelanguage` | 0.6.15 | Apache Software License |
| `google-api-core` | 2.33.0 | Apache Software License |
| `google-api-python-client` | 2.200.0 | Apache Software License |
| `google-auth-httplib2` | 0.4.2 | Apache Software License |
| `google-auth` | 2.57.1 | Apache Software License |
| `google-generativeai` | 0.8.6 | Apache Software License |
| `googleapis-common-protos` | 1.75.0 | Apache Software License |
| `grpcio-status` | 1.71.2 | Apache Software License |
| `grpcio` | 1.83.1 | Apache-2.0 |
| `h11` | 0.16.0 | MIT License |
| `hf-xet` | 1.6.0 | Apache-2.0 |
| `httpcore2` | 2.12.0 | BSD-3-Clause |
| `httpcore` | 1.0.9 | BSD-3-Clause |
| `httplib2` | 0.32.0 | MIT License |
| `httpx2` | 2.12.0 | BSD-3-Clause |
| `httpx` | 0.28.1 | BSD License |
| `huggingface_hub` | 1.30.0 | Apache Software License |
| `idna` | 3.19 | BSD-3-Clause |
| `iniconfig` | 2.3.0 | MIT |
| `ipython` | 9.17.1 | BSD-3-Clause |
| `ipython_pygments_lexers` | 1.1.1 | BSD License |
| `jedi` | 0.20.0 | MIT License |
| `Jinja2` | 3.1.6 | BSD License |
| `jiter` | 0.16.0 | MIT |
| `joblib` | 1.6.0 | BSD-3-Clause |
| `jsonpickle` | 4.1.2 | BSD-3-Clause |
| `kiwisolver` | 1.5.1 | BSD License |
| `lxml` | 6.1.3 | BSD-3-Clause |
| `markdown-it-py` | 4.2.0 | MIT License |
| `MarkupSafe` | 3.0.3 | BSD-3-Clause |
| `matplotlib-inline` | 0.2.2 | BSD-3-Clause |
| `matplotlib` | 3.11.1 | Python Software Foundation License |
| `mdurl` | 0.1.2 | MIT License |
| `mpmath` | 1.3.0 | BSD License |
| `murmurhash` | 1.0.15 | MIT License |
| `narwhals` | 2.26.0 | MIT |
| `networkx` | 3.6.1 | BSD-3-Clause |
| `numpy` | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `opencv-python-headless` | 5.0.0.93 | Apache Software License |
| `openpyxl` | 3.1.5 | MIT License |
| `opentelemetry-api` | 1.45.1 | Apache-2.0 |
| `packaging` | 26.3 | Apache-2.0 OR BSD-2-Clause |
| `pandas` | 3.0.5 | BSD License |
| `parso` | 0.8.7 | MIT License |
| `pdf2image` | 1.17.0 | MIT License |
| `pillow` | 12.3.0 | MIT-CMU |
| `pluggy` | 1.6.0 | MIT License |
| `preshed` | 3.0.13 | MIT License |
| `prompt_toolkit` | 3.0.53 | BSD License |
| `proto-plus` | 1.28.2 | Apache Software License |
| `protobuf` | 5.29.6 | 3-Clause BSD License |
| `psutil` | 7.2.2 | BSD-3-Clause |
| `pure_eval` | 0.2.3 | MIT License |
| `pyasn1` | 0.6.4 | BSD-2-Clause |
| `pyasn1_modules` | 0.4.2 | BSD License |
| `pycparser` | 3.0 | BSD-3-Clause |
| `pydantic` | 2.13.5 | MIT |
| `pydantic_core` | 2.46.5 | MIT |
| `Pygments` | 2.21.0 | BSD-2-Clause |
| `pymupdf` | 1.28.2 | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial Lic |
| `pyparsing` | 3.3.2 | MIT |
| `pytesseract` | 0.3.13 | Apache Software License |
| `pytest` | 9.1.1 | MIT |
| `python-dateutil` | 2.9.0.post0 | BSD License; Apache Software License |
| `python-docx` | 1.2.0 | MIT License |
| `python-louvain` | 0.16 | BSD License |
| `python-multipart` | 0.0.32 | Apache-2.0 |
| `python-pptx` | 1.0.2 | MIT License |
| `pyvis` | 0.3.2 | BSD |
| `PyYAML` | 6.0.3 | MIT License |
| `regex` | 2026.9.3 | Apache-2.0 AND CNRI-Python |
| `requests` | 2.34.2 | Apache Software License |
| `rich` | 15.0.0 | MIT License |
| `ruff` | 0.16.6 | MIT |
| `safetensors` | 0.8.0 | Apache Software License |
| `scikit-learn` | 1.9.0 | BSD-3-Clause |
| `scipy` | 1.18.1 | BSD License |
| `seaborn` | 0.13.2 | BSD License |
| `sentence-transformers` | 6.0.1 | Apache-2.0 |
| `setuptools` | 84.0.0 | MIT |
| `shellingham` | 1.5.4 | ISC License (ISCL) |
| `six` | 1.17.0 | MIT License |
| `smart_open` | 8.0.1 | MIT License |
| `sniffio` | 1.3.1 | MIT License; Apache Software License |
| `sounddevice` | 0.5.6 | MIT |
| `spacy-legacy` | 3.0.12 | MIT License |
| `spacy-loggers` | 1.0.5 | MIT |
| `spacy` | 3.8.16 | MIT License |
| `SpeechRecognition` | 3.17.0 | BSD-3-Clause |
| `spylls` | 0.1.7 | MIT License |
| `srsly` | 2.5.3 | MIT License |
| `stack-data` | 0.6.3 | MIT License |
| `starlette` | 1.7.0 | BSD-3-Clause |
| `sympy` | 1.14.0 | BSD License |
| `thinc` | 8.3.13 | MIT License |
| `threadpoolctl` | 3.6.0 | BSD License |
| `tokenizers` | 0.23.2 | Apache Software License |
| `torch` | 2.14.0 | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| `torchvision` | 0.29.1 | BSD |
| `tqdm` | 4.70.0 | MPL-2.0 AND MIT |
| `traitlets` | 5.16.1 | BSD License |
| `transformers` | 5.16.1 | Apache 2.0 License |
| `truststore` | 0.10.4 | MIT |
| `typer` | 0.27.2 | MIT |
| `typing-inspection` | 0.4.4 | MIT |
| `typing_extensions` | 4.16.0 | PSF-2.0 |
| `tzdata` | 2026.3 | Apache-2.0 |
| `uritemplate` | 4.2.0 | BSD 3-Clause OR Apache-2.0 |
| `urllib3` | 2.7.0 | MIT |
| `uvicorn` | 0.54.0 | BSD-3-Clause |
| `wasabi` | 1.1.3 | MIT |
| `wcwidth` | 0.8.3 | MIT |
| `weasel` | 1.0.0 | MIT License |
| `wordcloud` | 1.9.6 | MIT |
| `wrapt` | 2.4.0 | BSD-2-Clause |
| `xlsxwriter` | 3.2.9 | BSD License |
| `xyzservices` | 2026.9.1 | BSD-3-Clause |
<!-- FIN tabla generada -->
