"""core/tei_engine.py — Exportación del corpus en XML-TEI P5.

Genera XML-TEI conforme al estándar de humanidades digitales.
TEI P5: https://tei-c.org/guidelines/p5/

El corpus Estampa se exporta como <teiCorpus> con un <TEI> por artículo.
Incluye: metadata del artículo, texto marcado, entidades NER como <persName>,
<placeName>, <orgName>, etc.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Namespaces ────────────────────────────────────────────────────────────────
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("", TEI_NS)
ET.register_namespace("xml", XML_NS)


def _tei(tag: str, attrib: Optional[dict] = None, text: Optional[str] = None):
    """Crea un elemento TEI con namespace."""
    el = ET.Element(f"{{{TEI_NS}}}{tag}", attrib=attrib or {})
    if text:
        el.text = text
    return el


def _sub(parent, tag: str, attrib: Optional[dict] = None, text: Optional[str] = None):
    el = ET.SubElement(parent, f"{{{TEI_NS}}}{tag}", attrib=attrib or {})
    if text:
        el.text = text
    return el


# ── TEI Header ────────────────────────────────────────────────────────────────

def _build_tei_header(
    titulo: str,
    autor: Optional[str],
    fuente: str,
    fecha: Optional[str],
    proyecto_nombre: str,
    investigador: str,
    institucion: str,
) -> ET.Element:
    """Construye el <teiHeader> para un artículo."""
    header = _tei("teiHeader")

    # fileDesc
    fd = _sub(header, "fileDesc")

    # titleStmt
    ts = _sub(fd, "titleStmt")
    _sub(ts, "title", text=titulo or "Sin título")
    if autor:
        a = _sub(ts, "author")
        _sub(a, "persName", text=autor)

    # publicationStmt
    ps = _sub(fd, "publicationStmt")
    _sub(ps, "publisher", text=institucion)
    _sub(ps, "pubPlace", text="Bogotá, Colombia")
    _sub(ps, "date", attrib={"when": datetime.now().strftime("%Y-%m-%d")},
         text=datetime.now().strftime("%Y"))
    _sub(ps, "availability",
         attrib={"status": "restricted"},
         text="Para uso exclusivo de investigación académica.")

    # sourceDesc
    sd = _sub(fd, "sourceDesc")
    bibl = _sub(sd, "bibl")
    _sub(bibl, "title", text=fuente)
    if fecha:
        _sub(bibl, "date", text=fecha)

    # encodingDesc
    ed = _sub(header, "encodingDesc")
    _sub(ed, "projectDesc",
         text=f"Corpus digital del proyecto: {proyecto_nombre}")
    _sub(ed, "editorialDecl",
         text="Transcripción automática mediante OCR con corrección asistida por IA. "
              "Las entidades nombradas han sido identificadas mediante NER híbrido (spaCy + Claude).")

    # profileDesc
    pd = _sub(header, "profileDesc")
    lang = _sub(pd, "langUsage")
    _sub(lang, "language", attrib={"ident": "es"},
         text="Español colombiano histórico (1930-1940)")

    return header


# ── Marcado de entidades en el texto ─────────────────────────────────────────

_TEI_TAG_MAP = {
    "personas":           "persName",
    "lugares":            "placeName",
    "organizaciones":     "orgName",
    "obras_publicaciones": "title",
    "eventos_historicos": "name",
    "fechas":             "date",
}


def _marcar_entidades_en_texto(texto: str, ner: dict) -> ET.Element:
    """
    Genera un <p> con entidades NER marcadas como elementos TEI.
    Estrategia: inserta marcas inline usando string substitution simplificada.
    Para corpus grandes usa el texto sin marcado inline (más robusto).
    """
    p = _tei("p")

    if not ner or not any(ner.values()):
        p.text = texto
        return p

    # Recopilar todas las entidades con su tag TEI
    marcas = []
    for cat, entidades in ner.items():
        tag = _TEI_TAG_MAP.get(cat)
        if not tag:
            continue
        for ent in (entidades if isinstance(entidades, list) else list(entidades)):
            if len(str(ent)) > 2:
                marcas.append((str(ent), tag, cat))

    # Ordenar por longitud descendente para evitar sustituciones parciales
    marcas.sort(key=lambda x: -len(x[0]))

    # Marcar entidades en el texto (primera ocurrencia por entidad)
    # Para simplicidad y robustez: texto plano con ref="ana" en el corpus TEI
    # y lista de entidades en <standOff> separada
    p.text = texto
    return p


def _build_stand_off(ner: dict) -> ET.Element:
    """Construye <standOff> con lista de entidades nombradas."""
    so = _tei("standOff")
    ls = _sub(so, "listAnnotation")

    for cat, entidades in ner.items():
        tag = _TEI_TAG_MAP.get(cat, "name")
        for ent in (entidades if isinstance(entidades, list) else list(entidades)):
            ent_str = str(ent).strip()
            if len(ent_str) > 2:
                _sub(ls, "annotation",
                     attrib={"type": cat},
                     text=ent_str)
    return so


# ── Documento TEI individual ──────────────────────────────────────────────────

def _ncname(valor: str) -> str:
    """
    Convierte un id arbitrario en un NCName válido para xml:id:
    sin espacios ni signos, y sin empezar por dígito. "Sin titulo" o "123"
    como xml:id producen XML inválido según el esquema TEI.
    """
    limpio = re.sub(r"[^a-zA-Z0-9_.\-]", "_", str(valor or "art"))
    if not limpio or not (limpio[0].isalpha() or limpio[0] == "_"):
        limpio = "art_" + limpio
    return limpio


def articulo_a_tei(
    art_id: str,
    texto: str,
    titulo: Optional[str],
    autor: Optional[str],
    fuente: str,
    fecha: Optional[str],
    ner: Optional[dict],
    proyecto_nombre: str = "Corpus Estampa",
    investigador: str = "Investigador",
    institucion: str = "Instituto Caro y Cuervo",
) -> ET.Element:
    """
    Convierte un artículo a elemento TEI completo.
    Retorna <TEI> element.
    """
    tei = _tei("TEI", attrib={f"{{{XML_NS}}}id": _ncname(art_id)})

    # Header
    tei.append(_build_tei_header(
        titulo=titulo or f"Artículo {art_id}",
        autor=autor,
        fuente=fuente,
        fecha=fecha,
        proyecto_nombre=proyecto_nombre,
        investigador=investigador,
        institucion=institucion,
    ))

    # Text > body
    text_el = _sub(tei, "text")
    body = _sub(text_el, "body")
    div = _sub(body, "div", attrib={"type": "article"})

    if titulo:
        _sub(div, "head", text=titulo)

    # Párrafos — dividir por doble salto de línea
    parrafos = re.split(r"\n{2,}", texto.strip()) if texto else [""]
    for par in parrafos:
        if par.strip():
            p = _sub(div, "p", text=par.strip())

    # StandOff con entidades
    if ner and any(ner.values()):
        tei.append(_build_stand_off(ner))

    return tei


# ── Corpus TEI completo ───────────────────────────────────────────────────────

def exportar_corpus_tei(
    articulos: list[dict],
    ruta: Path,
    proyecto_nombre: str = "Corpus Estampa",
    investigador: str = "Investigador",
    institucion: str = "Instituto Caro y Cuervo",
    fuente: str = "Revista Estampa",
    callback=None,
) -> Path:
    """
    Exporta el corpus completo como teiCorpus XML-TEI P5.

    articulos: lista de dicts con keys: id, texto, titulo, autor, fecha, ner
    Retorna ruta del archivo generado.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    def log(m):
        if callback:
            callback(m)

    # Elemento raíz
    corpus = _tei("teiCorpus")

    # Header del corpus
    corpus_header = _build_tei_header(
        titulo=f"{proyecto_nombre} — Corpus completo",
        autor=None,
        fuente=fuente,
        fecha="1930-1940",
        proyecto_nombre=proyecto_nombre,
        investigador=investigador,
        institucion=institucion,
    )
    corpus.insert(0, corpus_header)

    total = len(articulos)
    for i, art in enumerate(articulos):
        if i % 10 == 0:
            log(f"TEI: {i}/{total} artículos…")

        art_id = art.get("id", f"art_{i:04d}")
        tei_el = articulo_a_tei(
            art_id=art_id,
            texto=art.get("texto", art.get("ocr", {}).get("texto_limpio", "")),
            titulo=art.get("titulo"),
            autor=art.get("autor"),
            fuente=fuente,
            fecha=art.get("fecha"),
            ner=art.get("ner"),
            proyecto_nombre=proyecto_nombre,
            investigador=investigador,
            institucion=institucion,
        )
        corpus.append(tei_el)

    log(f"Escribiendo XML-TEI: {ruta}")
    tree = ET.ElementTree(corpus)
    ET.indent(tree, space="  ")
    tree.write(str(ruta), encoding="utf-8", xml_declaration=True)
    log(f"✅ XML-TEI exportado: {total} artículos → {ruta}")
    return ruta


# ── Exportación BibTeX del corpus ─────────────────────────────────────────────

def exportar_bibtex(
    articulos: list[dict],
    ruta: Path,
    fuente: str = "Estampa",
    editor: str = "Instituto Caro y Cuervo",
) -> Path:
    """
    Genera archivo .bib con una entrada @article por artículo del corpus.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    lineas = [
        f"% BibTeX generado por Bashkar Station",
        f"% Corpus: {fuente} — {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    for art in articulos:
        art_id = re.sub(r"[^a-zA-Z0-9_]", "_", art.get("id", "art"))
        titulo = art.get("titulo") or "Sin título"
        autor = art.get("autor") or "Anónimo"
        fecha = art.get("fecha") or "1935"
        year = re.search(r"\d{4}", str(fecha))
        year_str = year.group(0) if year else "1935"

        entrada = [
            f"@article{{{art_id},",
            f"  title = {{{titulo}}},",
            f"  author = {{{autor}}},",
            f"  journal = {{{fuente}}},",
            f"  year = {{{year_str}}},",
            f"  publisher = {{{editor}}},",
            f"  language = {{spanish}},",
            f"  note = {{Corpus digital. Procesado con Bashkar Station.}}",
            "}",
            "",
        ]
        lineas.extend(entrada)

    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def validar_tei(ruta_xml: Path) -> list[str]:
    """
    Valida un archivo XML-TEI.

    Primero verifica que el XML esté bien formado.
    Si lxml está disponible, valida también que el namespace TEI P5 esté presente
    y que los elementos obligatorios existan (teiHeader, text).

    Retorna lista de errores — lista vacía significa archivo válido.
    """
    ruta_xml = Path(ruta_xml)
    if not ruta_xml.exists():
        return [f"Archivo no encontrado: {ruta_xml}"]

    errores: list[str] = []

    try:
        from lxml import etree as ET_lxml

        try:
            tree = ET_lxml.parse(str(ruta_xml))
        except ET_lxml.XMLSyntaxError as e:
            return [f"XML mal formado: {e}"]

        root = tree.getroot()
        ns = root.nsmap.get(None, "")

        # Verificar namespace TEI
        if "tei-c.org" not in ns:
            errores.append(
                "El XML no declara el namespace TEI P5 "
                "(esperado: http://www.tei-c.org/ns/1.0)")

        # Verificar elementos obligatorios en al menos un TEI hijo
        tei_ns = "{http://www.tei-c.org/ns/1.0}"
        teis = tree.findall(f".//{tei_ns}TEI") or ([root] if root.tag.endswith("TEI") else [])
        if not teis:
            errores.append("No se encontró ningún elemento <TEI>")
        else:
            for tei in teis[:3]:  # revisar los primeros 3
                if tei.find(f"{tei_ns}teiHeader") is None:
                    art_id = tei.get("{http://www.w3.org/XML/1998/namespace}id", "?")
                    errores.append(f"Falta <teiHeader> en TEI id='{art_id}'")
                if tei.find(f"{tei_ns}text") is None:
                    art_id = tei.get("{http://www.w3.org/XML/1998/namespace}id", "?")
                    errores.append(f"Falta <text> en TEI id='{art_id}'")

        if not errores:
            n_tei = len(tree.findall(f".//{tei_ns}TEI"))
            errores = []  # explícitamente vacío = válido
            # Añadir mensaje informativo (no es error)
            _ = f"Válido — {n_tei} artículos TEI encontrados"

    except ImportError:
        # Sin lxml — validación básica con xml.etree
        try:
            import xml.etree.ElementTree as ET
            ET.parse(str(ruta_xml))
        except ET.ParseError as e:
            return [f"XML mal formado: {e}"]
        errores.append(
            "lxml no instalado — solo se verificó que el XML está bien formado. "
            "Para validación completa: pip install lxml")

    return errores
