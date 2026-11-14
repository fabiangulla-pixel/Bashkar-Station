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
from core.proveniencia import con_proveniencia

# ── Namespaces ────────────────────────────────────────────────────────────────
TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("", TEI_NS)
ET.register_namespace("xml", XML_NS)


def _tei(tag: str, attrib: dict | None = None, text: str | None = None):
    """Crea un elemento TEI con namespace."""
    el = ET.Element(f"{{{TEI_NS}}}{tag}", attrib=attrib or {})
    if text:
        el.text = text
    return el


def _sub(parent, tag: str, attrib: dict | None = None, text: str | None = None):
    el = ET.SubElement(parent, f"{{{TEI_NS}}}{tag}", attrib=attrib or {})
    if text:
        el.text = text
    return el


# ── TEI Header ────────────────────────────────────────────────────────────────

def _meta_compatible(metadatos: dict | None, proyecto_nombre: str = "",
                     investigador: str = "", institucion: str = "",
                     fuente: str = "") -> dict:
    """Metadatos de la exportación; acepta los parámetros sueltos de antes.

    Hasta el 14-nov-2026 los valores por defecto eran «Corpus Estampa»,
    «Instituto Caro y Cuervo» y «Revista Estampa»: todo TEI decía eso, fuera
    cual fuera el proyecto. Ahora lo no declarado queda vacío.
    """
    meta = dict(metadatos or {})
    meta.setdefault("proyecto", proyecto_nombre or "Corpus")
    meta.setdefault("publicacion", fuente)
    responsable = investigador if investigador not in ("", "Investigador") else ""
    meta.setdefault("responsable", responsable or institucion)
    for clave, defecto in (("periodo", ""), ("lugar", ""), ("disponibilidad", ""),
                           ("creditos", []), ("idioma", "Español"),
                           ("herramientas", {})):
        meta.setdefault(clave, defecto)
    return meta


def _build_tei_header(titulo: str, autor: str | None, meta: dict,
                      fecha_fuente: str | None = None) -> ET.Element:
    """Construye el <teiHeader> con los metadatos reales del proyecto."""
    from core.metadatos_exportacion import declaracion_editorial
    from core.proveniencia import version_app

    header = _tei("teiHeader")
    fd = _sub(header, "fileDesc")

    ts = _sub(fd, "titleStmt")
    _sub(ts, "title", text=titulo or "Sin título")
    if autor:
        a = _sub(ts, "author")
        _sub(a, "persName", text=autor)
    for c in meta.get("creditos") or []:
        rs = _sub(ts, "respStmt")
        _sub(rs, "resp", text=str(c.get("rol") or "crédito"))
        _sub(rs, "name", text=str(c["nombre"]))

    ps = _sub(fd, "publicationStmt")
    if meta.get("responsable"):
        _sub(ps, "publisher", text=meta["responsable"])
    else:
        _sub(ps, "p", text=f"Exportado con Bashkar Station {version_app()}.")
    if meta.get("lugar"):
        _sub(ps, "pubPlace", text=meta["lugar"])
    _sub(ps, "date", attrib={"when": datetime.now().strftime("%Y-%m-%d")},
         text=datetime.now().strftime("%Y"))
    if meta.get("disponibilidad"):
        av = _sub(ps, "availability")
        _sub(av, "p", text=meta["disponibilidad"])

    sd = _sub(fd, "sourceDesc")
    bibl = _sub(sd, "bibl")
    _sub(bibl, "title", text=meta.get("publicacion") or "desconocido")
    fecha = fecha_fuente or meta.get("periodo")
    if fecha:
        _sub(bibl, "date", text=fecha)

    ed = _sub(header, "encodingDesc")
    pdesc = _sub(ed, "projectDesc")
    _sub(pdesc, "p", text=f"Corpus digital del proyecto: {meta.get('proyecto') or 'Corpus'}")
    edecl = _sub(ed, "editorialDecl")
    _sub(edecl, "p", text=declaracion_editorial(meta.get("herramientas") or {}))

    pd = _sub(header, "profileDesc")
    lang = _sub(pd, "langUsage")
    _sub(lang, "language", attrib={"ident": "es"}, text=meta.get("idioma") or "Español")

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
    titulo: str | None,
    autor: str | None,
    fuente: str,
    fecha: str | None,
    ner: dict | None,
    proyecto_nombre: str = "",
    investigador: str = "",
    institucion: str = "",
    metadatos: dict | None = None,
) -> ET.Element:
    """
    Convierte un artículo a elemento TEI completo.
    Retorna <TEI> element.
    """
    tei = _tei("TEI", attrib={f"{{{XML_NS}}}id": _ncname(art_id)})
    meta = _meta_compatible(metadatos, proyecto_nombre, investigador, institucion, fuente)
    tei.append(_build_tei_header(titulo or f"Artículo {art_id}", autor, meta,
                                 fecha_fuente=fecha))

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

@con_proveniencia("TEI P5", "ruta", "articulos")
def exportar_corpus_tei(
    articulos: list[dict],
    ruta: Path,
    proyecto_nombre: str = "",
    investigador: str = "",
    institucion: str = "",
    fuente: str = "",
    callback=None,
    metadatos: dict | None = None,
) -> Path:
    """
    Exporta el corpus completo como teiCorpus XML-TEI P5.

    articulos: lista de dicts con keys: id, texto, titulo, autor, fecha, ner
    metadatos: los de core.metadatos_exportacion.metadatos_proyecto(); sin
        ellos se usan los parámetros sueltos y lo no declarado queda vacío.
    Retorna ruta del archivo generado.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    meta = _meta_compatible(metadatos, proyecto_nombre, investigador, institucion, fuente)

    def log(m):
        if callback:
            callback(m)

    corpus = _tei("teiCorpus")
    corpus.insert(0, _build_tei_header(f"{meta['proyecto']} — Corpus completo",
                                       None, meta))

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
            fuente=meta.get("publicacion", ""),
            fecha=art.get("fecha"),
            ner=art.get("ner"),
            metadatos=meta,
        )
        corpus.append(tei_el)

    log(f"Escribiendo XML-TEI: {ruta}")
    tree = ET.ElementTree(corpus)
    ET.indent(tree, space="  ")
    tree.write(str(ruta), encoding="utf-8", xml_declaration=True)
    log(f"✅ XML-TEI exportado: {total} artículos → {ruta}")
    return ruta


# ── Exportación BibTeX del corpus ─────────────────────────────────────────────

@con_proveniencia("BibTeX", "ruta", "articulos")
def exportar_bibtex(
    articulos: list[dict],
    ruta: Path,
    fuente: str = "",
    editor: str = "",
    periodo: str = "",
) -> Path:
    """
    Genera archivo .bib con una entrada @article por artículo del corpus.

    El año sale de la fecha del artículo o, si no la tiene, del ``periodo``
    del proyecto; si ninguno lo trae, la entrada va sin año. Hasta el
    14-nov-2026 se escribía «1935» y «Instituto Caro y Cuervo» como editor
    cuando no se sabía.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    lineas = [
        "% BibTeX generado por Bashkar Station",
        f"% Corpus: {fuente or 'sin nombre'} — {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]
    anio_periodo = re.search(r"\d{4}", str(periodo or ""))

    for art in articulos:
        art_id = re.sub(r"[^a-zA-Z0-9_]", "_", art.get("id", "art"))
        titulo = art.get("titulo") or "Sin título"
        autor = art.get("autor") or "Anónimo"
        year = re.search(r"\d{4}", str(art.get("fecha") or "")) or anio_periodo

        entrada = [f"@article{{{art_id},",
                   f"  title = {{{titulo}}},",
                   f"  author = {{{autor}}},"]
        if fuente:
            entrada.append(f"  journal = {{{fuente}}},")
        if year:
            entrada.append(f"  year = {{{year.group(0)}}},")
        if editor:
            entrada.append(f"  publisher = {{{editor}}},")
        entrada += ["  language = {spanish},",
                    "  note = {Corpus digital. Procesado con Bashkar Station.}",
                    "}", ""]
        lineas.extend(entrada)

    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def contar_entidades_en_tei(ruta_xml: Path) -> int:
    """Entidades anotadas en el TEI (``annotation`` y nombres marcados)."""
    import xml.etree.ElementTree as ET_std
    try:
        root = ET_std.parse(str(ruta_xml)).getroot()
    except Exception:
        return 0
    etiquetas = {f"{{{TEI_NS}}}{t}" for t in
                 ("annotation", "persName", "placeName", "orgName")}
    # persName del autor en el teiHeader no es una entidad NER: se cuentan
    # solo las de standOff y las del cuerpo del texto.
    n = 0
    for zona in list(root.iter(f"{{{TEI_NS}}}standOff")) + \
            list(root.iter(f"{{{TEI_NS}}}body")):
        n += sum(1 for el in zona.iter() if el.tag in etiquetas)
    return n


def validar_tei(ruta_xml: Path, entidades_esperadas: int | None = None) -> list[str]:
    """
    Valida un archivo XML-TEI.

    Con ``entidades_esperadas`` > 0 (las que tiene el proyecto), también es
    error que el TEI no traiga ninguna: así pasó inadvertido que el exportador
    nunca encontraba las entidades de los artículos.

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

    if entidades_esperadas and contar_entidades_en_tei(ruta_xml) == 0:
        errores.append(
            f"El proyecto tiene {entidades_esperadas} entidades, pero el TEI no "
            "contiene ninguna: revisa que los artículos y el índice NER usen los "
            "mismos identificadores.")
    return errores
