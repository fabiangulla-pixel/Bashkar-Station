"""
Extracción multimodal estructurada de páginas de hemeroteca histórica.

A diferencia de `ocr_llm.ocr_con_vision` (que devuelve texto plano), este módulo
fuerza la salida de la IA de visión hacia un **esquema JSON estricto**: artículo
principal con jerarquía (título/antetítulo/secciones), registro de imágenes con
sus pies de página, y bloque publicitario. Transforma un bloque de píxeles no
estructurado en datos relacionales que el resto de Bashkar puede analizar.

Es la respuesta al hallazgo de la auditoría (sesión 36): las imágenes BNC de
microfilm NO se rescatan con preproceso clásico; requieren OCR por IA de visión.
Aquí esa salida queda además ESTRUCTURADA, lista para alimentar corpus_txt, el
índice NER, el grafo canónico y el análisis de publicidad.

Diseño:
- Función pura imagen→dict validado (`extraer_pagina`).
- Procesamiento de directorio robusto: try/except por página, no se detiene si
  una es ilegible (`procesar_directorio`).
- Reusa los clientes por proveedor de `core.ocr_llm` y el acumulador de usages
  (para que el costo real del lote salga del mismo sitio que el OCR normal).
- Reusa `core.costos.estimar_lote_ocr` para el presupuesto previo.
- Sin dependencias nuevas: validación con dataclasses + json estándar (el
  proyecto es offline-first; Pydantic no es dependencia del proyecto).

El módulo NO importa tkinter (regla del proyecto: core/ desacoplado de la UI).
"""

from __future__ import annotations

import base64
import gc
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core import ocr_llm

# ── Prompt Maestro (instrucción core, idéntica por imagen para consistencia) ──

PROMPT_MAESTRO = """Rol: Eres un procesador automatizado de hemeroteca histórica.
Tarea: Analiza la imagen adjunta de una página de revista/periódico ilustrado \
colombiano de los años 1930-1940 y extrae TODA la información en formato JSON estricto.

Estructura obligatoria del objeto JSON:
{
  "pagina_metadata": {
    "numero_pagina": <int o null>,
    "fuente_digital": <str o null>,
    "contexto_historico_estimado": <str o null>
  },
  "articulo_principal": {
    "titulo": <str>,
    "antetitulo_subtitulo": <str o null>,
    "autor": <str o null>,
    "bloques_contenido": [
      {"tipo": "parrafo_introductorio"|"parrafo_transicion"|"seccion",
       "texto": <str, para párrafos sueltos>,
       "subtitulo": <str, solo si tipo=seccion>,
       "parrafos": [<str>, ...]   // solo si tipo=seccion
      }
    ]
  },
  "imagenes_registro": [
    {"id_imagen": <int>, "posicion_relativa": <str>,
     "descripcion_contenido": <str>, "pie_de_pagina": <str literal>}
  ],
  "bloque_publicitario": [
    {"id_anuncio": <int>, "entidad": <str>, "tipo": <str>, "glosa_texto": <str>}
  ]
}

Reglas:
- Transcribe el texto MANTENIENDO la ortografía de época (NO modernices: conserva
  "habia", "fué", "á", tildes y formas históricas). Son datos, no errores.
- Respeta la jerarquía semántica (título, antetítulo, secciones con subtítulo).
- Registra CADA fotografía con su pie de página LITERAL.
- Aísla CADA anuncio publicitario con su entidad y texto promocional.
- Si un campo no existe en la página, usa null o un array vacío [].
Restricción de salida: Devuelve ÚNICAMENTE el objeto JSON válido. No agregues \
texto introductorio, ni vallas de código markdown, ni conclusiones."""


# ── Esquema (validación ligera con dataclasses) ──────────────────────────────

CLAVES_OBLIGATORIAS = (
    "pagina_metadata",
    "articulo_principal",
    "imagenes_registro",
    "bloque_publicitario",
)


@dataclass
class ResultadoPagina:
    """Resultado de procesar una imagen. `ok=False` => página fallida (no detiene el lote)."""

    imagen: str
    ok: bool
    datos: dict = field(default_factory=dict)
    error: str = ""
    ruta_json: str | None = None
    ruta_md: str | None = None


class JSONInvalidoError(ValueError):
    """La respuesta del modelo no es un objeto JSON válido con la estructura esperada."""


# ── Parseo tolerante de la respuesta del modelo ──────────────────────────────

_RE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _extraer_json(raw: str) -> dict:
    """Convierte la respuesta cruda del modelo en dict, tolerando vallas de código
    y prosa accidental alrededor del objeto JSON."""
    if not raw or not raw.strip():
        raise JSONInvalidoError("Respuesta vacía del modelo.")

    texto = _RE_FENCE.sub("", raw.strip()).strip()

    # Intento directo
    try:
        obj = json.loads(texto)
    except json.JSONDecodeError:
        # Recorte al primer { … último } por si el modelo añadió prosa
        ini, fin = texto.find("{"), texto.rfind("}")
        if ini == -1 or fin == -1 or fin <= ini:
            raise JSONInvalidoError("No se encontró un objeto JSON en la respuesta.")
        try:
            obj = json.loads(texto[ini : fin + 1])
        except json.JSONDecodeError as e:
            raise JSONInvalidoError(f"JSON malformado: {e}") from e

    if not isinstance(obj, dict):
        raise JSONInvalidoError("El JSON raíz no es un objeto.")
    return obj


def validar_pagina(obj: dict) -> dict:
    """Valida y normaliza el dict de una página. Rellena claves faltantes con
    valores vacíos para que el resto del pipeline nunca reviente por KeyError."""
    if not isinstance(obj, dict):
        raise JSONInvalidoError("Se esperaba un objeto JSON.")

    norm: dict = {}
    norm["pagina_metadata"] = obj.get("pagina_metadata") or {}
    if not isinstance(norm["pagina_metadata"], dict):
        norm["pagina_metadata"] = {}

    art = obj.get("articulo_principal") or {}
    if not isinstance(art, dict):
        art = {}
    art.setdefault("titulo", "")
    art.setdefault("antetitulo_subtitulo", None)
    art.setdefault("autor", None)
    bloques = art.get("bloques_contenido") or []
    art["bloques_contenido"] = bloques if isinstance(bloques, list) else []
    norm["articulo_principal"] = art

    imgs = obj.get("imagenes_registro") or []
    norm["imagenes_registro"] = imgs if isinstance(imgs, list) else []

    pub = obj.get("bloque_publicitario") or []
    norm["bloque_publicitario"] = pub if isinstance(pub, list) else []

    # Una página utilizable tiene al menos título o algún bloque de contenido.
    if not (norm["articulo_principal"]["titulo"] or norm["articulo_principal"]["bloques_contenido"]
            or norm["imagenes_registro"] or norm["bloque_publicitario"]):
        raise JSONInvalidoError("Página sin contenido extraíble.")
    return norm


# ── Llamada a la IA de visión forzando JSON ──────────────────────────────────

def _cargar_imagen_bytes(img_path: Path) -> tuple[bytes, str]:
    """Carga bytes + media_type, convirtiendo TIFF/BMP a JPEG (igual que ocr_llm)."""
    ext = img_path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".tif": "image/jpeg", ".tiff": "image/jpeg", ".bmp": "image/jpeg",
                 ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")
    if ext in (".tif", ".tiff", ".bmp"):
        try:
            import io

            from PIL import Image
            im = Image.open(img_path).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=92)
            del im
            return buf.getvalue(), "image/jpeg"
        except ImportError:
            return img_path.read_bytes(), media_type
    return img_path.read_bytes(), media_type


def extraer_pagina(
    img_path,
    api_key: str,
    proveedor: str = "gemini",
    modelo: str | None = None,
    prompt: str = PROMPT_MAESTRO,
) -> dict:
    """Extrae el JSON estructurado de UNA imagen de página.

    Proveedores: gemini (default, ideal en lote) | claude | openai | ollama
    | lmstudio (local, servidor OpenAI-compatible en localhost:1234).
    Registra el usage en el acumulador de `core.ocr_llm` (costo real del lote).
    Lanza FileNotFoundError, JSONInvalidoError o el error del proveedor.
    """
    img_path = Path(img_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {img_path}")

    img_bytes, media_type = _cargar_imagen_bytes(img_path)
    img_b64 = base64.b64encode(img_bytes).decode()
    prov = (proveedor or "gemini").strip().lower()

    try:
        from core import inference_provider as _ip
        resp = _ip.generate_vision(
            prov, prompt, img_b64, media_type,
            api_key=api_key, modelo=modelo, json_mode=True, timeout_ollama=180,
            cliente_claude=ocr_llm._cliente_claude,
            cliente_openai=ocr_llm._cliente_openai,
            cliente_lmstudio=ocr_llm._cliente_lmstudio,
            modelo_default_gemini="gemini-2.5-flash",
        )
        ocr_llm._registrar_usage_valor(resp.usage)
        raw = resp.texto
    finally:
        del img_bytes, img_b64
        gc.collect()

    return validar_pagina(_extraer_json(raw))


# ── JSON → Markdown legible ──────────────────────────────────────────────────

def json_a_markdown(datos: dict) -> str:
    """Genera el .md jerárquico de una página a partir del JSON validado."""
    datos = validar_pagina(datos)
    meta = datos["pagina_metadata"]
    art = datos["articulo_principal"]
    out: list[str] = []

    titulo = art.get("titulo") or "(sin título)"
    out.append(f"# {titulo}\n")

    ante = art.get("antetitulo_subtitulo")
    if ante:
        out.append(f"*{ante}*\n")
    autor = art.get("autor")
    if autor:
        out.append(f"**Autor:** {autor}\n")

    linea_meta = []
    if meta.get("numero_pagina") is not None:
        linea_meta.append(f"Página {meta['numero_pagina']}")
    if meta.get("contexto_historico_estimado"):
        linea_meta.append(str(meta["contexto_historico_estimado"]))
    if meta.get("fuente_digital"):
        linea_meta.append(str(meta["fuente_digital"]))
    if linea_meta:
        out.append("> " + " · ".join(linea_meta) + "\n")

    for bloque in art.get("bloques_contenido", []):
        if not isinstance(bloque, dict):
            continue
        tipo = bloque.get("tipo", "")
        if tipo == "seccion":
            sub = bloque.get("subtitulo")
            if sub:
                out.append(f"\n## {sub}\n")
            for p in bloque.get("parrafos", []) or []:
                out.append(f"{p}\n")
        else:
            texto = bloque.get("texto")
            if texto:
                out.append(f"{texto}\n")

    imgs = datos.get("imagenes_registro", [])
    if imgs:
        out.append("\n## Imágenes\n")
        for im in imgs:
            if not isinstance(im, dict):
                continue
            idx = im.get("id_imagen", "?")
            pos = im.get("posicion_relativa", "")
            desc = im.get("descripcion_contenido", "")
            pie = im.get("pie_de_pagina", "")
            out.append(f"- **Imagen {idx}** ({pos}): {desc}")
            if pie:
                out.append(f"  - *Pie:* {pie}")

    anuncios = datos.get("bloque_publicitario", [])
    if anuncios:
        out.append("\n## Publicidad\n")
        for an in anuncios:
            if not isinstance(an, dict):
                continue
            ent = an.get("entidad", "")
            tp = an.get("tipo", "")
            glosa = an.get("glosa_texto", "")
            out.append(f"- **{ent}** ({tp}): {glosa}")

    return "\n".join(out).rstrip() + "\n"


# ── Puentes al pipeline existente ────────────────────────────────────────────

def json_a_texto_plano(datos: dict) -> str:
    """Aplana el JSON al texto corrido que espera `ST.corpus_txt` (análisis,
    NER, lingüística). Incluye título, antetítulo y todos los párrafos; NO mete
    pies de foto ni publicidad para no contaminar el cuerpo del artículo."""
    datos = validar_pagina(datos)
    art = datos["articulo_principal"]
    partes: list[str] = []
    if art.get("titulo"):
        partes.append(art["titulo"])
    if art.get("antetitulo_subtitulo"):
        partes.append(art["antetitulo_subtitulo"])
    for bloque in art.get("bloques_contenido", []):
        if not isinstance(bloque, dict):
            continue
        if bloque.get("tipo") == "seccion":
            if bloque.get("subtitulo"):
                partes.append(bloque["subtitulo"])
            partes.extend(p for p in (bloque.get("parrafos") or []) if p)
        elif bloque.get("texto"):
            partes.append(bloque["texto"])
    return "\n\n".join(partes).strip()


def json_a_publicidad(datos: dict) -> list[dict]:
    """Devuelve la lista de anuncios normalizada para el análisis de publicidad."""
    datos = validar_pagina(datos)
    out = []
    for an in datos.get("bloque_publicitario", []):
        if isinstance(an, dict):
            out.append({"entidad": an.get("entidad", ""), "tipo": an.get("tipo", ""),
                        "glosa_texto": an.get("glosa_texto", "")})
    return out


# ── Estimación de costo del lote (estándar de costo-IA) ──────────────────────

def estimar_costo_directorio(carpeta, proveedor: str = "gemini",
                             modelo: str | None = None):
    """Cuenta imágenes y estima tokens/USD ANTES de procesar (estándar costo-IA).

    Toda página va por VISIÓN (n_vision = n_paginas). El prompt maestro es largo
    (~2000 chars) y la salida JSON es densa: se sube el overhead y la cota de
    salida respecto al OCR de texto plano.
    """
    from core import costos
    imgs = listar_imagenes(carpeta)
    mod = modelo or ("gemini-2.5-flash" if proveedor == "gemini" else "")
    return costos.estimar_lote_ocr(
        n_paginas=len(imgs), proveedor=proveedor, modelo=mod,
        n_vision=len(imgs), prompt_overhead_chars=2200,
        tokens_salida_por_pagina=4096,
    )


# ── Lector de directorio + procesamiento masivo robusto ──────────────────────

_EXT_IMG = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp")


def listar_imagenes(carpeta) -> list[Path]:
    """Lista ordenada de imágenes en la carpeta (no recursivo)."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise NotADirectoryError(f"No es una carpeta: {carpeta}")
    return sorted(p for p in carpeta.iterdir()
                  if p.is_file() and p.suffix.lower() in _EXT_IMG)


def procesar_directorio(
    carpeta,
    api_key: str,
    out_dir,
    proveedor: str = "gemini",
    modelo: str | None = None,
    guardar_json: bool = True,
    guardar_md: bool = True,
    callback: Callable[[int, int, ResultadoPagina], None] | None = None,
) -> list[ResultadoPagina]:
    """Procesa todas las imágenes de `carpeta` → JSON + .md en `out_dir`.

    Robusto: un Try/Except por imagen garantiza que el lote no se detiene si una
    página es ilegible (se marca ok=False con el error). Resetea el acumulador de
    usages al empezar; al terminar, `ocr_llm.usages()` tiene el consumo real del
    lote para `costos.costo_real_desde_usages`.

    `callback(idx, total, resultado)` se llama tras cada página (progreso en GUI).
    """
    imgs = listar_imagenes(carpeta)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ocr_llm.reset_usages()
    resultados: list[ResultadoPagina] = []
    total = len(imgs)

    for i, img in enumerate(imgs, 1):
        res = ResultadoPagina(imagen=img.name, ok=False)
        try:
            datos = extraer_pagina(img, api_key, proveedor=proveedor, modelo=modelo)
            res.datos = datos
            res.ok = True
            stem = img.stem
            if guardar_json:
                rj = out_dir / f"{stem}.json"
                rj.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                              encoding="utf-8")
                res.ruta_json = str(rj)
            if guardar_md:
                rm = out_dir / f"{stem}.md"
                rm.write_text(json_a_markdown(datos), encoding="utf-8")
                res.ruta_md = str(rm)
        except Exception as e:  # noqa: BLE001 — robustez: ninguna página detiene el lote
            res.error = f"{type(e).__name__}: {e}"
        resultados.append(res)
        if callback:
            try:
                callback(i, total, res)
            except Exception:  # noqa: BLE001 — el callback de UI no debe tumbar el lote
                pass

    return resultados


def resumen_lote(resultados: list[ResultadoPagina]) -> dict:
    """Estadísticas del lote + costo real (desde el acumulador de usages)."""
    ok = [r for r in resultados if r.ok]
    fallidas = [r for r in resultados if not r.ok]
    return {
        "total": len(resultados),
        "ok": len(ok),
        "fallidas": len(fallidas),
        "imagenes_detectadas": sum(len(r.datos.get("imagenes_registro", [])) for r in ok),
        "anuncios_detectados": sum(len(r.datos.get("bloque_publicitario", [])) for r in ok),
        "paginas_fallidas": [{"imagen": r.imagen, "error": r.error} for r in fallidas],
    }
