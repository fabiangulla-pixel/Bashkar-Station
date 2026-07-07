"""core/exploradores.py — Exploradores de publicación (Fases 3 y 4).

Módulos de publicación SEPARADOS del editor Tkinter. Leen las entidades
canónicas y el grafo del proyecto y generan artefactos web/RDF autocontenidos.

  - geocodificar_lugares(): asigna lat/lon a entidades tipo=lugar usando el
    gazetteer local datos/coordenadas_colombia.json (sin red).
  - mapa_lugares_html(): mapa interactivo. Usa folium si está instalado; si no,
    degrada con gracia a un HTML estático con Leaflet vía CDN.
  - timeline_numeros_html(): línea de tiempo de los números del corpus, cada
    punto enlazado a su transcripción/artículos.
  - exportar_rdf(): export OPCIONAL del grafo a RDF/Turtle con rdflib. Si rdflib
    no está instalado, escribe Turtle a mano (degradación con gracia) — nunca
    es dependencia obligatoria.

Ninguna dependencia pesada es obligatoria: todo degrada con gracia.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Optional


_GAZETTEER = Path(__file__).parent.parent / "datos" / "coordenadas_colombia.json"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


# ── Geocodificación local ─────────────────────────────────────────────────────

def _cargar_gazetteer(ruta: Optional[str] = None) -> dict:
    ruta = Path(ruta) if ruta else _GAZETTEER
    if not ruta.exists():
        return {}
    try:
        data = json.load(open(ruta, encoding="utf-8"))
    except Exception:
        return {}
    # aplanar las secciones (ciudades / paises_vecinos / regiones_historicas)
    plano: dict[str, dict] = {}
    for clave, val in data.items():
        if clave.startswith("_") or not isinstance(val, dict):
            continue
        for nombre, info in val.items():
            if isinstance(info, dict) and "lat" in info:
                plano[_norm(nombre)] = info
    return plano


def geocodificar_lugares(entidades_canonicas: list[dict],
                         ruta_gazetteer: Optional[str] = None) -> list[dict]:
    """
    Filtra entidades tipo=lugar y les asigna lat/lon desde el gazetteer local.
    Solo devuelve las que se pudieron georreferenciar.
    """
    gz = _cargar_gazetteer(ruta_gazetteer)
    out = []
    for e in entidades_canonicas:
        if e.get("tipo") != "lugar":
            continue
        clave = _norm(e.get("nombre", ""))
        info = gz.get(clave)
        if not info:
            continue
        out.append({
            "id": e.get("id", ""),
            "nombre": e.get("nombre", ""),
            "lat": info["lat"],
            "lon": info["lon"],
            "n_menciones": e.get("n_menciones", 0),
            "departamento": info.get("departamento", ""),
        })
    return out


# ── Mapa de lugares ───────────────────────────────────────────────────────────

def mapa_lugares_html(lugares: list[dict], ruta_salida: str | Path,
                      titulo: str = "Lugares mencionados") -> dict:
    """
    Genera un mapa HTML de los lugares georreferenciados. Tamaño del marcador
    proporcional a las menciones. Retorna {ok, motor, ruta, n}.
    """
    ruta_salida = str(ruta_salida)
    if not lugares:
        return {"ok": False, "motor": "—", "ruta": ruta_salida, "n": 0,
                "mensaje": "Sin lugares georreferenciados"}

    # centro: promedio de coordenadas
    clat = sum(l["lat"] for l in lugares) / len(lugares)
    clon = sum(l["lon"] for l in lugares) / len(lugares)

    try:
        import folium
        m = folium.Map(location=[clat, clon], zoom_start=4, tiles="CartoDB positron")
        for l in lugares:
            radio = 4 + min(l["n_menciones"], 20)
            folium.CircleMarker(
                location=[l["lat"], l["lon"]],
                radius=radio,
                popup=f"{l['nombre']} ({l['n_menciones']} menciones)",
                tooltip=l["nombre"],
                color="#C1121F", fill=True, fill_opacity=0.6,
            ).add_to(m)
        m.save(ruta_salida)
        return {"ok": True, "motor": "folium", "ruta": ruta_salida, "n": len(lugares)}
    except ImportError:
        _mapa_leaflet_cdn(lugares, ruta_salida, titulo, clat, clon)
        return {"ok": True, "motor": "leaflet_cdn", "ruta": ruta_salida,
                "n": len(lugares)}


def _mapa_leaflet_cdn(lugares, ruta, titulo, clat, clon):
    """Fallback sin folium: HTML estático con Leaflet vía CDN."""
    marcadores = ",\n".join(
        f'{{lat:{l["lat"]},lon:{l["lon"]},nombre:{json.dumps(l["nombre"])},'
        f'n:{l["n_menciones"]}}}' for l in lugares)
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>{titulo}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{{height:100%;margin:0}}</style></head><body>
<div id="map"></div><script>
var map=L.map('map').setView([{clat},{clon}],4);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png',
 {{attribution:'&copy; OpenStreetMap, &copy; CARTO'}}).addTo(map);
var pts=[{marcadores}];
pts.forEach(function(p){{
 L.circleMarker([p.lat,p.lon],{{radius:4+Math.min(p.n,20),color:'#C1121F',
  fillOpacity:0.6}}).addTo(map).bindPopup(p.nombre+' ('+p.n+' menciones)');
}});
</script></body></html>"""
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)


# ── Timeline de números ───────────────────────────────────────────────────────

def timeline_numeros_html(numeros: list[dict], ruta_salida: str | Path,
                          titulo: str = "Números del corpus") -> dict:
    """
    Genera una línea de tiempo HTML de los números del corpus. Cada número:
    {numero, fecha, n_articulos, ruta_transcripcion?}. Cada punto enlaza a la
    transcripción/artículos. HTML autocontenido (sin dependencias).
    Retorna {ok, ruta, n}.
    """
    ruta_salida = str(ruta_salida)
    if not numeros:
        return {"ok": False, "ruta": ruta_salida, "n": 0,
                "mensaje": "Sin números"}

    items = sorted(numeros, key=lambda x: str(x.get("fecha") or x.get("numero", "")))
    filas = []
    for it in items:
        num = it.get("numero", "—")
        fecha = it.get("fecha") or ""
        narts = it.get("n_articulos", 0)
        href = it.get("ruta_transcripcion") or ""
        enlace = (f'<a href="{href}">ver transcripción</a>' if href
                  else '<span class="sin">sin transcripción</span>')
        filas.append(
            f'<li><span class="fecha">{fecha}</span>'
            f'<span class="num">{num}</span>'
            f'<span class="arts">{narts} artículos</span>{enlace}</li>')

    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>{titulo}</title><style>
body{{font-family:Segoe UI,sans-serif;background:#0D1117;color:#E6EDF3;margin:0;padding:24px}}
h1{{font-weight:600}}
ul.tl{{list-style:none;padding:0;border-left:3px solid #C1121F;margin-left:12px}}
ul.tl li{{margin:0 0 14px 18px;position:relative;padding:8px 12px;background:#161B22;border-radius:8px}}
ul.tl li::before{{content:'';position:absolute;left:-27px;top:14px;width:12px;height:12px;
 background:#C1121F;border-radius:50%}}
.fecha{{display:inline-block;min-width:110px;color:#7EE787;font-weight:600}}
.num{{font-weight:600;margin-right:12px}}
.arts{{color:#8B949E;margin-right:12px}}
a{{color:#58A6FF}} .sin{{color:#6E7681;font-style:italic}}
</style></head><body>
<h1>{titulo} — {len(items)} números</h1>
<ul class="tl">
{chr(10).join(filas)}
</ul></body></html>"""
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(html)
    return {"ok": True, "ruta": ruta_salida, "n": len(items)}


# ── Export RDF (opcional) ─────────────────────────────────────────────────────

_NS = "https://bashkar.station/entidad/"
_PRED = "https://bashkar.station/predicado/"


def exportar_rdf(grafo: dict, ruta_salida: str | Path) -> dict:
    """
    Exporta el grafo {nodos, aristas} a RDF/Turtle. Usa rdflib si está; si no,
    escribe Turtle a mano. rdflib NO es dependencia obligatoria.
    Retorna {ok, motor, ruta, n_tripletas}.
    """
    ruta_salida = str(ruta_salida)
    nodos = grafo.get("nodos", [])
    aristas = grafo.get("aristas", [])

    try:
        from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS
        g = Graph()
        ENT = Namespace(_NS)
        PRED = Namespace(_PRED)
        g.bind("ent", ENT); g.bind("pred", PRED)
        for n in nodos:
            uri = URIRef(_NS + _norm(n["id"]).replace(" ", "_"))
            g.add((uri, RDFS.label, Literal(n.get("nombre", n["id"]))))
            g.add((uri, RDF.type, Literal(n.get("tipo", "entidad"))))
            if n.get("wikidata_id"):
                g.add((uri, ENT.wikidata, Literal(n["wikidata_id"])))
        for a in aristas:
            s = URIRef(_NS + _norm(a["origen_id"]).replace(" ", "_"))
            o = URIRef(_NS + _norm(a["destino_id"]).replace(" ", "_"))
            p = URIRef(_PRED + _norm(a["predicado"]).replace(" ", "_"))
            g.add((s, p, o))
        g.serialize(destination=ruta_salida, format="turtle")
        return {"ok": True, "motor": "rdflib", "ruta": ruta_salida,
                "n_tripletas": len(g)}
    except ImportError:
        n_trip = _turtle_manual(nodos, aristas, ruta_salida)
        return {"ok": True, "motor": "turtle_manual", "ruta": ruta_salida,
                "n_tripletas": n_trip}


def _turtle_manual(nodos, aristas, ruta) -> int:
    """Escribe Turtle válido sin rdflib (degradación con gracia)."""
    def uri(base, x):
        return f"<{base}{_norm(x).replace(' ', '_')}>"
    def esc(s):
        return str(s).replace("\\", "\\\\").replace('"', '\\"')

    lineas = [f'@prefix ent: <{_NS}> .', f'@prefix pred: <{_PRED}> .',
              '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .', '']
    n = 0
    for nodo in nodos:
        u = uri(_NS, nodo["id"])
        lineas.append(f'{u} rdfs:label "{esc(nodo.get("nombre", nodo["id"]))}" ;')
        lineas.append(f'    a "{esc(nodo.get("tipo", "entidad"))}" .')
        n += 2
        if nodo.get("wikidata_id"):
            lineas.append(f'{u} ent:wikidata "{esc(nodo["wikidata_id"])}" .')
            n += 1
    for a in aristas:
        s = uri(_NS, a["origen_id"])
        o = uri(_NS, a["destino_id"])
        p = uri(_PRED, a["predicado"])
        lineas.append(f'{s} {p} {o} .')
        n += 1
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    return n
