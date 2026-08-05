# El problema antes que la herramienta

Este manual no empieza explicando botones. Empieza explicando qué problema
intenta resolver Bashkar Station, porque la mayoría de las decisiones de la
aplicación —incluidas las que parecen incómodas— solo tienen sentido a la luz
de ese problema.

## Qué tiene de difícil la prensa histórica

Una colección de prensa ilustrada de los años treinta no es un corpus de texto.
Es un objeto material fotografiado, y entre la fotografía y el texto analizable
hay una cadena de pérdidas que conviene mirar de frente.

**El soporte llega degradado.** Buena parte de la prensa colombiana del siglo XX
se conserva en microfilm, y la digitalización de ese microfilm arrastra su
grano, su contraste plano y la inclinación de la cámara. En el corpus de
referencia de este proyecto —la revista *Estampa*, digitalizada por la
Biblioteca Nacional de Colombia— las páginas llegan con entre doce y diecisiete
grados de inclinación y una saturación de tinta que ronda el cuarenta por
ciento.

**La página no es lineal.** Una revista ilustrada organiza el contenido en
columnas, recuadros, pies de foto, publicidad y filetes. Un motor de OCR que
lea la página de arriba abajo entrega un texto donde la primera línea de la
columna izquierda se pega con la primera de la derecha. El resultado se lee como
prosa rota y contamina cualquier análisis posterior.

**La lengua es de otra época.** El español de 1939 no es el de hoy: hay
ortografía inestable, cursivas y versalitas con función semántica, extranjerismos
sin adaptar, y nombres propios que ya no existen. Un lematizador entrenado con
prensa contemporánea trata esas variantes como errores y las borra —borrando
justo el dato que interesa al historiador de la lengua.

**Los volúmenes son grandes y el tiempo es finito.** Un año de una revista
semanal son cincuenta números de veinte páginas. Nadie los transcribe a mano, y
por eso hay que automatizar; pero automatizar sin medir el error es publicar
conclusiones construidas sobre ruido.

:::metodo Por qué esto importa para el resultado
Cada eslabón de la cadena introduce un error que el siguiente amplifica. Un OCR
con un diez por ciento de error de carácter puede parecer aceptable, pero al
llegar al reconocimiento de entidades convierte «Rifa» en «Rita» y produce dos
personas donde había un sorteo. La calidad del dato no es una preocupación
técnica previa al análisis: **es el análisis**.
:::

## Qué es Bashkar Station, y qué no es

Bashkar Station es una **plataforma de escritorio que orquesta la cadena
completa**, desde la imagen escaneada hasta los formatos que exige una
publicación académica. Reúne en un solo entorno el reconocimiento de texto, la
normalización, la segmentación en artículos, el análisis lingüístico y la
exportación, sin obligar a salir a la línea de comandos ni a encadenar scripts
sueltos.

Conviene decir también lo que **no** es:

- **No es un framework ni una biblioteca.** Aquí no se programa. Es una
  herramienta de consumo y orquestación, pensada para el investigador que tiene
  las preguntas, no necesariamente para quien escribe el código.
- **No es un servicio en la nube.** Funciona sin conexión de principio a fin. Es
  una decisión deliberada, no una limitación, y el capítulo siguiente explica
  por qué.
- **No es una caja negra.** Cada módulo dice qué método aplica, con qué
  parámetros y con qué umbrales; y hay un módulo dedicado a medir cuánto se
  equivoca.

## Las decisiones que conviene conocer

Cuatro decisiones de diseño explican la mayor parte del comportamiento de la
aplicación. Un usuario que las entiende deja de pelearse con la herramienta.

### Funciona sin conexión por defecto

La aplicación arranca con un interruptor global apagado: mientras no se active
explícitamente, ninguna función llama a un servicio externo. El recorrido
completo está cubierto en local —reconocimiento con Tesseract o Kraken, modelos
lingüísticos de spaCy, búsqueda semántica con FAISS, y modelos de lenguaje
locales a través de Ollama o LM Studio— sin coste por página.

Las interfaces de programación en la nube existen, son opcionales y exigen
configurar una clave. Cuando se usan, la aplicación **estima el coste y lo
muestra antes de ejecutar**, y registra el gasto real después.

:::aviso No es una comodidad, es un requisito
Trabajar con prensa histórica implica material sujeto a las condiciones de uso
de la institución que lo digitalizó. Que el corpus no salga del equipo salvo
decisión explícita del investigador no es una preferencia técnica: es lo que
permite firmar un convenio con una biblioteca.
:::

### La página es la unidad atómica

El texto se organiza por página y no por artículo continuo, porque el
reconocimiento de una página escaneada no conserva información espacial
suficiente para reconstruir con fiabilidad qué columna sigue a cuál. La
segmentación en artículos ocurre **después**, sobre texto ya revisado, y las
señales de continuación entre páginas se marcan de forma explícita.

### No se lematiza por defecto

La variación ortográfica histórica es un dato lingüístico, no un error. Reducir
«assí» a «así» antes de analizar destruye evidencia sobre la norma escrita de la
época. La lematización está disponible cuando la pregunta la requiere, pero hay
que activarla a conciencia.

### Se etiquetan las zonas antes de reconocer el texto

Este es el punto que más cuesta al principio y el que más rendimiento da. Antes
de pasar el reconocimiento, el investigador marca sobre la imagen qué es cada
región: artículo, título, pie de foto, fotografía, publicidad, filete. El motor
de reconocimiento trabaja **solo sobre las zonas que llevan texto**, en el orden
de lectura que se le indicó.

:::dato Cuánto cambia esto, medido
Sobre una página real de *Estampa*, Tesseract aplicado a la página completa
devolvió **cero palabras**. La misma página, recortada por zonas etiquetadas,
devolvió **578 palabras**. El etiquetado previo no es un trámite: es lo que
hace utilizable al motor rápido.
:::

## El corpus de referencia

Todo lo que se explica en este manual se ha probado sobre la revista *Estampa*
(Bogotá, 1930-1940), un semanario ilustrado digitalizado por la Biblioteca
Nacional de Colombia. Se eligió porque reúne todas las dificultades a la vez:
microfilm degradado, maquetación a varias columnas con fotograbado, publicidad
integrada en el cuerpo, y una lengua que ya es moderna pero conserva usos de
época.

Los ejemplos y las cifras de este manual proceden de ese corpus. Cuando aparece
un número medido, procede de una ejecución real y se indica sobre qué material.
