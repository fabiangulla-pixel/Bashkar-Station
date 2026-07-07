"""
exportadores/exportar_alto.py — Exportación ALTO XML v4.

ALTO (Analyzed Layout and Text Object) es el estándar ISO 12148
para representar contenido de documentos escaneados con información
de layout y texto.

Compatibilidad: eScriptorium, Transkribus, DLibra, bibliotecas nacionales.

Especificación: https://www.loc.gov/standards/alto/
"""

from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

APP_VERSION = "11"
ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
ALTO_SCHEMA = (
    "http://www.loc.gov/standards/alto/ns-v4# "
    "https://www.loc.gov/standards/alto/v4/alto-4-3.xsd"
)

# Tipos de zona de Bashkar → tipos ALTO
_TIPO_ALTO = {
    "articulo":   "TextBlock",
    "titulo":     "TextBlock",
    "pie_foto":   "TextBlock",
    "indice":     "TextBlock",
    "colofon":    "TextBlock",
    "foto":       "Illustration",
    "publicidad": "Illustration",
    "cabecera":   "TextBlock",
    "numero_pag": "TextBlock",
}

# Etiquetas TAGREFS para distinguir tipos en el TextBlock
_TAGREF_ALTO = {
    "articulo":   "article",
    "titulo":     "heading",
    "pie_foto":   "caption",
    "indice":     "TOC",
    "colofon":    "colophon",
    "cabecera":   "header",
    "numero_pag": "pageNum",
    "foto":       "photo",
    "publicidad": "advertisement",
}


def exportar_pagina_alto(articulo_id: str,
                          zonas: list[dict],
                          ancho_imagen: int,
                          alto_imagen: int,
                          nombre_imagen: str,
                          ruta_salida: str) -> str:
    """
    Exporta una página anotada en formato ALTO XML v4.

    Args:
        articulo_id:   ID del artículo/página.
        zonas:         Lista de zonas con {tipo, x1, y1, x2, y2,
                       texto_ocr?, texto_manual?, confianza_ocr?}.
                       Coordenadas normalizadas 0.0-1.0.
        ancho_imagen:  Ancho en píxeles de la imagen original.
        alto_imagen:   Alto en píxeles de la imagen original.
        nombre_imagen: Nombre del archivo de imagen (solo el basename).
        ruta_salida:   Ruta donde guardar el XML.

    Returns:
        ruta_salida si se guardó correctamente.
    """
    # ── Raíz ──────────────────────────────────────────────────────────────────
    alto = Element("alto")
    alto.set("xmlns", ALTO_NS)
    alto.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    alto.set("xsi:schemaLocation", ALTO_SCHEMA)

    # ── Descripción ───────────────────────────────────────────────────────────
    desc = SubElement(alto, "Description")

    measure = SubElement(desc, "MeasurementUnit")
    measure.text = "pixel"

    source_info = SubElement(desc, "sourceImageInformation")
    fname_el = SubElement(source_info, "fileName")
    fname_el.text = nombre_imagen

    proc = SubElement(desc, "OCRProcessing")
    proc.set("ID", "OCR_BASHKAR")
    step = SubElement(proc, "ocrProcessingStep")
    soft = SubElement(step, "processingSoftware")
    SubElement(soft, "softwareName").text = "Bashkar Station"
    SubElement(soft, "softwareVersion").text = APP_VERSION

    # ── Tags (tipos de zona) ──────────────────────────────────────────────────
    tags = SubElement(alto, "Tags")
    tipos_usados = {z.get("tipo", "articulo") for z in zonas}
    for tipo in tipos_usados:
        if tipo in _TAGREF_ALTO:
            tag = SubElement(tags, "OtherTag")
            tag.set("ID", _TAGREF_ALTO[tipo])
            tag.set("LABEL", tipo)

    # ── Layout ────────────────────────────────────────────────────────────────
    layout = SubElement(alto, "Layout")
    page = SubElement(layout, "Page")
    page.set("ID", f"P_{articulo_id}")
    page.set("PHYSICAL_IMG_NR", "1")
    page.set("WIDTH", str(ancho_imagen))
    page.set("HEIGHT", str(alto_imagen))

    print_space = SubElement(page, "PrintSpace")
    print_space.set("HPOS", "0")
    print_space.set("VPOS", "0")
    print_space.set("WIDTH", str(ancho_imagen))
    print_space.set("HEIGHT", str(alto_imagen))

    # ── Bloques de contenido ──────────────────────────────────────────────────
    for i, zona in enumerate(zonas):
        tipo = zona.get("tipo", "articulo")
        tipo_alto = _TIPO_ALTO.get(tipo, "TextBlock")

        # Desnormalizar coordenadas (0.0-1.0 → píxeles)
        x1 = int(zona.get("x1", 0) * ancho_imagen)
        y1 = int(zona.get("y1", 0) * alto_imagen)
        x2 = int(zona.get("x2", 1) * ancho_imagen)
        y2 = int(zona.get("y2", 1) * alto_imagen)
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)

        texto = zona.get("texto_manual") or zona.get("texto_ocr") or ""
        confianza = zona.get("confianza_ocr", 0.75)
        tagref = _TAGREF_ALTO.get(tipo, tipo)

        if tipo_alto == "Illustration":
            bloque = SubElement(print_space, "Illustration")
            bloque.set("ID", f"IL_{i+1}")
            bloque.set("HPOS", str(x1))
            bloque.set("VPOS", str(y1))
            bloque.set("WIDTH", str(w))
            bloque.set("HEIGHT", str(h))
            bloque.set("TYPE", tipo)
        else:
            bloque = SubElement(print_space, "TextBlock")
            bloque.set("ID", f"TB_{i+1}")
            bloque.set("HPOS", str(x1))
            bloque.set("VPOS", str(y1))
            bloque.set("WIDTH", str(w))
            bloque.set("HEIGHT", str(h))
            bloque.set("TAGREFS", tagref)

            if texto:
                # Dividir el texto en líneas para mejor representación
                lineas = [l for l in texto.split("\n") if l.strip()]
                if not lineas:
                    lineas = [texto]

                linea_h = max(1, h // max(len(lineas), 1))
                for j, linea_txt in enumerate(lineas):
                    y_linea = y1 + j * linea_h
                    linea_el = SubElement(bloque, "TextLine")
                    linea_el.set("ID", f"TL_{i+1}_{j+1}")
                    linea_el.set("HPOS", str(x1))
                    linea_el.set("VPOS", str(y_linea))
                    linea_el.set("WIDTH", str(w))
                    linea_el.set("HEIGHT", str(linea_h))

                    string_el = SubElement(linea_el, "String")
                    string_el.set("ID", f"S_{i+1}_{j+1}")
                    string_el.set("HPOS", str(x1))
                    string_el.set("VPOS", str(y_linea))
                    string_el.set("WIDTH", str(w))
                    string_el.set("HEIGHT", str(linea_h))
                    string_el.set("CONTENT", linea_txt)
                    string_el.set("WC", str(round(confianza, 2)))

    # ── Serializar con formato legible ────────────────────────────────────────
    xml_crudo = tostring(alto, encoding="unicode")
    xml_bonito = minidom.parseString(xml_crudo).toprettyxml(indent="  ")
    # toprettyxml agrega <?xml...?> redundante si ya está en el string
    lineas = xml_bonito.split("\n")
    if lineas[0].startswith("<?xml"):
        xml_bonito = "\n".join(lineas)  # conservar declaración XML

    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(xml_bonito)

    return ruta_salida


def exportar_corpus_alto(articulos: list[dict],
                          repo,
                          carpeta_salida: str,
                          callback=None) -> list[str]:
    """
    Exporta todos los artículos del corpus en ALTO XML.

    Args:
        articulos:      Lista de dicts de artículos (de repo.listar_articulos()).
        repo:           Instancia de Repositorio para obtener zonas.
        carpeta_salida: Carpeta donde guardar los XML.
        callback:       callable(i, total, art_id) — progreso.

    Returns:
        Lista de rutas a los XML generados.
    """
    carpeta = Path(carpeta_salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    total = len(articulos)

    for i, art in enumerate(articulos):
        art_id = art.get("id", f"art_{i:04d}")
        zonas = repo.obtener_zonas_anotacion(art_id)
        ruta_img = art.get("archivo_origen", "")

        # Obtener dimensiones de la imagen
        ancho, alto = 2480, 3508  # A4 a 300 DPI por defecto
        try:
            from PIL import Image
            with Image.open(ruta_img) as img:
                ancho, alto = img.size
        except Exception:
            pass

        nombre_img = Path(ruta_img).name if ruta_img else f"{art_id}.png"
        ruta_xml = str(carpeta / f"{art_id}.xml")

        try:
            exportar_pagina_alto(
                articulo_id=art_id,
                zonas=zonas,
                ancho_imagen=ancho,
                alto_imagen=alto,
                nombre_imagen=nombre_img,
                ruta_salida=ruta_xml,
            )
            rutas.append(ruta_xml)
        except Exception:
            pass

        if callback:
            callback(i + 1, total, art_id)

    return rutas
