# SESSION_LOG — Bashkar Station

Bitácora breve. El detalle sesión a sesión está en `CHANGELOG.md`, que es
extenso y explica el porqué de cada corrección.

---

## 9-sep-2026 — Sesión 67: llegada al MSI y tres fallos silenciosos

La migración funcionó como una prueba de instalación desde cero, y por eso
salieron cosas que en el Lenovo estaban tapadas por configuración manual sin
documentar.

- **Entorno montado**: clon en `C:\dev\bashkar_station` (traído de GitHub),
  venv con Python 3.12.10, Tesseract 5.4.0 con español, diccionario Hunspell
  es_ES, `es_core_news_sm`.
- **Bug de producción**: matplotlib 3.11 eliminó `labels` de `boxplot` y el
  gráfico de confianza de OCR reventaba con el código intacto. Primer daño real
  de los rangos `>=`; de ahí `requirements.lock.txt`.
- **Bug silencioso**: la corrección ortográfica post-OCR estaba inerte porque
  `spylls` no trae diccionario español y nadie lo declaraba ni lo instalaba.
- **Bug de proceso**: el hook `pre-commit` corría con un intérprete sin
  dependencias y decía "tests en rojo" sin correr un solo test.
- **Conteo**: la primera corrida aquí dio 1.577 contra las 1.587 del Lenovo. No
  era una regresión: `spylls` ausente quitaba 11 tests de la recolección. Una
  cifra verde que probaba menos, que es justo lo que un verde no debería poder
  esconder.
- Paper: esqueleto convertido a MLA 9 y resumen a tres lenguas.

## 7-sep-2026 — Cierre para migración a PC MSI

Sesión de infraestructura, sin cambios funcionales.

- **Pruebas: 1.587 pasan, 27 saltadas, 0 fallan.** Corridas dos veces:
  **6 min 01 s** en el clon local de `C:` y **6 min 33 s** desde Drive. Sirvió
  para desmentir una suposición de esta misma sesión: se había dado por hecho
  que Drive multiplicaba el tiempo de las pruebas, y aquí cuesta un ~9%.
- Commiteado `PAPER_METODOLOGICO_ESQUELETO.md`, que llevaba días sin guardar con
  la revista objetivo ya decidida y sus normas verificadas.
- **Corregida la sección 8 de `CLAUDE.md`**, que decía "sesión 14, 499 tests"
  con el repo en la sesión 66 y 1.587 pruebas: 52 sesiones de desfase.
- Creados `docs/PROJECT_STATE.md`, `DECISIONS.md`, `NEXT_STEPS.md` y este archivo.
- Aclarado un falso positivo: el clon `C:\Users\Lenovo\Bashkar-Station` parecía
  tener 5 commits sin pushear, pero su referencia de `origin` estaba
  desactualizada — esos commits ya estaban en GitHub y la copia estaba 23
  commits **atrasada**. No había nada en riesgo.

## Sesión 66 — 3-sep-2026 — Colaboración, contrato A1, generalización, CHURRO

Cinco bugs reales, todos verificados contra datos reales y no fixtures.
Suite final: 1587 passed, 27 skipped. 18 commits.

1. Los parches de colaboración salían **sin una sola corrección de OCR** (0 →
   169), guardaban solo 200 caracteres del texto, y el hash de validación
   incluía claves privadas (hash distinto por máquina).
2. El fixture de migración reproducía una forma que **ningún proyecto tuvo**.
3. **Contrato A1**: nueve formas incompatibles de acuñar el id de artículo;
   NER con 184 entidades y TEI asignando 0. Medido sobre el corpus real:
   **21 de 138 artículos (15%) se perdían en silencio**.
4. **CHURRO reparado**: segfault sin traza por fijar `HF_HUB_OFFLINE` tarde.
   Misma causa que la sesión 63 arregló en otro módulo; reapareció porque la
   lógica está copiada en tres sitios.
5. **Primera prueba de generalización fuera de *Estampa***: 9 publicaciones de
   la BNC. 8 de 9 traen capa oculta; la fusión de palabras ya no es problema;
   la fragmentación varía 2,6%-35,6% sin que nada la detecte.

## Sesión 65
16 bugs reales con 1.500 tests en verde. Esquema real del `.bashkar`
documentado; datos de Proyecto_04 recuperados.

## Antes
Ver `CHANGELOG.md` y `git log --oneline`.
