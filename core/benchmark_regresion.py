"""core/benchmark_regresion.py — Benchmark OCR formal con línea base y regresiones.

``core/benchmark_ocr`` sabe medir (CER, WER, similitud). Este módulo le da la
forma de un benchmark reproducible:

  · un **manifiesto** (``benchmark.json``) que declara cada caso: imagen,
    referencia, salidas por ruta de OCR y estratos (revista, año, tipografía,
    calidad de imagen);
  · **métricas por ruta y por estrato**, más dos tasas de segmentación que el
    CER esconde: fusión (``de los`` → ``delos``) y fragmentación
    (``gobierno`` → ``gob ierno``);
  · una **línea base** congelada y la comparación contra ella, que falla si
    una ruta empeora más allá de la tolerancia.

Regla que no se negocia: **la referencia tiene que ser una transcripción
humana**. El manifiesto lo declara (``referencia.tipo == "humana"``) y el
módulo se niega a medir si no lo es. Un juicio de IA (como los de
``ground_truth_piloto/*/juicios``) no es verdad de referencia: medir contra él
produce un CER con apariencia de rigor y sin valor. Tampoco se acepta una
referencia prellenada con la salida de la misma ruta que se evalúa (sesgo
documentado en ``core/estandar_oro``).

Estructura de una carpeta de benchmark::

    benchmark/<corpus_id>/
        benchmark.json
        imagenes/<page_id>.jpg
        referencia/<page_id>.txt          ← transcripción humana
        salidas/<ruta>/<page_id>.txt      ← una carpeta por ruta de OCR
        linea_base.json                   ← la escribe ``guardar_linea_base``
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from core import benchmark_ocr as B

MANIFIESTO = "benchmark.json"
LINEA_BASE = "linea_base.json"
ESTRATOS = ("revista", "anio", "tipografia", "calidad_imagen", "tipologia")
# Tolerancia absoluta por defecto: medio punto de CER. Menos que eso es ruido
# de normalización en muestras del tamaño de un piloto.
TOLERANCIA = 0.005


class ReferenciaNoHumana(ValueError):
    """El manifiesto no declara una transcripción humana como referencia."""


# ── Manifiesto ────────────────────────────────────────────────────────────────

def cargar_manifiesto(carpeta, exigir_referencia: bool = True) -> dict:
    carpeta = Path(carpeta)
    ruta = carpeta / MANIFIESTO
    if not ruta.exists():
        raise FileNotFoundError(f"No hay {MANIFIESTO} en {carpeta}")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if exigir_referencia:
        validar_manifiesto(datos)
    return datos


def validar_manifiesto(datos: dict) -> None:
    for clave in ("corpus_id", "referencia", "casos"):
        if clave not in datos:
            raise ValueError(f"benchmark.json sin '{clave}'")
    ref = datos["referencia"]
    if ref.get("tipo") != "humana":
        raise ReferenciaNoHumana(
            f"referencia.tipo = {ref.get('tipo')!r}. Solo una transcripción "
            "humana sirve como verdad de referencia; un juicio de IA no.")
    if not ref.get("transcriptor"):
        raise ReferenciaNoHumana("referencia.transcriptor vacío: ¿quién transcribió?")
    ids = [c.get("page_id") for c in datos["casos"]]
    if len(ids) != len(set(ids)) or not all(ids):
        raise ValueError("page_id vacío o repetido en benchmark.json")


def _leer(carpeta: Path, rel: str) -> str | None:
    ruta = carpeta / rel
    return ruta.read_text(encoding="utf-8") if ruta.exists() else None


def cargar_textos(carpeta) -> tuple[dict, dict[str, str], dict[str, dict[str, str]]]:
    """(manifiesto, referencias, salidas por ruta). Casos sin referencia se omiten."""
    carpeta = Path(carpeta)
    man = cargar_manifiesto(carpeta)
    prellenado_con = man["referencia"].get("prellenado_con") or ""
    referencias: dict[str, str] = {}
    salidas: dict[str, dict[str, str]] = defaultdict(dict)
    for caso in man["casos"]:
        pid = caso["page_id"]
        ref = _leer(carpeta, caso.get("referencia", f"referencia/{pid}.txt"))
        if not ref or not ref.strip():
            continue
        referencias[pid] = ref
    rutas_dir = carpeta / "salidas"
    if rutas_dir.is_dir():
        for sub in sorted(p for p in rutas_dir.iterdir() if p.is_dir()):
            if sub.name == prellenado_con:
                # Medir una ruta contra una referencia hecha corrigiendo su
                # propia salida la favorece: se excluye y se avisa.
                continue
            for pid in referencias:
                txt = _leer(sub, f"{pid}.txt")
                if txt is not None:
                    salidas[sub.name][pid] = txt
    return man, referencias, dict(salidas)


# ── Tasas de segmentación ─────────────────────────────────────────────────────

def tasas_segmentacion(referencia: str, hipotesis: str) -> dict[str, float]:
    """Aproximación léxica de fusión y fragmentación de palabras.

    fusión: tokens de la hipótesis que son la concatenación de dos palabras
    consecutivas de la referencia y no existen como palabra en ella.
    fragmentación: pares consecutivos de la hipótesis cuya concatenación es una
    palabra de la referencia, sin que ninguna de las dos piezas lo sea.
    Ambas se expresan sobre el número de palabras de la referencia.
    """
    ref = B.normalizar(referencia).split()
    hip = B.normalizar(hipotesis).split()
    if not ref:
        return {"fusion": 0.0, "fragmentacion": 0.0}
    vocab = set(ref)
    pegadas = {a + b for a, b in zip(ref, ref[1:], strict=False)} - vocab
    fusiones = sum(1 for t in hip if t in pegadas)
    fragmentos = sum(1 for a, b in zip(hip, hip[1:], strict=False)
                     if a + b in vocab and a not in vocab and b not in vocab)
    return {"fusion": round(fusiones / len(ref), 4),
            "fragmentacion": round(fragmentos / len(ref), 4)}


# ── Evaluación ────────────────────────────────────────────────────────────────

@dataclass
class ResultadoRuta:
    ruta: str
    global_: dict
    por_estrato: dict[str, dict[str, dict]] = field(default_factory=dict)
    por_pagina: list[dict] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {"ruta": self.ruta, "global": self.global_,
                "por_estrato": self.por_estrato, "por_pagina": self.por_pagina}


def _metricas(referencias: dict[str, str], hip: dict[str, str]) -> tuple[dict, list]:
    res = B.comparar(referencias, hip)
    seg = defaultdict(float)
    palabras = 0
    for pid, ref in referencias.items():
        n = len(B.normalizar(ref).split())
        t = tasas_segmentacion(ref, hip.get(pid, ""))
        seg["fusion"] += t["fusion"] * n
        seg["fragmentacion"] += t["fragmentacion"] * n
        palabras += n
    glob = {
        "paginas": res.paginas,
        "cer": round(res.cer, 4),
        "wer": round(res.wer, 4),
        "similitud": round(res.similitud, 4),
        "fusion": round(seg["fusion"] / palabras, 4) if palabras else 0.0,
        "fragmentacion": round(seg["fragmentacion"] / palabras, 4) if palabras else 0.0,
        "cobertura": round(sum(1 for p in referencias if p in hip) / len(referencias), 4)
        if referencias else 0.0,
    }
    return glob, res.por_pagina


def evaluar(carpeta) -> dict:
    """Evalúa todas las rutas del benchmark. Devuelve un dict serializable."""
    man, referencias, salidas = cargar_textos(carpeta)
    casos = {c["page_id"]: c for c in man["casos"]}
    rutas = []
    for ruta, hip in sorted(salidas.items()):
        glob, por_pag = _metricas(referencias, hip)
        r = ResultadoRuta(ruta=ruta, global_=glob, por_pagina=por_pag)
        for estrato in ESTRATOS:
            grupos: dict[str, dict[str, str]] = defaultdict(dict)
            for pid, ref in referencias.items():
                valor = casos[pid].get(estrato)
                if valor not in (None, ""):
                    grupos[str(valor)][pid] = ref
            if grupos:
                r.por_estrato[estrato] = {
                    v: _metricas(refs, hip)[0] for v, refs in sorted(grupos.items())}
        rutas.append(r.como_dict())
    advertencias = []
    excluida = man["referencia"].get("prellenado_con")
    if excluida:
        advertencias.append(f"Ruta '{excluida}' excluida: la referencia se prellenó con ella.")
    sin_ref = len(casos) - len(referencias)
    if sin_ref:
        advertencias.append(f"{sin_ref} casos sin transcripción humana todavía; no se miden.")
    if len(referencias) < 20:
        advertencias.append(
            f"Solo {len(referencias)} páginas con referencia: las diferencias entre "
            "rutas pueden ser ruido. No publicar conclusiones con esta muestra.")
    return {"corpus_id": man["corpus_id"], "paginas_con_referencia": len(referencias),
            "rutas": rutas, "advertencias": advertencias}


# ── Línea base y regresiones ──────────────────────────────────────────────────

def guardar_linea_base(carpeta, resultado: dict | None = None) -> Path:
    """Congela las métricas actuales, con manifiesto de ejecución completo."""
    from core import proveniencia as P
    carpeta = Path(carpeta)
    resultado = resultado or evaluar(carpeta)
    refs = sorted((carpeta / "referencia").glob("*.txt"))
    man = P.manifiesto_ejecucion(
        tipo="benchmark_ocr_linea_base",
        corpus={"id": resultado["corpus_id"], "version": P.hash_archivos(refs),
                "n_paginas": resultado["paginas_con_referencia"]},
        metricas={r["ruta"]: r["global"] for r in resultado["rutas"]},
        advertencias=resultado["advertencias"],
    )
    man["resultado"] = resultado
    return P.escribir_manifiesto(man, carpeta / LINEA_BASE)


# Métricas donde subir es empeorar.
_PEOR_SI_SUBE = ("cer", "wer", "fusion", "fragmentacion")


def comparar_con_base(actual: dict, base: dict, tolerancia: float = TOLERANCIA) -> list[str]:
    """Lista de regresiones legibles; vacía si no hay.

    ``base`` puede ser el JSON de ``linea_base.json`` o el resultado de ``evaluar``.
    Una ruta que estaba en la base y desapareció también es una regresión.
    """
    base_res = base.get("resultado", base)
    previas = {r["ruta"]: r["global"] for r in base_res["rutas"]}
    ahora = {r["ruta"]: r["global"] for r in actual["rutas"]}
    problemas = []
    for ruta, m0 in previas.items():
        m1 = ahora.get(ruta)
        if m1 is None:
            problemas.append(f"{ruta}: la ruta ya no produce salidas")
            continue
        for k in _PEOR_SI_SUBE:
            if k in m0 and k in m1 and m1[k] - m0[k] > tolerancia:
                problemas.append(f"{ruta}: {k} {m0[k]:.4f} → {m1[k]:.4f}")
        if m1.get("cobertura", 1) < m0.get("cobertura", 1):
            problemas.append(f"{ruta}: cobertura {m0['cobertura']} → {m1['cobertura']}")
    return problemas


# ── Generar salidas con el pipeline real ──────────────────────────────────────

def generar_salidas(carpeta, ruta: str = "tesseract", log=print) -> int:
    """Corre una ruta de OCR (``core.benchmark_ocr.correr_ruta``, el mismo
    código que usa la app) sobre las imágenes del benchmark y guarda sus
    salidas en ``salidas/<ruta>/``. Devuelve cuántas páginas escribió."""
    from core.benchmark_ocr import correr_ruta
    carpeta = Path(carpeta)
    # Producir salidas no requiere referencia: se pueden generar antes de transcribir.
    man = cargar_manifiesto(carpeta, exigir_referencia=False)
    imagenes = []
    for caso in man["casos"]:
        img = carpeta / caso.get("imagen", f"imagenes/{caso['page_id']}.jpg")
        if img.exists():
            imagenes.append((caso["page_id"], img))
    textos = correr_ruta(ruta, [img for _, img in imagenes], log)
    destino = carpeta / "salidas" / ruta
    destino.mkdir(parents=True, exist_ok=True)
    n = 0
    for pid, img in imagenes:
        if img.stem in textos:
            (destino / f"{pid}.txt").write_text(textos[img.stem], encoding="utf-8")
            n += 1
    return n


def generar_salidas_tesseract(carpeta, nombre_ruta: str = "tesseract",
                              lang: str = "spa") -> int:
    """Compatibilidad: equivale a ``generar_salidas(carpeta, "tesseract")``."""
    return generar_salidas(carpeta, "tesseract")

def tabla_markdown(resultado: dict) -> str:
    filas = ["| Ruta | Págs | CER | WER | Fusión | Fragm. | Cobertura |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(resultado["rutas"], key=lambda r: r["global"]["cer"]):
        g = r["global"]
        filas.append(f"| {r['ruta']} | {g['paginas']} | {g['cer']:.3f} | {g['wer']:.3f} | "
                     f"{g['fusion']:.3f} | {g['fragmentacion']:.3f} | {g['cobertura']:.0%} |")
    for a in resultado["advertencias"]:
        filas.append(f"\n> ⚠ {a}")
    return "\n".join(filas)
