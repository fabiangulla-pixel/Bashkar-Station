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
    """Carga un .bashkar y retorna su dict."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {ruta}")
    return json.loads(ruta.read_text(encoding="utf-8"))


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
        textos = []
        for art in p.get("articulos", {}).values():
            textos.append(art.get("texto_limpio") or art.get("texto_ocr") or "")
        texto = " ".join(textos).lower()
        tokens = re.findall(r"[a-záéíóúüñ]{3,}", texto)
        return Counter(tokens)

    vocabs = [_vocab(p) for p in proyectos]
    sets = [set(v.keys()) for v in vocabs]

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

def comparar_topicos(proyectos: list[dict], nombres: list[str]) -> dict:
    """Compara etiquetas de tópicos entre proyectos."""
    result = {}
    for nom, p in zip(nombres, proyectos):
        top = p.get("topicos") or {}
        etiquetas = top.get("etiquetas_llm") or {}
        result[nom] = list(etiquetas.values()) if isinstance(etiquetas, dict) else []

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
        n_arts = len(p.get("articulos", {}))
        metadatos.append({
            "nombre": nom,
            "articulos": n_arts,
            "fecha_creacion": p.get("fecha_creacion", ""),
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
