"""core/comparador.py — Comparador multi-proyecto para Bashkar Station.

Compara dos o más proyectos .bashkar entre sí:
  - Entidades comunes vs exclusivas
  - Vocabulario compartido (solapamiento léxico)
  - Tópicos en común
  - Líneas temporales comparadas
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Callable

# ── Carga de proyectos ────────────────────────────────────────────────────────

def cargar_proyecto(ruta: str | Path) -> dict:
    """Carga un .bashkar y retorna su dict.

    Anota la ruta de origen en ``_ruta``: el JSON de un proyecto real es solo
    metadatos, y el contenido pesado (textos, artículos) vive en la carpeta
    hermana ``<stem>/`` y en el SQLite ``<stem>.db``. Sin la ruta, las
    comparaciones que necesitan texto no tienen dónde buscarlo y devuelven 0.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {ruta}")
    p = json.loads(ruta.read_text(encoding="utf-8"))
    if isinstance(p, dict):
        p["_ruta"] = str(ruta)
    return p


def _carpeta_datos(p: dict) -> Path | None:
    """Carpeta hermana <stem>/ donde viven los CSV y corpus_txt.json."""
    ruta = p.get("_ruta")
    if not ruta:
        return None
    carpeta = Path(ruta).with_suffix("")
    return carpeta if carpeta.is_dir() else None


def _textos_proyecto(p: dict) -> list[str]:
    """Textos planos de un proyecto, buscándolos donde de verdad están.

    Orden real de los datos (verificado sobre los proyectos de
    ~/Documents/BashkarStation/proyectos):
      1. ``<stem>/corpus_txt.json`` — lo que escribe project_manager cuando
         ``resultados.corpus_txt_guardado`` es True.
      2. tabla ``ocr`` del SQLite hermano (texto_limpio).
      3. raíz ``articulos`` — solo lo produce pipeline_maestro; los .bashkar
         que abre la GUI nunca la tienen.
    """
    carpeta = _carpeta_datos(p)
    if carpeta:
        corpus = carpeta / "corpus_txt.json"
        if corpus.exists():
            try:
                datos = json.loads(corpus.read_text(encoding="utf-8"))
                if isinstance(datos, list):
                    return [str(t) for t in datos if t]
            except Exception:
                pass

    ruta_db = p.get("db") or ""
    if ruta_db and p.get("_ruta"):
        db = Path(ruta_db)
        if not db.is_absolute():
            db = Path(p["_ruta"]).parent / db
        if db.exists():
            try:
                import sqlite3
                con = sqlite3.connect(str(db))
                filas = con.execute(
                    "SELECT COALESCE(NULLIF(texto_limpio,''), texto_crudo) FROM ocr"
                ).fetchall()
                con.close()
                textos = [str(f[0]) for f in filas if f and f[0]]
                if textos:
                    return textos
            except Exception:
                pass

    arts = p.get("articulos")
    if isinstance(arts, dict):
        arts = list(arts.values())
    if isinstance(arts, list):
        return [str(a.get("texto_limpio") or a.get("texto_ocr") or a.get("texto") or "")
                for a in arts if isinstance(a, dict)]
    return []


def _n_articulos(p: dict) -> int:
    """Número de artículos de un proyecto real (CSV hermano o SQLite)."""
    carpeta = _carpeta_datos(p)
    if carpeta and (carpeta / "articulos.csv").exists():
        try:
            import csv
            # Con csv.reader, no contando líneas: los títulos con saltos de
            # línea embebidos inflaban el total (142 en vez de 138 reales).
            with open(carpeta / "articulos.csv", encoding="utf-8", newline="") as f:
                return max(sum(1 for _ in csv.reader(f)) - 1, 0)
        except Exception:
            pass
    ruta_db = p.get("db") or ""
    if ruta_db and p.get("_ruta"):
        db = Path(ruta_db)
        if not db.is_absolute():
            db = Path(p["_ruta"]).parent / db
        if db.exists():
            try:
                import sqlite3
                con = sqlite3.connect(str(db))
                n = con.execute("SELECT COUNT(*) FROM articulos").fetchone()[0]
                con.close()
                if n:
                    return int(n)
            except Exception:
                pass
    arts = p.get("articulos")
    return len(arts) if isinstance(arts, (dict, list)) else 0


def _indice_ner(p: dict) -> dict:
    """Ubica el índice NER de un proyecto .bashkar.

    En proyectos reales (post-migración a SQLite) el índice NER vive
    anidado en resultados.indice_ner_global, no en la raíz del dict —
    la raíz nunca tiene "indice_ner_global" ni "ner_global". Sin este
    fallback, comparar_entidades() siempre veía índices vacíos y
    reportaba 0 entidades comunes para cualquier par de proyectos reales.
    """
    idx = p.get("indice_ner_global") or p.get("ner_global")
    if idx:
        return idx
    return (p.get("resultados", {}) or {}).get("indice_ner_global", {}) or {}


# ── Comparación de entidades NER ──────────────────────────────────────────────

def comparar_entidades(proyectos: list[dict]) -> dict:
    """
    Compara índices NER de N proyectos.
    Retorna:
      - comunes: entidades en todos los proyectos
      - exclusivas: {nombre_proyecto: {cat: [entidades]}}
      - frecuencia_global: Counter de entidades
    """
    indices = [_indice_ner(p) for p in proyectos]

    if not indices:
        return {"comunes": {}, "exclusivas": [], "frecuencia_global": {}}

    # Conjuntos de entidades por categoría por proyecto
    sets_por_cat: dict[str, list[set]] = {}
    for idx in indices:
        for cat, ents in idx.items():
            if not isinstance(ents, dict):
                continue
            sets_por_cat.setdefault(cat, [])
            sets_por_cat[cat].append(set(ents.keys()))

    comunes: dict[str, list[str]] = {}
    for cat, sets in sets_por_cat.items():
        if len(sets) < 2:
            continue
        interseccion = sets[0]
        for s in sets[1:]:
            interseccion = interseccion & s
        if interseccion:
            comunes[cat] = sorted(interseccion)

    # Frecuencia global de entidades
    freq: Counter = Counter()
    for idx in indices:
        for cat, ents in idx.items():
            if not isinstance(ents, dict):
                continue
            for ent, arts in ents.items():
                freq[ent] += len(arts) if isinstance(arts, (list, set)) else 1

    return {
        "comunes": comunes,
        "total_comunes": sum(len(v) for v in comunes.values()),
        "frecuencia_global": dict(freq.most_common(100)),
    }


# ── Comparación de vocabulario ────────────────────────────────────────────────

def comparar_vocabulario(proyectos: list[dict], nombres: list[str]) -> dict:
    """
    Compara el vocabulario (frecuencias de palabras) entre proyectos.
    nombres: etiquetas para cada proyecto.
    Retorna vocabulario compartido, exclusivo, y similitud Jaccard.
    """
    import re

    def _vocab(p: dict) -> Counter:
        texto = " ".join(_textos_proyecto(p)).lower()
        tokens = re.findall(r"[a-záéíóúüñ]{3,}", texto)
        return Counter(tokens)

    vocabs = [_vocab(p) for p in proyectos]
    sets = [set(v.keys()) for v in vocabs]
    if not sets:
        return {"compartido_total": 0, "exclusivos": {}, "jaccard": 0.0,
                "vocabulario_por_proyecto": {}}

    compartido = sets[0]
    for s in sets[1:]:
        compartido = compartido & s

    exclusivos = {}
    for i, (nom, s) in enumerate(zip(nombres, sets)):
        otros = set()
        for j, s2 in enumerate(sets):
            if j != i:
                otros |= s2
        exclusivos[nom] = sorted(s - otros)[:50]

    union_total = set()
    for s in sets:
        union_total |= s
    jaccard = len(compartido) / len(union_total) if union_total else 0.0

    return {
        "compartido_total": len(compartido),
        "exclusivos": exclusivos,
        "jaccard": round(jaccard, 4),
        "vocabulario_por_proyecto": {n: len(s) for n, s in zip(nombres, sets)},
    }


# ── Comparación de tópicos ────────────────────────────────────────────────────

def _etiquetas_topicos(p: dict) -> list[str]:
    """Etiquetas (o palabras clave) de los tópicos de un proyecto real."""
    top = p.get("topicos") or {}
    if isinstance(top, dict):
        etiquetas = top.get("etiquetas_llm") or {}
        if isinstance(etiquetas, dict) and etiquetas:
            return list(etiquetas.values())
        topicos = top.get("topicos") or {}
        if isinstance(topicos, dict) and topicos:
            return [str(v.get("nombre") or ", ".join(v.get("palabras", [])[:5]))
                    for v in topicos.values() if isinstance(v, dict)]

    temas = (p.get("resultados", {}) or {}).get("temas_lda") or []
    if isinstance(temas, list) and temas:
        out = []
        for t in temas:
            if isinstance(t, dict):
                out.append(str(t.get("nombre") or t.get("etiqueta")
                               or ", ".join(map(str, t.get("palabras", [])[:5]))))
            else:
                out.append(str(t))
        return out

    carpeta = _carpeta_datos(p)
    if carpeta and (carpeta / "temas.csv").exists():
        try:
            import csv
            with open(carpeta / "temas.csv", encoding="utf-8") as f:
                return [str(r.get("palabras_clave") or r.get("tema") or "")
                        for r in csv.DictReader(f)]
        except Exception:
            pass
    return []

def comparar_topicos(proyectos: list[dict], nombres: list[str]) -> dict:
    """Compara etiquetas de tópicos entre proyectos.

    Los tópicos de un proyecto real no están en la raíz: la GUI los guarda como
    ``<stem>/temas.csv`` (columnas tema, palabras_clave) y, cuando hay LDA en
    memoria, en ``resultados.temas_lda``. La raíz ``topicos`` solo la escribe
    pipeline_maestro. Se revisan las tres, en ese orden de especificidad.
    """
    result = {}
    for nom, p in zip(nombres, proyectos):
        result[nom] = _etiquetas_topicos(p)

    # Tópicos comunes (por coincidencia de etiqueta)
    if len(result) >= 2:
        sets = [set(v) for v in result.values()]
        comunes = sets[0]
        for s in sets[1:]:
            comunes = comunes & s
    else:
        comunes = set()

    return {
        "topicos_por_proyecto": result,
        "topicos_comunes": sorted(comunes),
    }


# ── Reporte comparativo ───────────────────────────────────────────────────────

def generar_reporte_comparativo(
    rutas: list[str | Path],
    nombres: list[str],
    callback: Callable[[str], None] | None = None,
) -> dict:
    """
    Genera un reporte comparativo completo entre N proyectos.
    Retorna dict con: entidades, vocabulario, topicos, metadatos.
    """
    def _log(msg: str):
        if callback:
            callback(msg)

    _log("Cargando proyectos...")
    proyectos = []
    for ruta in rutas:
        try:
            proyectos.append(cargar_proyecto(ruta))
            _log(f"  ✓ {ruta}")
        except Exception as e:
            _log(f"  ✗ {ruta}: {e}")
            proyectos.append({})

    _log("Comparando entidades NER...")
    entidades = comparar_entidades(proyectos)

    _log("Comparando vocabulario...")
    vocabulario = comparar_vocabulario(proyectos, nombres)

    _log("Comparando tópicos...")
    topicos = comparar_topicos(proyectos, nombres)

    # Metadatos básicos de cada proyecto
    metadatos = []
    for nom, p in zip(nombres, proyectos):
        # El .bashkar real no tiene ni "articulos" ni "fecha_creacion" en la
        # raíz: los artículos están en <stem>/articulos.csv o en el SQLite, y
        # la fecha se llama "creado". Antes esta tabla salía siempre "0 / vacío".
        metadatos.append({
            "nombre": nom,
            "articulos": _n_articulos(p),
            "fecha_creacion": p.get("fecha_creacion") or p.get("creado", ""),
        })

    _log("Reporte comparativo listo.")
    return {
        "nombres": nombres,
        "metadatos": metadatos,
        "entidades": entidades,
        "vocabulario": vocabulario,
        "topicos": topicos,
    }


def exportar_reporte_html(reporte: dict, ruta: Path) -> Path:
    """Genera un HTML con el reporte comparativo."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    nombres = reporte.get("nombres", [])
    metas = reporte.get("metadatos", [])
    ents = reporte.get("entidades", {})
    vocab = reporte.get("vocabulario", {})
    tops = reporte.get("topicos", {})

    # Tabla metadatos
    meta_rows = "".join(
        f"<tr><td>{m['nombre']}</td><td>{m['articulos']}</td><td>{m.get('fecha_creacion','')}</td></tr>"
        for m in metas
    )

    # Entidades comunes
    ent_comunes_rows = ""
    for cat, lista in ents.get("comunes", {}).items():
        for e in lista[:20]:
            ent_comunes_rows += f"<tr><td>{cat}</td><td>{e}</td></tr>"

    # Vocabulario exclusivo
    excl_html = ""
    for nom, palabras in vocab.get("exclusivos", {}).items():
        excl_html += f"<h4>{nom}</h4><p style='font-size:12px'>{', '.join(palabras[:30])}</p>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Comparativa de proyectos — Bashkar Station</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f0f23;color:#e0e0e0;padding:20px}}
h1{{color:#a78bfa;text-align:center}}
h2{{color:#7dd3fc;border-bottom:1px solid #334155;padding-bottom:4px}}
h3{{color:#86efac}}
h4{{color:#fbbf24}}
table{{width:100%;border-collapse:collapse;margin-bottom:20px}}
th{{background:#1e293b;color:#7dd3fc;padding:8px;text-align:left}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
.stat{{display:inline-block;background:#1e293b;border-radius:8px;padding:12px 20px;margin:8px}}
.stat .val{{font-size:2em;color:#a78bfa;font-weight:bold}}
.stat .lbl{{font-size:12px;color:#94a3b8}}
</style>
</head>
<body>
<h1>Comparativa de proyectos</h1>
<p style="text-align:center;color:#94a3b8">Proyectos: {', '.join(nombres)}</p>

<h2>Proyectos comparados</h2>
<table><tr><th>Proyecto</th><th>Artículos</th><th>Fecha</th></tr>{meta_rows}</table>

<h2>Estadísticas</h2>
<div>
  <div class="stat"><div class="val">{ents.get('total_comunes',0)}</div><div class="lbl">Entidades comunes</div></div>
  <div class="stat"><div class="val">{vocab.get('compartido_total',0)}</div><div class="lbl">Vocab. compartido</div></div>
  <div class="stat"><div class="val">{vocab.get('jaccard',0):.2%}</div><div class="lbl">Similitud Jaccard</div></div>
  <div class="stat"><div class="val">{len(tops.get('topicos_comunes',[]))}</div><div class="lbl">Tópicos comunes</div></div>
</div>

<h2>Entidades comunes</h2>
<table><tr><th>Categoría</th><th>Entidad</th></tr>{ent_comunes_rows or '<tr><td colspan="2">Ninguna</td></tr>'}</table>

<h2>Vocabulario exclusivo por proyecto</h2>
{excl_html or '<p>Sin datos</p>'}

<h2>Tópicos comunes</h2>
<p>{', '.join(tops.get('topicos_comunes', [])) or 'Ninguno'}</p>
</body>
</html>"""

    ruta.write_text(html, encoding="utf-8")
    return ruta
