#!/usr/bin/env python
"""scripts/juez_ground_truth.py — Juez de IA para triage de ground truth OCR.

Adaptado del patrón de Medallo/GullaBench (benchmarks/gullabench/corpus_prep/
llm_judge.py): un modelo de visión evalúa el texto candidato de OCR contra la
imagen real de la página y cita errores concretos, con un puntaje de
plausibilidad. NUNCA decide por su cuenta: entrega evidencia para que un
humano decida en review_app.py (fase siguiente del plan). No promueve ningún
estado a "human_verified" — eso es exclusivo de apply_ground_truth.py sobre
una decisión humana real.

Diseñado para correr SIN el resto de dependencias de Bashkar (torch,
transformers, spacy...): solo necesita el paquete `anthropic`. Así el
workflow de GitHub Actions no tiene que instalar la pila de ML completa.

Uso:
    python scripts/juez_ground_truth.py --piloto-dir ground_truth_piloto/rev_estampa_mar_1939 --dry-run
    python scripts/juez_ground_truth.py --piloto-dir ground_truth_piloto/rev_estampa_mar_1939 --concurrencia 6

Resumible: una página que ya tiene juicio en <piloto-dir>/juicios/<id>.json
se salta (a menos que --forzar).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_MODEL = "claude-sonnet-5"

# USD por millón de tokens. Verificado 2026-08-27 vía skill claude-api.
PRICING_PER_MTOK = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

# Techo prudente de tokens de salida por página (evidencia real: se ajusta
# tras la primera corrida real comparando con response.usage.output_tokens).
ASSUMED_OUTPUT_TOKENS = 800

_SYSTEM_PROMPT = (
    "Eres un verificador de OCR de prensa histórica en español (Bogotá, "
    "Colombia, revista Estampa, 1930-1940). Se te da la imagen de una "
    "página escaneada y el texto que un motor de OCR propuso para esa "
    "página. Señala errores concretos del texto propuesto comparándolo con "
    "lo que de verdad se lee en la imagen. No reescribas el texto completo. "
    "No inventes errores que no puedas verificar mirando la imagen — si una "
    "parte de la imagen es ilegible, dilo en vez de adivinar. Preserva "
    "arcaísmos ortográficos legítimos del español de los años 30 (no son "
    "errores de OCR). Responde ÚNICAMENTE con JSON válido, sin texto "
    "adicional, con esta forma exacta: "
    '{"accuracy_estimate": <número 0.0 a 1.0>, "errors": [{"quote": '
    '"<fragmento EXACTO del texto propuesto que está mal>", "issue": '
    '"<qué está mal, en pocas palabras>"}], "notes": "<opcional, una frase>"}'
)


class JudgeResponseError(ValueError):
    """El modelo no devolvió el JSON esperado."""


@dataclass(frozen=True)
class JudgeIssue:
    quote: str
    issue: str


@dataclass(frozen=True)
class JudgeResult:
    pagina_id: str
    accuracy_estimate: float
    errors: list  # list[JudgeIssue] serializado como dicts
    notes: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


def estimate_cost_usd(input_tokens: int, output_tokens: int, *, model: str) -> float:
    prices = PRICING_PER_MTOK[model]
    return input_tokens / 1_000_000 * prices["input"] + output_tokens / 1_000_000 * prices["output"]


def _media_type(image_path: Path) -> str:
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(image_path.suffix.lower(), "image/jpeg")


def _image_content_block(image_path: Path) -> dict:
    data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": _media_type(image_path), "data": data},
    }


def build_messages(image_path: Path, candidate_text: str) -> list[dict]:
    return [{
        "role": "user",
        "content": [
            _image_content_block(image_path),
            {"type": "text", "text": f"Texto propuesto por OCR:\n\n{candidate_text}"},
        ],
    }]


def _parse_response_text(text: str, pagina_id: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise JudgeResponseError(
            f"{pagina_id}: el juez no devolvió JSON válido: {text[:300]!r}"
        ) from error


def judge_page(client, pagina_id: str, image_path: Path, candidate_text: str,
                *, model: str = DEFAULT_MODEL, max_tokens: int = 8192) -> JudgeResult:
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=build_messages(image_path, candidate_text),
        output_config={"effort": "low"},
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    if not text:
        raise JudgeResponseError(
            f"{pagina_id}: respuesta sin bloque de texto (stop_reason="
            f"{response.stop_reason!r}) — revisar max_tokens/effort"
        )
    payload = _parse_response_text(text, pagina_id)
    if "accuracy_estimate" not in payload:
        raise JudgeResponseError(f"{pagina_id}: falta 'accuracy_estimate' en la respuesta")

    return JudgeResult(
        pagina_id=pagina_id,
        accuracy_estimate=float(payload["accuracy_estimate"]),
        errors=[{"quote": e["quote"], "issue": e["issue"]} for e in payload.get("errors", [])],
        notes=payload.get("notes", ""),
        model=model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cost_usd=estimate_cost_usd(response.usage.input_tokens, response.usage.output_tokens, model=model),
    )


def _cargar_manifiesto(piloto_dir: Path) -> dict:
    manifiesto_path = piloto_dir / "manifiesto_piloto.json"
    return json.loads(manifiesto_path.read_text(encoding="utf-8"))


def _paginas_pendientes(piloto_dir: Path, manifiesto: dict, *, forzar: bool) -> list[dict]:
    juicios_dir = piloto_dir / "juicios"
    pendientes = []
    for pagina in manifiesto["paginas"]:
        destino = juicios_dir / f"{pagina['pagina_id']}.json"
        if destino.exists() and not forzar:
            continue
        pendientes.append(pagina)
    return pendientes


def estimar_costo(client, piloto_dir: Path, paginas: list[dict], *, modelo: str) -> tuple[int, float]:
    """Cuenta tokens REALES de entrada (vía count_tokens, sin generar) para
    cada página pendiente; el de salida es el techo asumido. No gasta en
    generación — solo en conteo, que no se cobra por generación."""
    total_input = 0
    for pagina in paginas:
        texto = (piloto_dir / pagina["candidato"]).read_text(encoding="utf-8", errors="replace")
        imagen = piloto_dir / pagina["imagen"]
        resp = client.messages.count_tokens(
            model=modelo, system=_SYSTEM_PROMPT,
            messages=build_messages(imagen, texto),
        )
        total_input += resp.input_tokens
    total_output_asumido = len(paginas) * ASSUMED_OUTPUT_TOKENS
    costo = estimate_cost_usd(total_input, total_output_asumido, model=modelo)
    return total_input, costo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piloto-dir", type=Path, required=True)
    parser.add_argument("--modelo", default=DEFAULT_MODEL)
    parser.add_argument("--concurrencia", type=int, default=4)
    parser.add_argument("--forzar", action="store_true", help="Rejuzgar páginas ya juzgadas")
    parser.add_argument("--limite", type=int, default=None, help="Tope de páginas (pruebas)")
    parser.add_argument("--dry-run", action="store_true", help="Solo estima costo, no gasta en generación")
    args = parser.parse_args()

    import anthropic
    client = anthropic.Anthropic()

    manifiesto = _cargar_manifiesto(args.piloto_dir)
    pendientes = _paginas_pendientes(args.piloto_dir, manifiesto, forzar=args.forzar)
    if args.limite:
        pendientes = pendientes[: args.limite]

    if not pendientes:
        print("No hay páginas pendientes de juzgar (todas ya tienen juicio; usa --forzar para rehacer).")
        return 0

    if args.dry_run:
        print(f"Estimando costo real de {len(pendientes)} página(s) con {args.modelo}…")
        tokens_in, costo = estimar_costo(client, args.piloto_dir, pendientes, modelo=args.modelo)
        print(f"Tokens de entrada (reales, contados): {tokens_in:,}")
        print(f"Tokens de salida asumidos (techo, {ASSUMED_OUTPUT_TOKENS}/pág): {len(pendientes) * ASSUMED_OUTPUT_TOKENS:,}")
        print(f"COSTO ESTIMADO: ${costo:.4f} USD para {len(pendientes)} página(s)")
        print("Nada se gastó en generación. Corre sin --dry-run para ejecutar de verdad.")
        return 0

    juicios_dir = args.piloto_dir / "juicios"
    juicios_dir.mkdir(parents=True, exist_ok=True)

    resultados: list[JudgeResult] = []
    errores: list[str] = []
    inicio = time.monotonic()

    def _trabajar(pagina: dict) -> JudgeResult:
        texto = (args.piloto_dir / pagina["candidato"]).read_text(encoding="utf-8", errors="replace")
        imagen = args.piloto_dir / pagina["imagen"]
        return judge_page(client, pagina["pagina_id"], imagen, texto, model=args.modelo)

    with ThreadPoolExecutor(max_workers=args.concurrencia) as pool:
        futuros = {pool.submit(_trabajar, p): p["pagina_id"] for p in pendientes}
        for futuro in as_completed(futuros):
            pagina_id = futuros[futuro]
            try:
                resultado = futuro.result()
            except Exception as error:  # noqa: BLE001 — se reporta, no se detiene el lote
                errores.append(f"{pagina_id}: {error}")
                print(f"  ✗ {pagina_id}: ERROR — {error}")
                continue
            (juicios_dir / f"{resultado.pagina_id}.json").write_text(
                json.dumps(asdict(resultado), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            resultados.append(resultado)
            print(f"  ✓ {resultado.pagina_id}: accuracy={resultado.accuracy_estimate:.2f} "
                  f"errores={len(resultado.errors)} costo=${resultado.cost_usd:.4f}")

    duracion = time.monotonic() - inicio
    costo_total = sum(r.cost_usd for r in resultados)
    print(f"\n{len(resultados)}/{len(pendientes)} páginas juzgadas en {duracion/60:.1f} min. "
          f"Costo real: ${costo_total:.4f} USD.")
    if errores:
        print(f"{len(errores)} página(s) con error (reintentar con --forzar):")
        for e in errores:
            print(f"  - {e}")

    return 1 if errores and not resultados else 0


if __name__ == "__main__":
    sys.exit(main())
