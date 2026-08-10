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
| Kraken | OCR de manuscrito e impresión antigua | No |
| Dictado por voz | Dictar notas en vez de escribirlas | No |

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
