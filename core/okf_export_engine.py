"""core/okf_export_engine.py — Exportador de bundle OKF (Open Knowledge Format).

Repaqueta lo que YA está calculado en el SQLite del proyecto (artículos, OCR,
entidades canónicas, relaciones) como un bundle OKF: un directorio de archivos
.md con frontmatter YAML, sin depender de SQLite/API propia para ser leído por
otro agente. Spec de referencia (jun-2026):
github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Mapeo de dominio:
  - Documento  → un `numero` (edición) del corpus, agrupa sus artículos.
  - Articulo   → una fila de `articulos` con texto OCR no vacío.
  - Entidad    → una fila de `entidades_canonicas`, con sus apariciones
    (artículos donde se menciona) y relaciones salientes ya fundidas.

Cero llamadas a LLM/red: es repaquetado local puro, mismo espíritu $0 que
`exportadores/` (ALTO XML, TEI) y `core/exploradores.py` (RDF/GEXF). No toca
NER, el grafo de entidades ni ningún motor de análisis — solo lee lo que
`datos/repositorio.py` ya expone.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datos.repositorio import Repositorio

_MAX_RESUMEN = 220


def _slug(texto: str) -> str:
    """ASCII, minúsculas, separado por guiones. Determinista."""
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "sin-titulo"


def _articulo_slug(art: dict) -> str:
    # sufijo con el id real: dos artículos con el mismo título no colisionan.
    return f"{_slug(art.get('titulo'))}-{_slug(art.get('id'))}"


def _documento_slug(numero: str) -> str:
    return _slug(numero)


def _entidad_slug(canonica_id: str) -> str:
    # el id canónico ("tipo:slug-nombre") ya es único por construcción.
    return _slug(canonica_id)


def _yaml_str(valor) -> str:
    """Escapa un valor para YAML de una línea (comillas, backslashes, saltos)."""
    v = str(valor).replace("\\", "\\\\").replace('"', '\\"')
    v = " ".join(v.split())  # colapsa saltos de línea / espacios repetidos
    return f'"{v}"'


def _frontmatter(campos: dict) -> str:
    """Serializa a bloque YAML frontmatter. Omite valores vacíos salvo 'type'
    (obligatorio en la spec OKF; el resto son recomendados)."""
    lineas = ["---"]
    for clave, valor in campos.items():
        if clave != "type" and valor in (None, "", [], {}):
            continue
        if isinstance(valor, list):
            lineas.append(f"{clave}: [{', '.join(_yaml_str(v) for v in valor)}]")
        else:
            lineas.append(f"{clave}: {_yaml_str(valor)}")
    lineas.append("---")
    return "\n".join(lineas)


def _escribir_md(ruta: Path, campos: dict, cuerpo: str):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contenido = _frontmatter(campos) + "\n\n" + cuerpo.rstrip() + "\n"
    ruta.write_text(contenido, encoding="utf-8")


# ── Documentos (números / ediciones) ────────────────────────────────────────

def exportar_documentos_okf(articulos: list[dict], carpeta: Path) -> list[dict]:
    """Un concepto Documento por cada `numero` distinto. Recibe solo artículos
    ya filtrados (con contenido exportado) para no enlazar artículos rotos.
    Retorna [{numero, slug, n_articulos}]."""
    por_numero: dict[str, list[dict]] = {}
    for art in articulos:
        numero = (art.get("numero") or "").strip() or "sin-numero"
        por_numero.setdefault(numero, []).append(art)

    documentos = []
    for numero, arts in por_numero.items():
        slug = _documento_slug(numero)
        fecha = next((a.get("fecha_publicacion") for a in arts
                     if a.get("fecha_publicacion")), "")
        secciones = sorted({a["seccion"] for a in arts if a.get("seccion")})

        cuerpo = [f"# {numero}", "", f"**Artículos:** {len(arts)}"]
        if fecha:
            cuerpo.append(f"**Fecha:** {fecha}")
        if secciones:
            cuerpo.append(f"**Secciones:** {', '.join(secciones)}")
        cuerpo += ["", "## Artículos de este número"]
        for a in sorted(arts, key=lambda a: (a.get("pagina_inicio") or 0,
                                             a.get("titulo") or "")):
            enlace = f"- [{a.get('titulo') or 'Sin título'}](../articulos/{_articulo_slug(a)}.md)"
            if a.get("seccion"):
                enlace += f" — {a['seccion']}"
            cuerpo.append(enlace)

        _escribir_md(
            carpeta / "documentos" / f"{slug}.md",
            {"type": "Documento", "title": numero,
             "description": f"Número/edición del corpus — {len(arts)} artículo(s)",
             "tags": ["documento"], "timestamp": fecha},
            "\n".join(cuerpo))
        documentos.append({"numero": numero, "slug": slug, "n_articulos": len(arts)})
    return documentos


# ── Artículos ────────────────────────────────────────────────────────────────

def exportar_articulos_okf(articulos: list[dict], carpeta: Path,
                           textos: dict[str, str],
                           entidades_por_articulo: dict[str, list[dict]]
                           ) -> list[dict]:
    """Un concepto Artículo por cada fila con texto OCR no vacío (las que no
    tienen texto son "inválidas" para OKF — no hay contenido que empaquetar).
    `entidades_por_articulo`: {articulo_id: [entidad_canonica_dict, ...]}.
    Retorna [{id, slug, titulo, numero}] de los artículos SÍ exportados."""
    exportados = []
    for art in articulos:
        texto = (textos.get(art["id"]) or "").strip()
        if not texto:
            continue
        slug = _articulo_slug(art)
        titulo = art.get("titulo") or "Sin título"
        autor = art.get("autor") or "Anónimo"
        numero = art.get("numero") or ""
        resumen = " ".join(texto.split())[:_MAX_RESUMEN]

        cuerpo = [f"# {titulo}", "", f"**Autor:** {autor}"]
        if numero:
            cuerpo.append(f"**Número:** [{numero}](../documentos/{_documento_slug(numero)}.md)")
        if art.get("seccion"):
            cuerpo.append(f"**Sección:** {art['seccion']}")
        cuerpo += ["", "## Texto", "", texto]

        cans = entidades_por_articulo.get(art["id"], [])
        if cans:
            cuerpo += ["", "## Entidades mencionadas"]
            for c in sorted(cans, key=lambda c: c["nombre"]):
                cuerpo.append(
                    f"- [{c['nombre']} ({c['tipo']})](../entidades/{_entidad_slug(c['id'])}.md)")

        tags = ["articulo"]
        if numero:
            tags.append(f"numero:{numero}")
        if art.get("seccion"):
            tags.append(f"seccion:{art['seccion']}")

        _escribir_md(
            carpeta / "articulos" / f"{slug}.md",
            {"type": "Articulo", "title": titulo, "description": resumen,
             "resource": art.get("archivo_origen") or "", "tags": tags,
             "timestamp": art.get("fecha_publicacion") or ""},
            "\n".join(cuerpo))
        exportados.append({"id": art["id"], "slug": slug, "titulo": titulo,
                           "numero": numero})
    return exportados


# ── Entidades canónicas ───────────────────────────────────────────────────────

def exportar_entidades_okf(canonicas: list[dict], carpeta: Path,
                           apariciones_por_canonica: dict[str, list[str]],
                           articulos_por_id: dict[str, dict],
                           relaciones_por_origen: dict[str, list[dict]]
                           ) -> list[dict]:
    """Un concepto Entidad por cada fila de entidades_canonicas, con sus
    apariciones (enlaces a artículos) y relaciones salientes ya fundidas.
    Una entidad mencionada en 3 artículos = 1 archivo con 3 apariciones,
    nunca 3 archivos (la fusión ya ocurrió en fundir_menciones_en_canonicas)."""
    canonicas_por_id = {c["id"]: c for c in canonicas}
    exportadas = []
    for c in canonicas:
        slug = _entidad_slug(c["id"])
        cuerpo = [f"# {c['nombre']}", "", f"**Tipo:** {c['tipo']}",
                 f"**Menciones:** {c.get('n_menciones', 0)}"]
        if c.get("wikidata_id"):
            uri = c.get("wikidata_uri") or f"https://www.wikidata.org/wiki/{c['wikidata_id']}"
            cuerpo.append(f"**Wikidata:** [{c['wikidata_id']}]({uri})")

        arts_validos = [articulos_por_id[aid]
                        for aid in apariciones_por_canonica.get(c["id"], [])
                        if aid in articulos_por_id]
        if arts_validos:
            cuerpo += ["", "## Apariciones"]
            for a in sorted(arts_validos, key=lambda a: a["titulo"]):
                cuerpo.append(f"- [{a['titulo']}](../articulos/{a['slug']}.md)")

        rels = relaciones_por_origen.get(c["id"], [])
        rels_texto = [r for r in rels
                     if r.get("destino_id") or r["predicado"] != "mencionado_en"]
        if rels_texto:
            cuerpo += ["", "## Relaciones"]
            for r in rels_texto:
                if r.get("destino_id") and r["destino_id"] in canonicas_por_id:
                    dest = canonicas_por_id[r["destino_id"]]
                    cuerpo.append(
                        f"- **{r['predicado']}** → "
                        f"[{dest['nombre']}](../entidades/{_entidad_slug(dest['id'])}.md)")
                elif r.get("destino_pagina"):
                    cuerpo.append(f"- **{r['predicado']}** → {r['destino_pagina']}")

        _escribir_md(
            carpeta / "entidades" / f"{slug}.md",
            {"type": "Entidad", "title": c["nombre"],
             "description": f"{c['tipo']} — {c.get('n_menciones', 0)} mención(es)",
             "tags": ["entidad", f"tipo:{c['tipo']}"]},
            "\n".join(cuerpo))
        exportadas.append({"id": c["id"], "slug": slug, "nombre": c["nombre"],
                           "tipo": c["tipo"]})
    return exportadas


# ── Índice del bundle ──────────────────────────────────────────────────────────

def escribir_index_okf(carpeta: Path, nombre_proyecto: str,
                       documentos: list[dict], articulos: list[dict],
                       entidades: list[dict]) -> None:
    cuerpo = [f"# {nombre_proyecto}", "",
             f"Bundle OKF exportado de Bashkar Station — {len(documentos)} "
             f"documento(s), {len(articulos)} artículo(s), {len(entidades)} "
             f"entidad(es) canónica(s).",
             "", "## Documentos"]
    for d in sorted(documentos, key=lambda d: d["numero"]):
        cuerpo.append(f"- [{d['numero']}](documentos/{d['slug']}.md) — "
                      f"{d['n_articulos']} artículo(s)")
    cuerpo += ["", "## Artículos"]
    for a in sorted(articulos, key=lambda a: a["titulo"]):
        cuerpo.append(f"- [{a['titulo']}](articulos/{a['slug']}.md)")
    cuerpo += ["", "## Entidades"]
    for e in sorted(entidades, key=lambda e: e["nombre"]):
        cuerpo.append(f"- [{e['nombre']} ({e['tipo']})](entidades/{e['slug']}.md)")

    _escribir_md(
        carpeta / "index.md",
        {"type": "Bundle", "title": nombre_proyecto,
         "description": f"Exportación OKF de {nombre_proyecto} "
                        f"({len(articulos)} artículos, {len(entidades)} entidades)",
         "tags": ["bashkar-station", "okf"],
         "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "\n".join(cuerpo))


# ── Orquestador ────────────────────────────────────────────────────────────────

def exportar_proyecto_okf(repo: Repositorio, carpeta_salida: str | Path,
                          nombre_proyecto: str = "Corpus") -> dict:
    """
    Exporta el proyecto completo (documentos + artículos + entidades
    canónicas + relaciones) como un bundle OKF en `carpeta_salida`.

    No recalcula nada ni llama a red: repaqueta lo que ya está en el SQLite
    del proyecto (mismo principio que exportar_rdf/GEXF en core/exploradores.py).
    Retorna {ok, carpeta, n_documentos, n_articulos, n_entidades}.
    """
    carpeta = Path(carpeta_salida)
    carpeta.mkdir(parents=True, exist_ok=True)

    articulos = repo.listar_articulos()
    textos = {a["id"]: (repo.obtener_texto(a["id"]) or "") for a in articulos}

    canonicas = repo.listar_entidades_canonicas()
    canonicas_por_id = {c["id"]: c for c in canonicas}

    apariciones_por_canonica: dict[str, list[str]] = {}
    canonicas_por_articulo: dict[str, list[str]] = {}
    for par in repo.menciones_de_canonicas():
        apariciones_por_canonica.setdefault(par["canonica_id"], []).append(par["articulo_id"])
        canonicas_por_articulo.setdefault(par["articulo_id"], []).append(par["canonica_id"])

    entidades_por_articulo = {
        aid: [canonicas_por_id[cid] for cid in cids if cid in canonicas_por_id]
        for aid, cids in canonicas_por_articulo.items()
    }

    articulos_exportados = exportar_articulos_okf(
        articulos, carpeta, textos, entidades_por_articulo)
    articulos_por_id = {a["id"]: a for a in articulos_exportados}

    articulos_validos = [a for a in articulos if a["id"] in articulos_por_id]
    documentos_exportados = exportar_documentos_okf(articulos_validos, carpeta)

    relaciones_por_origen: dict[str, list[dict]] = {}
    for r in repo.listar_relaciones():
        relaciones_por_origen.setdefault(r["origen_id"], []).append(r)

    entidades_exportadas = exportar_entidades_okf(
        canonicas, carpeta, apariciones_por_canonica, articulos_por_id,
        relaciones_por_origen)

    escribir_index_okf(carpeta, nombre_proyecto, documentos_exportados,
                       articulos_exportados, entidades_exportadas)

    return {
        "ok": True, "carpeta": str(carpeta),
        "n_documentos": len(documentos_exportados),
        "n_articulos": len(articulos_exportados),
        "n_entidades": len(entidades_exportadas),
    }
