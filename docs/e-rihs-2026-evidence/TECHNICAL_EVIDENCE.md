# Bashkar Station — Technical Evidence for E-RIHS 2026 / ANAMNESIS Request

Prepared: 2026-10-14
Repository: https://github.com/fabiangulla-pixel/Bashkar-Station
Commit evaluated: `7e6cdbdf3b3b28e6258b89a5b6148ea5eb180af2` (2026-10-13), branch `main`
Working copy: `C:\dev\bashkar_station`
Application version string (`gui_comun.APP_VERSION`): `13.1`
(Note: `README.md`'s badge still reads "v12.0" — it was not updated after the
version bump to 13.1; this is a documentation lag, not a functional issue.)

## 0. Development and institutional context — correction

Bashkar Station was developed by its author with the support of a **Beca de
Estímulo** (stimulus grant) from Colombia's **Ministerio de las Culturas,
las Artes y los Saberes**. **Instituto Caro y Cuervo** (Bogotá) served as
the grant's *mentoring institution*. The software is **not** institutional
property of Instituto Caro y Cuervo, and the author — an alumnus of the
institute — holds **no current contractual research affiliation** with it.
This document and its PDF annex state this explicitly in §1, correcting an
earlier draft of this package that implied the software was "developed at"
the institute.

## 1. Scope and honesty constraints

This package documents **what actually ran**, on this date, on the author's
machine. It does not claim:
- an integration with ANAMNESIS or a formal CNRS collaboration (there is none);
- any institutional affiliation beyond what §0 states.

**Reference corpus used.** This package uses **one real page** of *Estampa*
(Bogotá, March 1939), digitized by the Biblioteca Nacional de Colombia
(BNC) — `ground_truth_piloto/rev_estampa_mar_1939/imagenes/p0005.jpg` in the
author's own working copy. *Estampa* was a Colombian weekly illustrated
magazine covering politics, culture, society and current affairs with
extensive photographic and graphic content, 1939 — the kind of richly
illustrated, mixed-layout historical periodical Bashkar Station is built to
process. The page is reproduced here under the author's own existing
research-use authorization for this corpus; this package does not imply any
further redistribution right beyond this specific evidence exercise. The
real OCR transcription used is one produced **in this session**, by running
Tesseract (Spanish) on the image live — it is shown unedited, including its
genuine digitization noise, as honest evidence of real input quality rather
than a cleaned-up sample. (An earlier draft of this package used an
entirely synthetic, invented page instead of real material, out of an
excess of caution about reuse rights before the author confirmed
authorization; that synthetic version has been replaced throughout by this
real one.)

## 2. Environment inspected

- Python: 3.12.10 (MSC v.1943 64-bit), venv `C:\dev\venv-bashkar`.
- Key dependencies import successfully in this venv: `tkinter`, `pytesseract`,
  `spacy`, `fitz`/PyMuPDF (deprecated alias warning only, non-blocking),
  `sqlite3`.
- Two first-class frontends share the same `core/` business logic and the
  same `Estado` class (`core/estado.py`), per `docs/ARQUITECTURA.md`:
  - **Desktop** — `app.py`, Tkinter, ~21k lines, uses local GPU if present.
  - **Web** — `servidor_web.py`, Python stdlib `http.server` backend +
    vanilla JS frontend in `web/`, no build step, no framework.
  - A third interface, `cli.py`, runs the pipeline with no UI at all.
- **Desktop GUI could not be screenshotted in this exercise.** The process
  launches and runs (confirmed via `tasklist`, real memory growth, clean
  stdout), but this execution environment has no interactive Windows desktop
  session reachable for screen capture — screenshots of the primary monitor
  only ever showed the automation/editor session itself, never a Tk window.
  This is an environment limitation of this specific evidence-gathering
  session, not a defect of Bashkar Station; the desktop app is the
  researcher's daily driver (see project memory, sessions 1-74).
- **Web frontend was fully exercised instead** — launched as the real
  process (`python servidor_web.py`, local mode, port 8421), driven through
  its actual HTTP API (`requests`), and screenshotted with a real headless
  Chromium browser (Playwright, installed for this exercise) hitting
  `http://localhost:8421/`. Every screenshot in this package is a real
  render of the running application, not a mockup.

## 3. Pipeline executed end-to-end (real run, this session)

Commands and real server responses are in `full_demo_real.log` (included in
this package). Summary of the real, observed run, on the real *Estampa*
page:

| Step | Endpoint (real server) | Result observed |
|---|---|---|
| Create project | `POST /api/proyecto/nuevo` | `ERIHS_Demo_Estampa_Real.bashkar` created on disk |
| Upload PDF | `POST /api/subir` | 433,824 bytes received, `estampa_1939_p05.pdf` (real scan + real Tesseract text layer) |
| Convert (embedded-text extraction, PyMuPDF) | `POST /api/conv/iniciar` | job `ok`, 1/1 page, `ocr: ready` |
| Normalize | `POST /api/norm/iniciar` | job `ok`, 1 file, 9 words changed, 9 hyphenations rejoined (real OCR-noise correction) |
| Segment into articles | `POST /api/seg/iniciar` | job `ok`, **1 article** detected (full-page masthead/editorial), 1202 words |
| NER (hybrid spaCy + rules) | `POST /api/ner/iniciar` | job `ok`, **39 entities**: real historical names (Agustín Nieto Caballero, Alfonso López, Ricardo Lleras Codazzi), real places (Bogotá, Cali, París, Santander), real institutions (Gimnasio Moderno, Universidad Libre) |
| Lexical analysis | `POST /api/anal/iniciar` | job `ok`, 830 words, 526-term vocabulary |
| Export TEI P5 | `POST /api/exportar {"formato":"tei"}` | `corpus_tei.xml` written, well-formed XML with `<teiHeader>`, `<standOff>` entity layer |
| Export entities CSV | `POST /api/exportar {"formato":"csv_ner"}` | `entidades.csv`, UTF-8 BOM, Excel-safe |
| Export BibTeX | `POST /api/exportar {"formato":"bibtex"}` | `corpus.bib` |

All three exported files are included under `exportes_estampa_real/` in
this package as raw evidence, generated in this run, not reused from a
prior session.

**Known limitations surfaced by this exact run (reported honestly, not
fixed):**
- Real 1939 digitization/OCR noise is visible throughout the extracted
  entities and text (e.g. "Gimnasi", "COLOMBI", "Tomás Mueda Vargas" for
  "Rueda Vargas") — this is exactly the condition Bashkar's normalization
  and human-review stages exist to address, shown here unedited rather than
  cleaned up.
- Both the TEI and BibTeX exporters hardcode `publisher = "Instituto Caro y
  Cuervo"` / `journal = "Estampa"` as default fields regardless of the
  active project's own name. Given the institutional correction in §0, this
  pre-existing default is now also a **factual-accuracy issue**, not just a
  cosmetic one — worth fixing in a future session. Left unmodified for this
  exercise per the no-source-changes constraint; visible as-is in
  `exportes_estampa_real/corpus_tei.xml` and `corpus.bib`.

## 4. Automated tests

Command run in this session:
```
cd C:\dev\bashkar_station
C:\dev\venv-bashkar\Scripts\python.exe -m pytest tests/ -q
```
**Real result, this session: 1967 passed, 29 skipped, 0 failed, in 245.25s**
(see `pytest_result.txt` for the full tail). This is the project's real,
pre-existing automated test suite (GUI, OCR, NER, TEI, API-parity tests
included); no tests were written or altered to produce this evidence
package.

## 5. Screenshot inventory

| File | Panel / module | How it was reached | What it shows |
|---|---|---|---|
| `01_main_interface.png` | Configuración (web) | `GET /` then navigate to "Configuración" after project load | App name + version banner ("Bashkar Station web v1.0"), active project "ERIHS_Demo_Estampa_Real", pipeline stage badges all green (`ocr/norm/seg/anal: ready`), real counts (1 número, 1 artículo, 39 entidades) |
| `02_document_processing.png` | Normalizar | Click "Normalizar" in sidebar | Real Tesseract OCR output of the real Estampa page, unedited, with real digitization noise visible |
| `03_normalization_or_segmentation.png` | Segmentar | Click "Segmentar" | The 1 real article detected on this page, with title/author/section/word-count columns populated from the actual run |
| `04_analysis_or_entities.png` | Analizar | Click "Analizar" | Real lexical frequency bars (526-term vocabulary) computed over the real page |
| `05_results_or_exports.png` | Resultados | Click "Resultados" | Real export buttons (XML-TEI P5, BibTeX, CSV articles, CSV entities) — three were exercised for this package |

Capture date: 2026-10-14. Capture method: Playwright (headless Chromium)
against the live local server, full-page screenshot, 1600×1000 viewport.

## 6. Existing vs. future (SCAN2DATA)

**Existing today, verified in this session:**
- Multi-format ingestion (image OCR via Tesseract/Kraken in the desktop app;
  embedded-text PDF extraction in both frontends, verified here on a real
  BNC-digitized page).
- Per-page processing provenance (`core/proveniencia.py`, `@con_proveniencia`
  decorators on exporters) — not exercised visually in this package but
  present in the architecture (`docs/ARQUITECTURA.md`).
- Article-level segmentation with type/section/author detection.
- Hybrid NER (spaCy + rule-based gazetteer; RoBERTa available in the desktop
  app, disabled by default for a documented threading-safety reason) —
  verified here to correctly recover real historical names and institutions
  from a 1939 source.
- Structured export to TEI P5, BibTeX, CSV, with entities in `<standOff>`.
- A documented, test-enforced parity contract between the desktop and the
  API/web surfaces (`core/operaciones.py` + `tests/test_paridad.py`).

**Relevant to E-RIHS / ANAMNESIS, not yet built:**
- No connector to ANAMNESIS or any W7 (who/what/when/where/why/how/with-what)
  paradata schema exists in the codebase today. The closest existing
  structure is the provenance manifest (`.proveniencia.json`) written
  alongside exports, which records motor/version per page and could be
  mapped to a subset of W7 fields (what/how/with-what) as a documentation
  exercise — this mapping has not been attempted and is proposed as future
  work, not a current capability.
- No OAI-PMH or LOD endpoint for external harvesting; Wikidata entity linking
  exists one-way (outbound enrichment), not as a published dataset.
- No collaboration or data-sharing agreement with CNRS or ANAMNESIS exists;
  none is claimed.

## 7. Files in this package

```
docs/e-rihs-2026-evidence/
├── Bashkar_Station_E-RIHS_Technical_Evidence.pdf
├── TECHNICAL_EVIDENCE.md          (this file)
├── 01_main_interface.png
├── 02_document_processing.png
├── 03_normalization_or_segmentation.png
├── 04_analysis_or_entities.png
├── 05_results_or_exports.png
├── estampa_1939_real_page_input.pdf   (real BNC scan + real Tesseract text layer, this session)
├── exportes_estampa_real/
│   ├── corpus_tei.xml
│   ├── entidades.csv
│   └── corpus.bib
├── pytest_result.txt              (tail of the real test run, this session)
└── full_demo_real.log             (full HTTP API transcript of the real pipeline run)
```

No changes were committed or pushed to GitHub as part of producing this
package, per the task's instruction.
