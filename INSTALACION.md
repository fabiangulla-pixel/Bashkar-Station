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

## Arrancar la aplicación

```
python app.py
```

En Windows también sirve `Ejecutar.bat`.

---

## Por qué el `.exe` no puede instalar por su cuenta

Dentro de un ejecutable de PyInstaller, `sys.executable` no apunta a Python:
apunta al **propio ejecutable**. Una versión anterior de Bashkar intentaba
instalar los paquetes que faltaban llamando a `sys.executable -m pip`, y cada
llamada relanzaba la aplicación completa. El resultado real, medido: unos 90
procesos en 12 segundos y un reinicio forzado de la máquina.

Por eso, congelado, el asistente diagnostica y te da los comandos, pero no
ejecuta nada. Es una decisión deliberada.
