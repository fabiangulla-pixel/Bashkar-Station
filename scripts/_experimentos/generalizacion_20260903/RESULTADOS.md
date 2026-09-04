# Prueba de generalización de Bashkar Station — 3 de septiembre de 2026

Medición sobre **un ejemplar de cada una de las nueve publicaciones** disponibles
(Biblioteca Nacional de Colombia), 12 páginas muestreadas de cada uno por la
**ruta de producción** (`alto_reconstructor.reconstruir_texto_pagina`, con
`ignorar_ocr_basura=True`).

Alcance: sirve para orientar decisiones, no para afirmar nada sobre las
colecciones completas.

## Resultado principal

| Publicación | Tokens | Fusión | Fragmento | Estado |
|---|---:|---:|---:|---|
| El Nuevo Tiempo (1902) | 3.003 | 0,07 % | **35,6 %** | crítico |
| La Semana Cómica | 7.159 | 0,01 % | **20,8 %** | crítico |
| La Mujer | 7.323 | 0,20 % | 7,4 % | aceptable |
| **Estampa 1939** | 8.218 | 0,26 % | 6,8 % | **línea base** |
| Panida (1915) | 2.988 | 0,00 % | 6,2 % | aceptable |
| Agitación Femenina | 11.866 | 0,03 % | 4,0 % | aceptable |
| Rin-Rin | 2.953 | 0,00 % | 2,6 % | aceptable |
| El Gráfico | 60 | — | — | **falla total** |
| El Día | 0 | — | — | **falla total** |

De nueve publicaciones: **cinco funcionan, dos se degradan gravemente, dos fallan
por completo.**

## Hipótesis falsada

Se predijo que el **piso absoluto** del umbral de separación de palabras
(`max(0.15, 0.018 × tamaño_fuente)`) causaría fusiones en tipografías pequeñas:
por debajo de 6,52 pt el factor relativo efectivo supera 0,023 y sale del rango
que el propio módulo documenta como admisible. *El Nuevo Tiempo*, a 5,27 pt, da
0,0285.

**La predicción es falsa.** Bajar el piso de 0,15 a 0,02 no elimina ni una sola
fusión en ninguna publicación; solo añade 31 fragmentos en *El Nuevo Tiempo*. La
fusión de palabras **no es un problema en ningún corpus de la muestra**: el
máximo es la propia *Estampa* con 21 casos en 8.218 tokens (0,26 %).

El arreglo del umbral relativo hecho en la sesión 65 resolvió el problema de
fusión de verdad, y lo resolvió para todas las publicaciones, no solo para las
dos con las que se calibró.

## El problema real: fragmentación

Es el error contrario, y nadie lo estaba midiendo. *El Nuevo Tiempo* parte más de
un tercio de sus tokens en trozos de una o dos letras; *La Semana Cómica*, uno de
cada cinco. Contra el 6,8 % de la línea base.

Un token fragmentado no es tan grave como uno fusionado —es filtrable aguas
abajo— pero con un 36 % de basura el NER y las frecuencias quedan inservibles.

## El hallazgo más grave: El Día

*El Día* declara la fuente `HiddenHorzOCR` de Adobe Paper Capture, igual que
*Estampa*. Su conjunto de fuentes es **idéntico**. Cualquier comprobación basada
en "¿tiene la capa oculta?" responde que sí y encamina el documento a la ruta
rápida.

Censo página por página del ejemplar:

```
p01–p14:      0 caracteres
p15:     18.958 caracteres
p16:     12.317 caracteres
```

**Solo 2 de 16 páginas tienen texto. El 87,5 % del ejemplar no está OCR-izado.**

Bashkar hoy procesaría este documento, tomaría la ruta rápida porque la fuente
está declarada, extraería el 12,5 % del contenido y **reportaría éxito**. Es la
misma clase de fallo silencioso que esta sesión encontró en la ingesta de
artículos y en los parches de colaboración.

**Consecuencia de diseño:** la ruta de OCR debe decidirse **por página y por
presencia real de texto**, nunca por la declaración de fuentes del documento.

## El Gráfico

Única publicación sin capa de texto en absoluto: 44 caracteres por página, que
son marca de agua. Exige OCR desde cero. Es, además, la publicación elegida como
primer contraste colombiano en el plan de la beca, así que la fase de
generalización tiene que resolver esta ruta. `core/ocr_churro.py` (CHURRO-3B,
visión local, gratis) está integrado y nunca se ha usado en serio; el modelo pesa
~7 GB y no está descargado.

## Integridad de las copias

Dos de las nueve copias desde Google Drive quedaron **truncadas en silencio**,
con aviso `Invalid request code` que dejó archivo en destino igual:

| Archivo | Copia mala | Copia buena | Porción |
|---|---:|---:|---:|
| Estampa (1939) | 44,7 MB | 116,2 MB | 38 % |
| El Nuevo Tiempo | 9,7 MB | 22,4 MB | 43 % |

Un PDF truncado abre sin protestar y solo falla al llegar al final, o cuelga a
MuPDF reconstruyendo la tabla de referencias cruzadas (>90 s por archivo). La
verificación tiene que abrir la **última** página, y procesar cada archivo en un
subproceso con límite de tiempo.

Esto confirma que la "ficha mínima por corpus" del plan —huella del archivo y
fecha de descarga— no es burocracia: es la única defensa contra medir sobre un
corpus a medias sin enterarse.

## Qué implica para el proyecto

1. La **ruta de OCR generaliza** dentro de la BNC: 8 de 9 traen capa oculta. El
   acoplamiento al formato de Paper Capture es menos grave de lo que la lectura
   del código sugería.
2. Lo que **no** generaliza es la calidad del resultado. La fragmentación varía
   de 2,6 % a 35,6 % sin que nada en el pipeline lo detecte ni lo reporte.
3. Hace falta una **métrica de calidad por documento** que dispare abstención.
   El plan ya la contempla ("¿cuándo el sistema debe abstenerse?"); esta medición
   da el umbral empírico para definirla: por encima de ~10 % de fragmentación el
   documento no es utilizable sin revisión.

## Reproducir

```
C:\build_rf\generalizacion\
  validar.py        integridad de cada PDF, aislado y con timeout
  diagnostico.py    ruta de OCR, fuentes, tamaño de tipografía
  medir_fusiones.py fusiones y fragmentos por la ruta de producción
```

## La ruta sin capa de texto: El Gráfico por Tesseract

Antes de poder medir nada hubo que resolver un bloqueo que nadie sabía que
existía: **Tesseract estaba instalado sin el idioma español**. La carpeta
`tessdata` solo tenía `eng.traineddata` y `osd.traineddata`.

Es decir: la ruta de respaldo de Bashkar —la que usa cualquier documento sin
capa de texto— estaba **muerta para español en esta máquina**, y no fallaba con
un mensaje claro sino dentro del worker. *El Gráfico*, hoy, no se podía procesar
por ninguna de las dos vías.

Resuelto instalando `spa.traineddata` (13,6 MB, `tessdata_best`) en
`C:\build_rf\tessdata` y apuntando `TESSDATA_PREFIX` ahí, sin tocar
`Program Files` ni requerir permisos de administrador.

### Resultado

| Página | Segundos | Confianza | Tokens | Fusión | Fragmento | Largo medio |
|---|---:|---:|---:|---:|---:|---:|
| p0001 (portada) | 5,3 | 86,7 | 24 | 0,00 % | 8,3 % | 6,17 |
| p0006 | 34,3 | 92,8 | 714 | 0,00 % | 2,9 % | 4,70 |
| p0011 | 40,9 | 93,0 | 955 | 0,00 % | 3,1 % | 4,57 |
| **agregado** | | | **1.693** | **0,00 %** | **3,1 %** | **4,65** |

**La ruta "mala" produce tokens más limpios que la ruta "buena".** 3,1 % de
fragmentación frente al 6,8 % de *Estampa* por su capa oculta, y cero fusiones.
Cuesta ~35 s/página a 300 dpi en vez de ser instantánea.

Muestra real del texto obtenido (página 1, *El Gráfico*, 24 de julio de 1910):

> llustraciones, información, literatura y varieades. / Directores: Alberto
> Sánchez y Abrahán Cortés M. / NO. 1 BOGOTA, JULIO 24 DE 1910 SERIE 1 […]
> descubierto el bronce hubo un vuelo tricolor de flores deste las tribunas
> hasta la imágen del Precursor: las damas habían desprendido los ramilletes que
> trajeran sobre el pecho para hacer su ofrenda.

Texto legible y coherente, con los errores típicos de OCR sobre impresión de
época (`llustraciones`, `varieades`, `Narino` por `Nariño`).

**Advertencia metodológica:** fragmentación baja no es exactitud. Estas métricas
dicen si los tokens están bien FORMADOS, no si dicen lo que dice la página.
Afirmar calidad real exige transcripción de referencia y CER, que es lo que el
plan promete y todavía no existe para esta publicación.

**Conclusión operativa:** *El Gráfico* no está bloqueado. Solo le faltaba el
idioma. Y con Tesseract funcionando, CHURRO deja de ser un rescate y pasa a ser
una mejora a comparar — lo cual es una posición mucho más cómoda.

## CHURRO: dos meses a medias sin que nadie se enterara

El modelo llevaba desde el **4 de agosto** con solo el fragmento 2 de 2 (2,5 GB
de ~7,5 GB). Faltaban el fragmento 1 (5,0 GB) y el índice del modelo.

Cada intento de descarga **en segundo plano moría a los pocos minutos sin bajar
un byte**. Solo funcionó al ejecutarla **en primer plano**, donde tardó 6 m 39 s.
Esto sugiere que el botón "Descargar modelo CHURRO" de la GUI sufre lo mismo al
lanzarse desde un hilo, y no lo reporta.

`esta_descargado()` hizo bien su trabajo: devolvía `False` correctamente porque
exige todos los fragmentos declarados en el índice, no la mera existencia de
algún `.safetensors`. Esa defensa, escrita en una sesión anterior, evitó que la
aplicación creyera tener el modelo.

### Verificación de integridad

Hugging Face nombra cada blob LFS con el SHA-256 de su contenido. Recalculados:

| Tamaño | Archivo | Fecha | Verificación |
|---:|---|---|---|
| 2,51 GB | fragmento 2 de 2 | 4-ago | **ÍNTEGRO** |
| 0,01 GB | tokenizer | 4-ago | **ÍNTEGRO** |
| 5,00 GB | fragmento 1 de 2 | 3-sep | **ÍNTEGRO** |

Los archivos viejos no estaban corruptos: simplemente estaban incompletos como
conjunto. Verificar el hash es una garantía más fuerte que volver a descargar.

## Recuento de fallos silenciosos de la jornada

Cinco, todos de la misma familia — algo se interrumpe o falta, el sistema no
protesta, y el resultado parece normal:

1. Copias truncadas desde Drive (38 % y 43 % del archivo) con aviso ignorable.
2. *El Día* declara la capa oculta y solo tiene 2 de 16 páginas OCR-izadas.
3. Tesseract sin idioma español: ruta de respaldo inservible.
4. CHURRO a medias desde agosto; la descarga en segundo plano nunca avanza.
5. (De sesiones previas, corregido hoy) 15 % de artículos perdidos por colisión
   de id, y parches sin ninguna de las 169 correcciones manuales.

Para un piloto público donde terceros suben documentos que el equipo no controla,
esto deja de ser una molestia de desarrollo y se vuelve el requisito central:
**verificar los supuestos en cada frontera y reportar lo que no se cumplió.**
