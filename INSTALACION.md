# Instalar Bashkar Station

Guía para Windows y macOS. No hace falta saber programar.

---

## Lo más rápido: el asistente

Bashkar trae una ventana que revisa tu equipo, te dice qué falta y lo instala.

```
python setup_wizard.py
```

Verás una lista con cada componente en verde (listo), ámbar (opcional) o rojo
(falta). El botón **Instalar lo que falta** se encarga de los paquetes de
Python. Para los programas del sistema —Tesseract y Poppler— el asistente te da
el comando exacto de tu plataforma y un botón para copiarlo.

> Si abres Bashkar desde el `.exe` empaquetado, el asistente no puede instalar
> paquetes de Python: te dará los comandos para que los pegues en una terminal.
> No es una limitación caprichosa, ver la nota al final.

---

## Windows

### 1. Python

Descarga Python 3.10 o superior de [python.org](https://www.python.org/downloads/).
**Marca la casilla «Add Python to PATH»** en la primera pantalla del instalador;
es la que se olvida y la que causa que después nada funcione.

### 2. Bashkar

```
cd ruta\a\bashkar_station
python setup_wizard.py
```

### 3. Tesseract OCR

Descarga el instalador de
[UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) y, durante la
instalación, **marca el idioma español** en la lista de idiomas adicionales.

Si ya lo instalaste sin el español, no hace falta reinstalar: descarga
[`spa.traineddata`](https://github.com/tesseract-ocr/tessdata/raw/main/spa.traineddata)
y déjalo en `C:\Users\TU_USUARIO\tessdata\`. Bashkar mira ahí primero,
precisamente para no tener que pedir permisos de administrador.

### 4. Poppler

No tiene instalador: se descomprime.
Baja el `.zip` de
[poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
y descomprímelo en `C:\poppler`. Bashkar lo busca ahí.

### 5. Diccionario Hunspell español

Lo baja `python instalar.py` (paso 2b) a `~/.bashkar/diccionarios/`. Si
prefieres hacerlo a mano, toma `es_ES.aff` y `es_ES.dic` de los
[diccionarios de LibreOffice](https://github.com/LibreOffice/dictionaries/tree/master/es)
y déjalos ahí. Para usar otro diccionario, apunta la variable de entorno
`BASHKAR_DICCIONARIO_ES` a la ruta base, sin extensión.

Por qué es un paso aparte: la biblioteca `spylls` empaqueta inglés, ruso y
sueco, pero **no español**. Sin este archivo la corrección ortográfica
post-OCR no corrige nada y **no avisa** — el pipeline sigue como si todo
estuviera bien. `python instalar.py` lo reporta al final, en la verificación.

---

## macOS

> **Aviso honesto:** el código está preparado para macOS y las tres plataformas
> están cubiertas por pruebas automáticas, pero **nadie ha ejecutado todavía
> Bashkar en un Mac real**. Si eres la primera persona en hacerlo, avisa de lo
> que encuentres.

### 1. Homebrew

Si no lo tienes, pégalo en la Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Python, Tesseract y Poppler

```bash
brew install python tesseract tesseract-lang poppler
```

`tesseract-lang` trae el español. Sin él, el OCR lee tus páginas como si
estuvieran en inglés y el resultado es basura difícil de diagnosticar.

### 3. Bashkar

```bash
cd ruta/a/bashkar_station
python3 setup_wizard.py
```

### Si el OCR no encuentra Tesseract aunque `brew` diga que está

Es un comportamiento conocido de macOS, no un fallo de la instalación: una
aplicación lanzada desde Finder hereda un PATH mínimo que **no incluye
Homebrew**, así que el sistema no ve `/opt/homebrew/bin`. Bashkar ya busca ahí
explícitamente (`core/plataforma.py`), pero si usas otra ubicación, indícala en
un archivo `tesseract_path.txt` junto a `app.py` con la ruta completa.

---

## Linux (Debian / Ubuntu)

```bash
sudo apt install python3 python3-pip tesseract-ocr tesseract-ocr-spa poppler-utils
python3 setup_wizard.py
```

---

## Qué instala cada cosa

| Componente | Para qué sirve | ¿Obligatorio? |
|---|---|---|
| Paquetes de Python | El motor entero: PDF, OCR, análisis, gráficos | Sí |
| Modelo `es_core_news_sm` | Lematización, entidades, sintaxis en español | Sí |
| Tesseract + español | Reconocer el texto de las páginas escaneadas | Sí |
| Poppler | Convertir las páginas del PDF en imágenes | Sí |
| Diccionario Hunspell es_ES | Corrección ortográfica post-OCR | No |
| Kraken | OCR de manuscrito e impresión antigua | No |
| Dictado por voz | Dictar notas en vez de escribirlas | No |

---

## Reproducir el entorno exacto

`requirements.txt` declara rangos (`>=`), así que una instalación nueva trae
las últimas versiones de hoy, que no son las probadas. Para reproducir el
entorno con el que la suite quedó en verde:

```
pip install -r requirements.lock.txt
```

No es una precaución teórica: al migrar al equipo nuevo, pip resolvió
matplotlib 3.11, que eliminó un argumento que el código usaba, y el gráfico de
confianza de OCR reventaba con el código intacto.

### Qué ruta usar

| Para… | Instalar con | Por qué |
|---|---|---|
| Investigación y publicación | `requirements.lock.txt` | Resultados reproducibles: mismas versiones con que se midió |
| Compilar el `.exe` | `requirements.lock.txt` | El ejecutable debe empaquetar versiones probadas |
| CI (GitHub Actions) | `requirements.lock.txt` | Es lo que se verifica en cada push |
| Desarrollo con librerías recientes | `requirements.txt` | Rangos `>=`; puede romper algo, y la suite lo dirá |
| Despliegue web (Render) | `requirements.txt` (ver `render.yaml`) | Linux: el lock trae ruedas de Windows |

`python scripts/verificar_dependencias.py` comprueba que los dos archivos no se
hayan separado: todo paquete de `requirements.txt` debe estar fijado en el
lock, con una versión dentro de su rango. La CI lo corre en cada push.

Cada manifiesto de proveniencia (`*.proveniencia.json`, `linea_base.json`)
registra las versiones realmente instaladas y los componentes externos
(Tesseract, idioma español, Poppler, diccionario), leídos con las mismas rutas
que usa la aplicación.

Para desarrollar (tests y lint) hace falta además:

```
pip install -r requirements-dev.txt
```

---

## GPU NVIDIA y motores pesados (opcional, recomendado si hay GPU)

Desde la sesión 72 Bashkar usa la GPU cuando la hay (`core/recursos.dispositivo_torch`).
`BASHKAR_DISPOSITIVO=cpu` lo fuerza a CPU. Medido en una RTX 5080 Laptop
(16 GB) sobre 20 páginas de *Estampa*: NER con RoBERTa 15,7 s → 1,0 s;
embeddings 3,6 s → 0,3 s; mismas entidades.

### 1. torch con CUDA en el venv de Bashkar

`pip install torch` trae la versión **solo CPU**. Para GPU, reinstalar desde
el índice de PyTorch (CUDA 13.0; driver NVIDIA 580 o más reciente):

```
pip install --force-reinstall --no-deps torch==2.14.0 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
python -c "import torch; print(torch.cuda.is_available())"     # True
```

### 2. Surya y PaddleOCR, cada uno en su venv

No caben en el venv de Bashkar: Surya baja Pillow e instala otro OpenCV, y
Paddle choca con torch por las DLL de CUDA. Bashkar los llama como
**trabajadores persistentes** (`core/ocr/externo.py`): el proceso arranca una
vez, carga el modelo en la GPU y atiende página tras página.

```
py -3.12 -m venv C:\dev\venv-surya
C:\dev\venv-surya\Scripts\pip install torch==2.14.0 torchvision --index-url https://download.pytorch.org/whl/cu130
C:\dev\venv-surya\Scripts\pip install surya-ocr

py -3.12 -m venv C:\dev\venv-paddle
C:\dev\venv-paddle\Scripts\pip install paddlepaddle-gpu==3.4.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu130/ --extra-index-url https://pypi.org/simple
C:\dev\venv-paddle\Scripts\pip install "paddleocr[doc-parser]"
```

Otras rutas: variables `BASHKAR_VENV_SURYA` y `BASHKAR_VENV_PADDLE`.

**Surya 0.22 es un modelo de visión servido por llama.cpp** (vLLM no existe
en Windows). Hace falta `llama-server` con CUDA: descargar
`llama-bXXXX-bin-win-cuda-13.x-x64.zip` y `cudart-llama-bin-win-cuda-13.x-x64.zip`
de https://github.com/ggml-org/llama.cpp/releases y descomprimir ambos en
`C:\dev\tools\llama.cpp\` (o fijar `LLAMA_CPP_BINARY`).

La primera página de cada motor descarga sus modelos (Surya ~2 GB, Paddle
~1 GB, CHURRO ~7 GB).

### 3. El enrutador

`config/ocr.toml` decide qué motor lee cada página (Ruta 0 del escritorio,
`motor=auto` en la API). Sus umbrales son provisionales hasta que el
benchmark tenga referencia humana.

---

## Arrancar la aplicación

```
python app.py
```

En Windows también sirve `Ejecutar.bat`.

### La API (versión nube)

```
python -m api                    # http://localhost:8422/docs
```

Sin `BASHKAR_PASSWORD` corre en modo local (una sesión, acceso al disco,
como el escritorio). Con `BASHKAR_PASSWORD` pide `POST /api/v1/sesiones` y
un token `Bearer` por petición; cada sesión trabaja aislada.

---

## Por qué el `.exe` no puede instalar por su cuenta

Dentro de un ejecutable de PyInstaller, `sys.executable` no apunta a Python:
apunta al **propio ejecutable**. Una versión anterior de Bashkar intentaba
instalar los paquetes que faltaban llamando a `sys.executable -m pip`, y cada
llamada relanzaba la aplicación completa. El resultado real, medido: unos 90
procesos en 12 segundos y un reinicio forzado de la máquina.

Por eso, congelado, el asistente diagnostica y te da los comandos, pero no
ejecuta nada. Es una decisión deliberada.
