# Recorridos de trabajo

Cada capítulo de esta parte resuelve una tarea completa, de principio a fin.
No hace falta leerlos en orden: se puede ir al que corresponda al problema que
se tenga delante.

## De la imagen al texto

Reconocer texto sobre prensa histórica no es un problema resuelto, y por eso la
aplicación no ofrece un botón sino **siete rutas**. Elegir bien ahorra semanas.

### Las rutas disponibles

| Ruta | Cómo funciona | Cuándo conviene |
|---|---|---|
| **Tesseract** | Motor clásico, local, muy rápido | Impresos limpios, o cualquier página ya etiquetada por zonas |
| **Tesseract por zonas** | Recorta cada zona, la mejora y la reconoce aparte | Maquetación a varias columnas; **es la ruta por defecto recomendada** |
| **Texto embebido (BNC)** | Extrae la capa de texto del PDF y reconstruye el orden por coordenadas | PDF de biblioteca con reconocimiento previo |
| **Kraken / CATMuS** | Modelo entrenado para impresos históricos | Tipografías antiguas donde Tesseract falla |
| **IA de visión en la nube** | Claude, GPT o Gemini leen la imagen | Páginas irrecuperables, cuando el presupuesto lo permite |
| **CHURRO-3B** | Modelo de visión de pesos abiertos, **local y gratuito** | Lo mismo que el anterior, sin coste ni salida de datos |
| **PERO-OCR** | Cadena especializada en prensa desde microfilm | El caso típico de las hemerotecas latinoamericanas |

### Cómo elegir sin adivinar

La respuesta corta: **midiendo**. El capítulo «Medir la calidad del
reconocimiento» explica cómo, y es el que convierte esta elección en una
decisión defendible ante un evaluador.

La respuesta larga tiene una regla práctica que se sostiene en datos medidos
sobre *Estampa*:

:::dato Dos mediciones sobre el mismo corpus
Sobre una página completa sin etiquetar, Tesseract devolvió **0 palabras** y
CHURRO-3B **499**, en 51 minutos de proceso.

Sobre una página etiquetada por zonas, Tesseract devolvió **578** palabras en
11 segundos y CHURRO **569** en 38 minutos.

La lectura: **el etiquetado rescata al motor rápido**, y el modelo de visión es
la herramienta para lo que ni así se recupera —o para construir la referencia
con la que se mide todo lo demás.
:::

:::aviso El recuento de palabras no mide la calidad
En esa segunda medición las dos rutas produjeron casi las mismas palabras, pero
Tesseract escribió «Rita» donde decía «Rifa», «£sta maqgnilica» donde decía
«Esta magnífica» y «s 75 00» donde decía «$ 75.00», además de inventar líneas
enteras. Para un recuento de frecuencias eso es ruido; para el reconocimiento de
entidades, «Rita» y «Rifa» son cosas distintas. Contar palabras no basta: hay
que medir el error de carácter.
:::

### Usar CHURRO-3B

Es un modelo de pesos abiertos entrenado sobre casi cien mil páginas históricas
de ciento cincuenta y cinco colecciones, veintidós siglos y cuarenta y seis
grupos lingüísticos —el español entre ellos—. Corre en el equipo, no cuesta
dinero y no saca el corpus fuera.

Pesa unos siete gigabytes que se descargan una sola vez desde el propio panel
de **⚖️ Benchmark OCR**, con el botón *Descargar modelo CHURRO*. Después
funciona sin conexión. Si se coloca la carpeta del modelo en `modelos_ia`, junto
al ejecutable, viaja con la aplicación en la memoria USB.

:::aviso Es lento, y hay que contar con ello
Entre tres y cuatro minutos por zona en un procesador de seis núcleos sin tarjeta
gráfica. Sirve para construir una referencia de calidad sobre unas decenas de
zonas, no para procesar un corpus entero. La aplicación estima el tiempo y pide
confirmación antes de lanzar un lote.
:::

## Etiquetar zonas: el paso que lo cambia todo

Es el capítulo más importante de este manual. El etiquetado parece trabajo
manual prescindible y es justo lo contrario: es lo que hace que el resto
funcione.

### Qué se hace

En **✏️ Etiquetar** se dibujan rectángulos sobre la imagen de la página y se
asigna a cada uno un tipo. Los tipos que llevan texto —artículo, título, pie de
foto, índice— se reconocen; los que no —fotografía, publicidad, filete,
cabecera, colofón, número de página— se saltan.

### Por qué importa tanto

Tres razones, y las tres tienen consecuencias medibles:

1. **Preserva el orden de lectura.** Un motor que lee la página entera mezcla
   las columnas. Uno que lee zona por zona, en el orden que se le indicó,
   entrega prosa continua.
2. **Evita el ruido.** Una fotografía no contiene texto que interese, pero un
   motor de reconocimiento intentará leerla igual y devolverá basura que luego
   contamina las frecuencias.
3. **Ahorra recursos.** Con un modelo de visión, cada zona que no se procesa son
   miles de unidades de cómputo que no se gastan. Y evita que el modelo se ponga
   a describir la imagen en lugar de transcribirla.

:::metodo El orden de lectura es una decisión editorial
La aplicación calcula un orden automático por bandas y columnas, pero se puede
corregir a mano. Ese orden es una interpretación de la maquetación, y en
publicaciones con recuadros o continuaciones puede haber más de una lectura
razonable. Conviene dejar constancia del criterio en la bitácora del proyecto.
:::

### Ayudas para no hacerlo todo a mano

Hay detección automática de zonas —por análisis de imagen o por inteligencia
artificial de visión— que propone un etiquetado inicial. Es un punto de partida,
no un resultado: siempre conviene revisarlo. También se pueden dividir y
fusionar zonas, y vincular un pie de foto con su fotografía.

## Del texto al corpus analizable

### Normalizar sin destruir

**📝 Normalizar** es donde el texto reconocido se convierte en texto fiable. La
pantalla muestra la imagen y el texto, y permite corregir palabra por palabra.

El verificador señala las palabras dudosas y propone alternativas del diccionario
y del propio corpus. Se puede ampliar el vocabulario con los nombres propios y
los términos de época que la revista usa y ningún diccionario recoge.

:::aviso Normalizar no es modernizar
La normalización de esta aplicación es deliberadamente conservadora: limpia
artefactos del reconocimiento, no la ortografía de la época. Si el original
escribe «obscuro», se queda «obscuro». Modernizar aquí destruiría el dato que
busca el historiador de la lengua.
:::

### Segmentar en artículos

**📋 Segmentar** localiza dónde empieza y acaba cada pieza y le asigna una
tipología. A partir de aquí la unidad de análisis es el artículo, que es como
razona el investigador, y no la página, que es como llegó el material.

Las continuaciones entre páginas se marcan de forma explícita, porque
adivinarlas automáticamente produce errores silenciosos difíciles de detectar
después.

## Entidades, redes y conocimiento enlazado

### Reconocer entidades

**🏷 Entidades** identifica personas, lugares, organizaciones, fechas, obras y
eventos. Combina tres métodos: un modelo estadístico de spaCy, un modelo neuronal
específico para español, y opcionalmente un modelo de lenguaje que valida los
casos dudosos.

Cada entidad recibe un semáforo de confianza. **🔍 Revisión NER**, dentro del
panel de Lingüística, presenta una cola con las dudosas para confirmarlas,
descartarlas o renombrarlas. Las decisiones quedan registradas y se aplican al
índice global.

:::metodo Por qué hay revisión humana
Ninguna combinación de modelos alcanza precisión suficiente sobre texto
histórico degradado. Una cola de revisión con trazabilidad no es una concesión:
es lo que permite escribir en el artículo cuántas entidades se validaron a mano
y con qué criterio.
:::

### Enlazar con Wikidata

Las entidades se pueden vincular a Wikidata, lo que las convierte en
identificadores globales citables. La desambiguación tiene en cuenta el contexto
del artículo, filtra por tipo de entidad y descarta homónimos modernos fuera de
la ventana histórica.

:::dato Lo que costó afinarlo
En una primera versión, cinco de cada siete entidades del corpus se enlazaban
mal: «Francisco Franco» apuntaba a un tenista colombiano y «España» a un
acorazado de 1912. Con la desambiguación actual, seis de siete son correctas. El
caso que resiste es «Alfonso López», presidente colombiano de los años treinta,
que Wikidata no distingue sin contexto adicional.
:::

### Construir la red

**🕸 Redes** construye el grafo de entidades que aparecen juntas, calcula
métricas de centralidad y detecta comunidades. Exporta a GEXF para trabajar en
Gephi.

:::aviso Una red de autores no siempre tiene sentido
En *Estampa*, el 74 % de los artículos son anónimos. Una red de coautoría sobre
ese material no mide colaboración: mide coincidencia en el mismo número, que es
trivial. Por eso la red se construye sobre entidades mencionadas y no sobre
firmas. Conviene comprobar este tipo de supuestos antes de graficar.
:::

## Medir la calidad del reconocimiento

Este capítulo describe el módulo que convierte «elegí este motor» en «medí los
motores y elegí este».

### Por qué hace falta

Elegir una ruta de reconocimiento porque «se ve mejor» no es defendible en una
publicación. **⚖️ Benchmark OCR** transcribe las mismas páginas con varias rutas
y las compara contra una transcripción de referencia hecha a mano.

### Las métricas

| Métrica | Qué mide | Cómo leerla |
|---|---|---|
| **CER** | Proporción de caracteres a corregir | ≤0,05 casi limpio · ≤0,10 explotable · ≤0,25 exige corrección · >0,25 inservible |
| **WER** | Lo mismo por palabras | Siempre mayor que el CER: un carácter mal invalida la palabra entera |
| **Similitud** | `1 − CER` | Comparable con la literatura publicada |
| **Segundos por página** | Coste en tiempo | Decide qué ruta sirve para el corpus completo y cuál solo para la muestra |

### Construir el estándar de oro

Sin transcripción de referencia solo se pueden comparar rutas entre sí. El CER
absoluto exige que alguien transcriba a mano, y la aplicación reduce ese trabajo
al mínimo.

El botón **📤 Preparar estándar de oro** exporta **un recorte por zona con
texto**, cada uno con su archivo de texto vacío al lado. Se transcriben bloques
cortos, no páginas enteras: se puede parar y seguir, y el botón **📊 Avance**
dice cuánto queda.

Las reglas de transcripción van en un archivo de instrucciones dentro de la
propia carpeta. La primera es la que más se incumple: **transcribir lo que se ve,
no lo que debería decir**. Si el original escribe «Kadet» con una sola te, se
transcribe «Kadet». El estándar mide al motor, no corrige a la revista.

:::aviso Sobre rellenar previamente con el resultado automático
La aplicación permite volcar la salida de un motor para corregirla en lugar de
escribir desde cero. Ahorra mucho tiempo y es práctica habitual, pero **sesga**:
quien corrige tiende a dar por buenos los errores que no saltan a la vista. Y si
el estándar se usa después para evaluar ese mismo motor, la comparación queda
invalidada. Por eso viene desactivado y, cuando se usa, queda registrado.
:::

### Interpretar el resultado

La tabla se exporta a hoja de cálculo o se copia como tabla lista para pegar en
un artículo. Lo habitual es que ninguna ruta gane en todo: una es exacta y lenta,
otra rápida y sucia. La decisión razonable suele ser **usar la lenta y buena para
construir la referencia, y la rápida para el corpus completo**, documentando el
error que se acepta.

## Publicar los resultados

### Formatos de intercambio

**📈 Resultados** exporta en TEI P5 —el estándar de codificación de textos en
humanidades, con las entidades en su sección correspondiente—, en BibTeX para
gestores bibliográficos, y en hojas de cálculo para análisis estadístico
posterior.

También genera un **paquete de publicación** completo: la codificación, las
referencias, las tablas, la bitácora de investigación y un documento de métodos
con los parámetros usados en cada etapa.

### El bundle de conocimiento abierto

El exportador OKF produce un directorio de archivos de texto con metadatos, sin
depender de una base de datos ni de una interfaz propia. Está pensado para que
cualquier sistema —incluidos los asistentes de inteligencia artificial— pueda
leer el conocimiento del corpus directamente.

### Obtener un identificador citable

El repositorio del proyecto puede conectarse a Zenodo, de modo que cada versión
publicada genere automáticamente un identificador digital permanente. Es el
requisito que suelen pedir las revistas de humanidades digitales para citar el
software con el que se produjo un análisis.

:::metodo La reproducibilidad es parte del resultado
Un análisis computacional que no puede repetirse no es un resultado, es una
anécdota. Guardar la bitácora, exportar el documento de métodos y depositar el
software con identificador permanente son los tres gestos que convierten un
trabajo en algo que otro investigador puede verificar.
:::
