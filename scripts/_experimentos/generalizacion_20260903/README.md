# Prueba de generalización — 3 de septiembre de 2026

Scripts y resultados de la primera medición de Bashkar Station contra
publicaciones distintas de *Estampa*. Responde la pregunta de evaluación n.º 1
del plan de Becas Leonardo: si el pipeline generaliza "sin reglas fijas de una
sola publicación".

**`RESULTADOS.md` es el documento; los scripts son cómo se obtuvo.**

## Qué hace cada uno

| Script | Qué mide |
|---|---|
| `validar.py` | Integridad de cada PDF, en subproceso aislado con timeout |
| `diagnostico.py` | Ruta de OCR que tomaría cada publicación, fuentes, tipografía |
| `medir_fusiones.py` | Fusiones y fragmentos por la ruta de producción real |
| `tesseract_grafico.py` | Tesseract sobre *El Gráfico* (única sin capa de texto) |
| `churro_grafico.py` | CHURRO-3B sobre las mismas páginas, para comparar |
| `esperar_y_lanzar_churro.py` | Espera a que haya RAM libre y lanza CHURRO solo |

## Cómo reproducir

Los PDF de muestra **no** están en el repositorio: pesan 205 MB y son material
de la Biblioteca Nacional. Se copian desde la carpeta de publicaciones a disco
local (nunca se leen desde Google Drive: es lentísimo y trunca en silencio) y
los scripts apuntan a `C:\build_rf\generalizacion\muestra`.

Requisitos que hubo que resolver sobre la marcha y que conviene tener a mano:

- **Tesseract necesita `spa.traineddata`.** No venía instalado; solo había
  inglés. Se resolvió con `tessdata_best` y `TESSDATA_PREFIX`. Sin eso, la ruta
  de respaldo de Bashkar no funciona para español.
- **CHURRO necesita ~8,4 GB de RAM libres** y unos 34 min por página en CPU. No
  es ruta de producción; sirve para construir el estándar de oro.

## Conclusiones que cambiaron decisiones

1. **8 de 9 publicaciones traen la capa oculta de Paper Capture.** El
   acoplamiento al formato de la BNC es menos grave de lo que sugería leer el
   código. La excepción es *El Gráfico*, que es justo el contraste elegido en el
   plan de la beca.
2. **La fusión de palabras ya no es problema** en ningún corpus (máximo 0,26 %).
   El arreglo del umbral relativo de la sesión 65 funcionó para todos.
3. **La fragmentación sí varía muchísimo**: de 2,6 % a 35,6 %, sin que nada en
   el pipeline lo detecte ni lo reporte. Umbral empírico de abstención propuesto:
   por encima de ~10 % el documento no es utilizable sin revisión.
4. **El Día declara la capa oculta y solo tiene 2 de 16 páginas OCR-izadas.** La
   ruta debe decidirse por página y por presencia real de texto, nunca por la
   declaración de fuentes del documento.
5. **Tesseract supera a CHURRO como ruta de producción** (34 s frente a 2.068 s
   por página, con métricas estructurales equivalentes). CHURRO lee mejor los
   caracteres dañados, pero rompe las palabras partidas por guion de línea y hay
   indicio de que moderniza la ortografía —riesgo serio en un corpus histórico.

## Advertencia metodológica

Las métricas usadas (fusión, fragmento) dicen si los tokens están bien
**formados**, no si dicen lo que dice la página. Y resultaron **insuficientes**:
declararon empate entre Tesseract y CHURRO donde el análisis palabra por palabra
mostró diferencias sistemáticas.

Medir calidad real exige CER contra transcripción humana. Ese estándar de oro
**no existe todavía** en el proyecto: `ground_truth_piloto/` contiene imágenes,
candidatos de máquina y juicios de IA, no transcripción humana.
