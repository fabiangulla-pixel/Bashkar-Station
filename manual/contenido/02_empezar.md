# Poner en marcha

Dos capítulos para pasar de no tener nada a tener un corpus analizable. El
primero instala; el segundo recorre el camino completo con un solo número de
revista, para que la lógica del conjunto quede clara antes de entrar en detalle.

## Instalar y abrir por primera vez

Bashkar Station se distribuye de dos maneras, y la elección depende de si se va a
programar sobre ella o solo a usarla.

### Con el ejecutable (lo habitual)

Basta copiar la carpeta `BashkarStation` y hacer doble clic en
`BashkarStation.exe`. No hay instalación, ni permisos de administrador, ni
dependencias que resolver: todo viaja dentro, incluidos los motores de análisis.

La carpeta ocupa alrededor de 1,7 GB, así que cabe en cualquier memoria USB y
funciona igual en otro equipo. El primer arranque tarda unos veinte segundos
porque carga los modelos lingüísticos; los siguientes son más rápidos.

### Desde el código fuente (para desarrollar)

```
git clone https://github.com/fabiangulla-pixel/Bashkar-Station.git
cd Bashkar-Station
python instalar.py
python app.py
```

`instalar.py` resuelve las dependencias de Python, descarga el modelo de spaCy
para español e instala Tesseract y Poppler en Windows si faltan.

:::aviso Requisitos reales
Python 3.9 o superior (el desarrollo se hace sobre 3.14). Para los modelos de
visión hacen falta al menos 16 GB de memoria: un modelo de tres mil millones de
parámetros ocupa cerca de doce. Sin ellos, el resto de la aplicación funciona
con holgura en 8 GB.
:::

### La primera pantalla

Al abrir aparece una pantalla de bienvenida con tres opciones: continuar el
último proyecto, crear uno nuevo o abrir uno existente. Si se cierra sin elegir,
la aplicación crea un proyecto automático para no dejar al usuario en el vacío.

Un **proyecto** es un archivo `.bashkar` más una carpeta hermana con los datos
pesados. Guarda la configuración, el progreso de cada etapa y las rutas del
corpus; no guarda las imágenes, que permanecen donde estén.

:::aviso Las claves de interfaz de programación se guardan en claro
Si se configuran claves de servicios de nube, quedan escritas en el archivo
`.bashkar` **en texto plano y en el disco**. Es una limitación conocida, no un
descuido: el archivo nunca sale del equipo y nunca entra al repositorio. Pero si
se comparte un `.bashkar` con un colega, hay que borrar las claves antes.
:::

## Tu primer corpus en veinte minutos

Este recorrido usa un solo número de revista en PDF y llega hasta un texto
segmentado en artículos. Es el camino corto: sirve para entender la lógica antes
de afinar nada.

### 1 · Configurar el proyecto

En **⚙ Configuración** se indican tres cosas: el nombre de la publicación, el
periodo, y la carpeta donde están los archivos de entrada. La carpeta de salida
se crea sola y organiza el trabajo en subcarpetas numeradas —`01_pdfs`,
`02_imagenes`, `03_ocr`, `04_analisis`, `05_etiquetas`— que se irán llenando en
orden.

:::atajo Si el PDF ya trae texto
Muchos PDF de bibliotecas digitales llevan una capa de texto de un
reconocimiento previo. En ese caso, el panel **⚡ Conversor PDF** extrae ese
texto directamente y ahorra el reconocimiento entero: un número de cuarenta y
ocho páginas en unos siete segundos. Merece la pena comprobarlo antes de
empezar.
:::

### 2 · Obtener el texto

Si no hay texto embebido, hay que reconocerlo. El panel **📄 Extracción OCR**
ofrece varias rutas y el capítulo siguiente las compara en detalle; para este
primer recorrido, Tesseract con idioma español es suficiente.

### 3 · Revisar lo que salió

**📝 Normalizar** muestra cada página con su imagen al lado y el texto
reconocido debajo. Aquí se corrige lo que el motor entendió mal. No hace falta
dejarlo perfecto: el objetivo es que el texto sea lo bastante fiable para lo que
se vaya a preguntar después.

La aplicación conserva tres versiones de cada página —el texto crudo, la
corrección manual y la sugerencia automática— y permite elegir cuál pasa al
análisis. Esa elección se guarda con el proyecto.

### 4 · Separar los artículos

**📋 Segmentar** detecta dónde empieza y acaba cada pieza, y distingue artículo,
índice, publicidad y colofón. Aquí la unidad de trabajo deja de ser la página y
pasa a ser el artículo, que es la unidad con la que razona un investigador.

### 5 · Analizar y exportar

Con el corpus segmentado se abre todo lo demás: frecuencias, entidades, redes,
tópicos. **📈 Resultados** exporta en los formatos que pide una publicación
—TEI P5, BibTeX, hojas de cálculo— y arma un paquete completo listo para
depositar.

:::metodo Guardar es parte del método
La aplicación guarda sola cada tres minutos, y un punto ámbar junto al nombre
del proyecto avisa cuando hay cambios sin guardar. Aun así, conviene guardar a
mano antes de cualquier operación larga: la bitácora del proyecto es parte de la
trazabilidad de la investigación, no solo una copia de seguridad.
:::
