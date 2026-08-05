# Referencia

Las fichas de los treinta paneles, la solución de los problemas más frecuentes
y un glosario. Esta parte está pensada para consultarla, no para leerla seguida.

## Los treinta paneles

Las fichas que siguen **se generan desde el código fuente de la aplicación**,
del mismo archivo que alimenta la ayuda que aparece dentro de cada panel. Por
eso el manual no puede contradecir a la interfaz: si una guía cambia en el
programa, cambia aquí al regenerar el documento.

Cada ficha responde a cuatro preguntas: qué es, para qué sirve, qué resultado
produce y cómo interpretar ese resultado. La última es la más útil, porque
incluye los umbrales y las trampas de cada método.

{{REFERENCIA_PANELES}}

## Cuando algo no funciona

### La aplicación no abre

Si se lanza desde un acceso directo o un archivo por lotes y no ocurre nada, lo
primero a comprobar es la **ruta**: los accesos directos antiguos pueden apuntar
a carpetas que se renombraron. Un archivo por lotes bien hecho comprueba que la
carpeta existe y avisa en lugar de cerrarse en silencio.

Si se ejecuta desde el código fuente y parece colgado en el primer arranque,
puede estar instalando dependencias. Es normal la primera vez.

### La ventana se congela

Las operaciones largas corren en segundo plano y la ventana debería seguir
respondiendo. Si se congela al cambiar de página en Normalizar o en el
Etiquetador, conviene comprobar que la carpeta de trabajo **no esté en una unidad
de red o en una carpeta sincronizada en la nube**: cada lectura pasa a ser una
consulta remota.

La aplicación guarda en caché local las páginas ya vistas, así que la segunda
visita a una página es mucho más rápida que la primera.

### El reconocimiento devuelve cero palabras

Es el síntoma clásico de una página de microfilm inclinada. En orden:

1. Etiquetar las zonas y usar la ruta por zonas, que corrige la inclinación y
   trata cada región por separado.
2. Si sigue sin salir nada, probar Kraken o CHURRO-3B.
3. Si tampoco, es probable que la imagen de origen no tenga información
   recuperable. Conviene verificarlo con el visor antes de invertir más tiempo.

### Un modelo de visión no aparece disponible

El panel indica el motivo en lugar de fallar a mitad de un trabajo. Los motivos
habituales son que falte descargar el modelo —hay un botón para ello— o que la
biblioteca correspondiente no esté instalada, en cuyo caso el propio mensaje
indica qué hacer.

### El proyecto de ayer no aparece

Está en el botón grande de continuar de la pantalla de bienvenida, con su fecha
de última modificación. La lista de recientes no repite el proyecto actual. Si
el nombre despista, conviene recordar que corresponde a la fecha de **creación**,
no a la del último trabajo.

## Glosario

**CER** (*character error rate*). Proporción de caracteres que habría que
corregir en una transcripción automática respecto de una de referencia. Es la
métrica principal para evaluar reconocimiento de texto.

**Corpus**. El conjunto de textos sobre el que se trabaja, con sus metadatos.
En esta aplicación, un corpus se organiza en números, páginas y artículos.

**Entidad nombrada**. Una persona, lugar, organización, fecha, obra o evento
mencionado en el texto. Identificarlas permite pasar del análisis de palabras al
análisis de actores.

**Estándar de oro**. Transcripción hecha a mano que se toma como verdad para
medir el error de los métodos automáticos.

**HTR** (*handwritten text recognition*). Reconocimiento de texto manuscrito.
Se distingue del OCR clásico, pensado para impresos.

**Kappa de Cohen**. Medida de acuerdo entre dos codificadores que corrige el
acuerdo esperado por azar. Por encima de 0,6 se considera aceptable; por debajo
de 0,4, pobre.

**Lematizar**. Reducir cada palabra a su forma de diccionario. Útil para contar
frecuencias, destructivo para estudiar variación ortográfica histórica.

**OCR** (*optical character recognition*). Reconocimiento óptico de caracteres:
convertir la imagen de un texto impreso en texto codificado.

**Orden de lectura**. La secuencia en que deben leerse las zonas de una página
para reconstruir el discurso. En maquetación a varias columnas no coincide con
el orden de arriba abajo.

**TEI**. *Text Encoding Initiative*, el estándar de codificación de textos en
humanidades digitales. Permite marcar estructura, entidades y variantes de forma
interoperable.

**Tokenizar**. Dividir un texto en unidades mínimas de análisis, normalmente
palabras. Es el primer paso de casi cualquier procesamiento lingüístico.

**Wikidata**. Base de conocimiento colaborativa que asigna un identificador
único a cada entidad. Enlazar a ella convierte una mención en un dato citable y
comparable entre proyectos.

**Zona**. Región rectangular de una página con una tipología asignada: artículo,
título, pie de foto, fotografía, publicidad, filete. El reconocimiento trabaja
sobre las zonas que llevan texto.
