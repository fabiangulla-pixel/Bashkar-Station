# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Bashkar Station v10.3
# Run: pyinstaller bashkar_station.spec --clean

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

APP_DIR = Path(SPECPATH)

block_cipher = None

# SDK de Google Gemini (extracción multimodal IA). Puede no estar instalado en
# todos los entornos de build; si no está, no se rompe el spec.
_google_genai_imports = []
try:
    _google_genai_imports = collect_submodules('google.generativeai')
except Exception:
    _google_genai_imports = []

a = Analysis(
    [str(APP_DIR / 'app.py')],
    pathex=[str(APP_DIR)],
    binaries=[],
    datas=[
        # Incluir assets gráficos
        (str(APP_DIR / 'assets'), 'assets'),
        (str(APP_DIR / 'Logo_Bashkar_Station.png'), '.'),
        (str(APP_DIR / 'logo_sidebar.png'), '.'),
        # Datos de la app: gazetteer de coordenadas, stopwords, personajes (JSON/TXT)
        (str(APP_DIR / 'datos' / 'coordenadas_colombia.json'), 'datos'),
        (str(APP_DIR / 'datos' / 'personajes_historicos_co.json'), 'datos'),
        (str(APP_DIR / 'datos' / 'stopwords_historicas_es.txt'), 'datos'),
        # Archivos de configuración de rutas (si existen)
        (str(APP_DIR / 'tesseract_path.txt'), '.') if (APP_DIR / 'tesseract_path.txt').exists()
            else (str(APP_DIR / 'README.md'), '.'),
        (str(APP_DIR / 'poppler_path.txt'), '.') if (APP_DIR / 'poppler_path.txt').exists()
            else (str(APP_DIR / 'requirements.txt'), '.'),
        # Diccionario spylls español
        ('C:/Users/Lenovo/AppData/Roaming/Python/Python314/site-packages/spylls/hunspell/data/es',
         'spylls/hunspell/data/es'),
    ],
    hiddenimports=[
        # Core modules
        'core',
        'core.text_extractor',
        'core.ocr_normalizer',
        'core.article_segmenter',
        'core.alto_reconstructor',
        'core.spell_corrector',
        'core.visual_analyzer',
        'core.image_analyzer',
        'core.layout_analyzer',
        'core.project_manager',
        'core.analysis_engine',
        'core.charts',
        'core.comparative_analyzer',
        'core.excel_export',
        'core.image_describer',
        'core.image_exporter',
        'core.metadata_extractor',
        'core.metadata_fetcher',
        'core.ocr_engine',
        'core.word_vectors',
        'core.text_postprocessor',
        'core.image_preprocessor',
        'core.ner_engine',
        'core.ner_roberta_local',
        'core.sentiment_engine',
        'core.collocation_engine',
        'core.topic_engine',
        'core.zone_labeler',
        'core.novelty_engine',
        'core.annotation_engine',
        'core.busqueda_semantica' if False else 'core.embeddings_local',
        'core.chart_builder',
        'core.gutter_completion',
        'core.deepfont',
        'core.visual_classifier',
        'core.visual_search',
        'core.explainer',
        'core.article_segmenter_v2',
        'core.ocr_llm',
        'core.ocr_kraken',
        'core.ocr_normalizer',
        'core.entity_linker',
        'core.vocabulario_controlado',
        'core.exploradores',
        'core.morfologia_historica',
        'core.network_engine',
        'core.stylometry_engine',
        'core.lexicon_engine',
        'core.intertextual_engine',
        'core.tei_engine',
        'core.pipeline_maestro',
        'core.colaboracion',
        'core.confianza_engine',
        'core.storytelling_engine',
        'core.comparador',
        # Extracción multimodal IA + guía de módulos (sesiones 41-42)
        'core.extractor_multimodal',
        'core.guia_modulos',
        'core.costos',
        'core.image_captioner',
        'core.layout_tesseract',
        # Motores portados de ¡Quac! + lingüística computacional (sesiones 27-37)
        'core.frame_engine',
        'core.sentimiento_discriminante',
        'core.revision_engine',
        'core.validacion_engine',
        'core.sintaxis_engine',
        'core.coref_engine',
        'core.viz_engine',
        'core.timeline_engine',
        'core.bitacora_engine',
        'datos',
        'datos.repositorio',
        'datos.schema',
        'datos.migracion',
        'exportadores',
        # PyMuPDF
        'fitz',
        # spylls
        'spylls',
        'spylls.hunspell',
        'spylls.hunspell.dictionary',
        # NLP
        'spacy',
        'spacy.lang.es',
        'es_core_news_sm',
        'gensim',
        'gensim.models',
        'gensim.models.ldamodel',
        'gensim.models.word2vec',
        # sklearn
        'sklearn',
        'sklearn.feature_extraction',
        'sklearn.feature_extraction.text',
        'sklearn.decomposition',
        'sklearn.metrics',
        'sklearn.metrics.pairwise',
        # scipy
        'scipy',
        'scipy.sparse',
        # plotting
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'seaborn',
        # data
        'pandas',
        'openpyxl',
        'networkx',
        # image / ocr
        'cv2',
        'PIL',
        'PIL._tkinter_finder',
        'pdf2image',
        'pytesseract',
        # web
        'requests',
        'urllib3',
        # standard
        'statistics',
        'unicodedata',
        'json',
        'csv',
        'zipfile',
        'threading',
        'queue',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
    ] + _google_genai_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Deep learning — pesados e innecesarios en runtime
        'torch', 'torchvision', 'torchaudio', 'detectron2',
        'tensorflow', 'tensorflow_core', 'keras',
        'cupy', 'cuml', 'numba', 'llvmlite',
        # spaCy internals — PyInstaller se queda sin RAM intentando introspeccionar thinc
        'thinc', 'blis', 'cymem', 'preshed', 'murmurhash',
        'srsly', 'wasabi', 'catalogue', 'confection', 'weasel',
        'spacy.lang', 'spacy.pipeline', 'spacy.training',
        'spacy.cli', 'spacy.tests',
        # ML pesados no usados en runtime
        'sklearn.datasets', 'sklearn.tests',
        'scipy.spatial.transform', 'scipy.io', 'scipy.stats',
        # Otros innecesarios
        'onnx', 'onnxruntime',
        'jupyter', 'IPython', 'ipykernel', 'ipywidgets',
        'test', 'tests', 'unittest',
        'tkinter.test',
        # Grandes paquetes de visualización no usados directamente
        'bokeh', 'plotly', 'altair', 'dash',
        # Audio / video
        'pygame', 'cv2.tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BashkarStation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Sin ventana de consola (app Tkinter)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(APP_DIR / 'bashkar_station.ico'),
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BashkarStation',
)
