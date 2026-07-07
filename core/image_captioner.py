"""
core/image_captioner.py — Descripción automática de imágenes etiquetadas.

Para cada zona de tipo "foto" en una página etiquetada:
  1. Recorta la zona de la imagen original a color.
  2. La envía al proveedor de visión elegido (Claude/GPT-4o/Gemini/Ollama).
  3. Genera:
       - descripcion   : texto libre en español ("Mujer usando máquina de coser")
       - categorias    : lista de etiquetas temáticas controladas
       - texto_visible : texto que aparece dentro de la imagen (letreros, pies de foto)
  4. Guarda en SQLite tabla "descripciones_imagen".
  5. Indexa el embedding de la descripción en FAISS para búsqueda por similitud.

Uso:
    from core.image_captioner import describir_zona, describir_numero
    desc = describir_zona(img_path, zona, proveedor="claude", api_key="...")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

# ── Categorías temáticas controladas para Estampa 1930-1940 ──────────────────
# Vocabulario inspirado en iconografía de humanidades digitales e historia cultural

CATEGORIAS_TEMATICAS = [
    # Sujeto principal
    "mujer", "hombre", "niño", "niña", "grupo", "multitud", "retrato",
    # Espacio
    "interior", "exterior", "urbano", "rural", "hogar", "iglesia",
    "oficina", "fabrica", "calle", "plaza", "campo",
    # Actividad
    "trabajo", "celebracion", "reunion", "deporte", "arte", "religion",
    "politica", "guerra", "educacion", "comercio", "viaje",
    # Tecnología / modernidad
    "maquina", "automovil", "avion", "radio", "telefono", "imprenta",
    "fotografia", "cine", "electricidad",
    # Clase / estatus
    "elite", "clase_media", "popular", "indigena", "campesino",
    # Género / rol social
    "domestico", "profesional", "maternal", "moda", "deporte_femenino",
    # Registro visual
    "publicidad", "fotoreportaje", "retrato_formal", "instantanea",
    "ilustracion", "caricatura", "grabado",
]


# ── Prompt base para descripción de imágenes ─────────────────────────────────

PROMPT_DESCRIPCION = """Eres un investigador de historia cultural e iconografía analizando imágenes de la revista colombiana Estampa (1930-1940).

Analiza esta imagen y responde en JSON con exactamente estos campos:

{
  "descripcion": "Una oración descriptiva en español, concisa y factual. Ejemplo: 'Mujer usando máquina de coser en taller doméstico'. Máximo 20 palabras.",
  "categorias": ["lista", "de", "categorías"],
  "texto_visible": "Cualquier texto legible dentro de la imagen (letreros, títulos, pies de foto impresos). Vacío si no hay.",
  "contexto_historico": "Una oración sobre el contexto histórico o social que sugiere la imagen. Máximo 15 palabras."
}

Para "categorias" usa SOLO términos de esta lista:
{categorias}

Devuelve SOLO el JSON, sin texto adicional."""


# ── Función principal ─────────────────────────────────────────────────────────

def describir_zona(
    img_path: Path,
    zona,                          # Zona de zone_labeler (tiene x0,y0,x1,y1)
    proveedor: str = "claude",
    api_key: str = "",
    modelo: str = "",
    prompt_custom: str = "",
    callback: Callable | None = None,
) -> dict:
    """
    Describe una zona de imagen etiquetada como "foto".

    Args:
        img_path:     Imagen completa de la página (color preferible).
        zona:         Objeto Zona con coordenadas normalizadas.
        proveedor:    "claude" | "openai" | "gemini" | "ollama"
        api_key:      Clave API del proveedor.
        modelo:       Modelo específico. Si vacío, usa el default.
        prompt_custom: Prompt personalizado. Si vacío usa el default.
        callback:     callable(mensaje) para logging.

    Returns:
        dict con: descripcion, categorias, texto_visible, contexto_historico,
                  proveedor, modelo, zona_tipo, x0,y0,x1,y1
    """
    def log(m):
        if callback:
            callback(m)

    try:
        from PIL import Image
        img = Image.open(img_path).convert("RGB")
        W, H = img.size

        # Recortar zona con margen mínimo
        x0 = max(0, int(zona.x0 * W) - 4)
        y0 = max(0, int(zona.y0 * H) - 4)
        x1 = min(W, int(zona.x1 * W) + 4)
        y1 = min(H, int(zona.y1 * H) + 4)

        if x1 <= x0 or y1 <= y0:
            return _resultado_vacio(zona)

        recorte = img.crop((x0, y0, x1, y1))

        # Si el recorte es muy pequeño (< 50x50), no vale la pena
        if recorte.width < 50 or recorte.height < 50:
            return _resultado_vacio(zona)

    except Exception as e:
        log(f"⚠ Error al recortar imagen: {e}")
        return _resultado_vacio(zona)

    prompt = (prompt_custom.strip() or
              PROMPT_DESCRIPCION.replace("{categorias}",
                                         ", ".join(CATEGORIAS_TEMATICAS)))

    # Guardar recorte temporalmente
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    recorte.save(str(tmp_path), "JPEG", quality=85)

    try:
        raw = _llamar_vision(tmp_path, proveedor, api_key, modelo, prompt, log)
        resultado = _parsear_respuesta(raw)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    resultado.update({
        "proveedor": proveedor,
        "modelo":    modelo,
        "zona_tipo": zona.tipo,
        "x0": zona.x0, "y0": zona.y0, "x1": zona.x1, "y1": zona.y1,
    })
    return resultado


def describir_numero(
    out_dir: Path,
    numero: str,
    proveedor: str = "claude",
    api_key: str = "",
    modelo: str = "",
    db_path: Path | None = None,
    callback: Callable | None = None,
    solo_fotos: bool = True,
) -> list[dict]:
    """
    Describe todas las zonas de foto de un número completo.
    Guarda los resultados en SQLite y los retorna.

    Args:
        out_dir:    Carpeta raíz del proyecto.
        numero:     Nombre del número (ej. "estampa_001").
        proveedor:  Proveedor de visión IA.
        api_key:    API key del proveedor.
        modelo:     Modelo específico.
        db_path:    Ruta a la base de datos SQLite. None = no guardar en DB.
        callback:   callback(n_actual, n_total, pagina, descripcion).
        solo_fotos: Si True, solo procesa zonas de tipo "foto". Si False, todas.

    Returns:
        list[dict] con todas las descripciones generadas.
    """
    from core.zone_labeler import cargar_pagina, listar_paginas_etiquetadas

    img_dir = out_dir / "02_imagenes" / numero
    etiquetadas = listar_paginas_etiquetadas(out_dir, numero)

    resultados = []
    total = len(etiquetadas)

    for i, pagina in enumerate(etiquetadas, 1):
        pag_data = cargar_pagina(out_dir, numero, pagina)
        if not pag_data:
            continue

        zonas_img = [z for z in pag_data.zonas
                     if (z.tipo == "foto" if solo_fotos else True)]
        if not zonas_img:
            continue

        # Buscar imagen original a color
        img_path = _buscar_imagen(img_dir, pagina)
        if img_path is None:
            continue

        for j, zona in enumerate(zonas_img):
            desc = describir_zona(img_path, zona, proveedor=proveedor,
                                   api_key=api_key, modelo=modelo)
            desc["numero"]  = numero
            desc["pagina"]  = pagina
            desc["zona_idx"] = j
            resultados.append(desc)

            if callback:
                callback(i, total, pagina, desc.get("descripcion", ""))

    # Guardar en SQLite
    if db_path and resultados:
        _guardar_en_db(db_path, resultados)

    # Indexar embeddings para búsqueda por similitud
    _indexar_embeddings(out_dir, numero, resultados)

    return resultados


# ── Búsqueda por similitud de descripción ────────────────────────────────────

def buscar_imagenes_similares(
    consulta: str,
    out_dir: Path,
    numero: str,
    top_n: int = 5,
) -> list[dict]:
    """
    Busca imágenes cuya descripción sea semánticamente similar a la consulta.
    Usa el índice FAISS creado por describir_numero().

    Returns:
        list[dict] con: pagina, zona_idx, descripcion, distancia
    """
    indice_path = out_dir / "06_indices" / numero / "descripciones.faiss"
    meta_path   = out_dir / "06_indices" / numero / "descripciones_meta.json"

    if not indice_path.exists() or not meta_path.exists():
        return []

    try:
        import faiss
        import numpy as np

        from core.embeddings_local import get_embedding

        index = faiss.read_index(str(indice_path))
        meta  = json.loads(meta_path.read_text(encoding="utf-8"))

        vec = np.array([get_embedding(consulta)], dtype=np.float32)
        faiss.normalize_L2(vec)

        D, I = index.search(vec, min(top_n, index.ntotal))
        resultados = []
        for dist, idx in zip(D[0], I[0]):
            if idx < 0 or idx >= len(meta):
                continue
            m = dict(meta[idx])
            m["distancia"] = round(float(dist), 4)
            resultados.append(m)
        return resultados
    except Exception:
        return []


# ── SQLite ────────────────────────────────────────────────────────────────────

def _guardar_en_db(db_path: Path, resultados: list[dict]):
    try:
        import sqlite3
        from datetime import datetime
        con = sqlite3.connect(str(db_path))
        con.execute("""CREATE TABLE IF NOT EXISTS descripciones_imagen (
            numero           TEXT,
            pagina           TEXT,
            zona_idx         INTEGER,
            zona_tipo        TEXT,
            x0 REAL, y0 REAL, x1 REAL, y1 REAL,
            descripcion      TEXT,
            categorias       TEXT,
            texto_visible    TEXT,
            contexto_historico TEXT,
            proveedor        TEXT,
            modelo           TEXT,
            ts               TEXT,
            PRIMARY KEY (numero, pagina, zona_idx)
        )""")
        ts = datetime.now().isoformat(timespec="seconds")
        for r in resultados:
            con.execute("""INSERT OR REPLACE INTO descripciones_imagen
                (numero,pagina,zona_idx,zona_tipo,x0,y0,x1,y1,
                 descripcion,categorias,texto_visible,contexto_historico,
                 proveedor,modelo,ts)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                r.get("numero",""), r.get("pagina",""), r.get("zona_idx",0),
                r.get("zona_tipo","foto"),
                r.get("x0",0), r.get("y0",0), r.get("x1",1), r.get("y1",1),
                r.get("descripcion",""), json.dumps(r.get("categorias",[]),
                ensure_ascii=False), r.get("texto_visible",""),
                r.get("contexto_historico",""),
                r.get("proveedor",""), r.get("modelo",""), ts,
            ))
        con.commit()
        con.close()
    except Exception:
        pass


def cargar_descripciones_db(db_path: Path, numero: str,
                             pagina: str | None = None) -> list[dict]:
    """Carga descripciones guardadas de la base de datos."""
    try:
        import sqlite3
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        if pagina:
            rows = con.execute(
                "SELECT * FROM descripciones_imagen WHERE numero=? AND pagina=?",
                (numero, pagina)).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM descripciones_imagen WHERE numero=?",
                (numero,)).fetchall()
        con.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["categorias"] = json.loads(d.get("categorias", "[]"))
            except Exception:
                d["categorias"] = []
            result.append(d)
        return result
    except Exception:
        return []


# ── Indexación FAISS ──────────────────────────────────────────────────────────

def _indexar_embeddings(out_dir: Path, numero: str, resultados: list[dict]):
    try:
        import faiss
        import numpy as np

        from core.embeddings_local import get_embedding

        idx_dir = out_dir / "06_indices" / numero
        idx_dir.mkdir(parents=True, exist_ok=True)

        textos = [r.get("descripcion", "") for r in resultados]
        vecs   = np.array([get_embedding(t) for t in textos], dtype=np.float32)
        faiss.normalize_L2(vecs)

        index = faiss.IndexFlatIP(vecs.shape[1])
        index.add(vecs)
        faiss.write_index(index, str(idx_dir / "descripciones.faiss"))

        meta = [{"pagina":   r.get("pagina",""),
                 "zona_idx": r.get("zona_idx", 0),
                 "descripcion": r.get("descripcion",""),
                 "categorias":  r.get("categorias",[])}
                for r in resultados]
        (idx_dir / "descripciones_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass   # FAISS opcional — si no está, la búsqueda por similitud no funciona


# ── Helpers internos ──────────────────────────────────────────────────────────

def _buscar_imagen(img_dir: Path, pagina: str) -> Path | None:
    if not img_dir.exists():
        return None
    for ext in ("*.png", "*.jpg", "*.tif", "*.tiff"):
        hits = sorted(img_dir.glob(f"*{pagina}*")) + sorted(img_dir.glob(ext))
        for h in hits:
            if pagina in h.stem or True:
                return h
    return None


def _resultado_vacio(zona) -> dict:
    return {
        "descripcion": "",
        "categorias": [],
        "texto_visible": "",
        "contexto_historico": "",
        "zona_tipo": getattr(zona, "tipo", "foto"),
        "x0": getattr(zona, "x0", 0),
        "y0": getattr(zona, "y0", 0),
        "x1": getattr(zona, "x1", 1),
        "y1": getattr(zona, "y1", 1),
    }


def _parsear_respuesta(raw: str) -> dict:
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return _resultado_vacio(type("Z", (), {"tipo":"foto","x0":0,"y0":0,"x1":1,"y1":1})())
    try:
        data = json.loads(m.group())
    except Exception:
        data = {}
    return {
        "descripcion":        str(data.get("descripcion", "")).strip(),
        "categorias":         [c for c in data.get("categorias", [])
                               if c in CATEGORIAS_TEMATICAS],
        "texto_visible":      str(data.get("texto_visible", "")).strip(),
        "contexto_historico": str(data.get("contexto_historico", "")).strip(),
    }


def _llamar_vision(img_path: Path, proveedor: str, api_key: str,
                   modelo: str, prompt: str, log) -> str:
    """Llama al proveedor de visión y retorna el texto crudo de la respuesta."""
    import base64
    ext = img_path.suffix.lower()
    mt_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".png": "image/png", ".webp": "image/webp"}
    mt = mt_map.get(ext, "image/jpeg")
    with open(img_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()

    try:
        if proveedor == "claude":
            import anthropic
            m = modelo or "claude-haiku-4-5-20251001"
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=m, max_tokens=512,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64",
                                                  "media_type": mt, "data": b64}},
                    {"type": "text", "text": prompt},
                ]}])
            return resp.content[0].text

        elif proveedor == "openai":
            import openai
            m = modelo or "gpt-4o-mini"
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=m, max_tokens=512,
                messages=[{"role": "user", "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mt};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ]}])
            return resp.choices[0].message.content

        elif proveedor == "gemini":
            import google.generativeai as genai
            from PIL import Image as _I
            genai.configure(api_key=api_key)
            m = modelo or "gemini-1.5-flash"
            gm = genai.GenerativeModel(m)
            img = _I.open(img_path)
            resp = gm.generate_content([prompt, img])
            return resp.text

        elif proveedor == "ollama":
            import requests
            m = modelo or "llava"
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": m, "prompt": prompt,
                      "images": [b64], "stream": False},
                timeout=120)
            return resp.json().get("response", "")

    except Exception as e:
        log(f"⚠ Error {proveedor}: {e}")
        return ""

    return ""
