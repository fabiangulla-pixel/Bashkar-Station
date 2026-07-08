"""core/costos.py — Estimación de tokens y costo ANTES de llamar a la IA externa.

Estándar transversal de los proyectos con API key: antes de ejecutar una tarea
contra un proveedor de pago hay que (1) contabilizar el volumen de datos, (2)
estimar los tokens y (3) traducirlo a dólares, para que el usuario confirme el
gasto. Tras la ejecución se registra el costo REAL (leído del `usage` que
devuelve el proveedor) y se compara contra lo estimado.

Bashkar es MULTIPROVEEDOR (claude por defecto, openai, gemini, ollama) y de DOS
modalidades: visión (imagen → texto) y corrección de texto. ollama es local =
costo 0. Por eso este módulo modela:
- precios por modelo de cada proveedor de pago;
- tokens de IMAGEN además de los de texto.

Tokens de imagen (Claude): ≈ (ancho × alto) / 750, con tope ~1600 porque la API
reescala imágenes grandes a ~1.15 megapíxeles. Para una estimación previa sin
abrir cada imagen usamos la COTA de 1600 tokens/imagen (cota superior prudente,
alineada con el estándar de no subestimar el gasto). NO usar tiktoken (es de
OpenAI y subcuenta los tokens de Claude).

Precios (USD por 1M de tokens):
- Claude — verificados contra la skill claude-api (cache 2026-06-04):
    claude-sonnet-4-6 $3/$15 (visión por defecto), claude-haiku-4-5 $1/$5
    (texto por defecto), claude-opus-4-8 $5/$25, claude-fable-5 $10/$50.
- OpenAI — verificados en web 2026-06-27: gpt-4o $2.50/$10, gpt-4o-mini $0.15/$0.60.
- Gemini — gemini-1.5-flash ~ $0.075/$0.30 (orden de magnitud; refinar si se usa).
- ollama — LOCAL, costo 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PRECIOS_VERIFICADOS_EL = "2026-06-27"
CARACTERES_POR_TOKEN = 4.0
# Cota superior de tokens por imagen en Claude (imagen reescalada al máximo).
TOKENS_IMAGEN_COTA = 1600


@dataclass(frozen=True)
class PrecioModelo:
    input_por_millon: float
    output_por_millon: float


# Tabla por familia de modelo (lookup empareja por prefijo: los ids traen sufijo
# de fecha, p. ej. claude-haiku-4-5-20251001).
PRECIOS: dict[str, PrecioModelo] = {
    # Claude (skill claude-api, cache 2026-06-04)
    "claude-opus-4-8": PrecioModelo(5.00, 25.00),
    "claude-opus-4-7": PrecioModelo(5.00, 25.00),
    "claude-sonnet-4-6": PrecioModelo(3.00, 15.00),
    "claude-haiku-4-5": PrecioModelo(1.00, 5.00),
    "claude-fable-5": PrecioModelo(10.00, 50.00),
    # OpenAI (web 2026-06-28). Nota: gpt-5.5 >272K ctx sube a 2x in / 1.5x out.
    "gpt-5.5": PrecioModelo(5.00, 30.00),
    "gpt-5.4-mini": PrecioModelo(0.75, 4.50),
    "gpt-4o-mini": PrecioModelo(0.15, 0.60),
    "gpt-4o": PrecioModelo(2.50, 10.00),
    # Gemini (web 2026-06-28). 2.5-pro sube a 2.50/15.00 sobre 200K ctx.
    "gemini-2.5-flash": PrecioModelo(0.30, 2.50),
    "gemini-2.5-pro": PrecioModelo(1.25, 10.00),
    "gemini-3-pro": PrecioModelo(1.25, 10.00),
    "gemini-3.1-flash": PrecioModelo(0.30, 2.50),
    "gemini-1.5-flash": PrecioModelo(0.075, 0.30),
    "gemini-1.5-pro": PrecioModelo(1.25, 5.00),
}

PROVEEDORES_LOCALES = {"ollama", "lmstudio"}


def _precio_de(modelo: str) -> tuple[PrecioModelo, bool]:
    """Devuelve (precio, es_catalogado). Empareja por prefijo de familia.

    Modelo no catalogado → precio más caro conocido (cota superior conservadora).
    """
    base = (modelo or "").strip().lower()
    # Empareja por el prefijo más largo que aplique (evita que "gpt-4o" capture
    # a "gpt-4o-mini": se prueba de la clave más larga a la más corta).
    for familia in sorted(PRECIOS, key=len, reverse=True):
        if base == familia or base.startswith(familia):
            return PRECIOS[familia], True
    mas_caro = max(PRECIOS.values(), key=lambda p: p.output_por_millon)
    return mas_caro, False


def estimar_tokens(texto: str) -> int:
    if not texto:
        return 0
    return int(len(texto) / CARACTERES_POR_TOKEN) + 1


def _costo(tokens_in: int, tokens_out: int, precio: PrecioModelo) -> float:
    return (
        tokens_in / 1_000_000 * precio.input_por_millon
        + tokens_out / 1_000_000 * precio.output_por_millon
    )


@dataclass
class EstimacionCosto:
    proveedor: str
    modelo: str
    n_items: int
    n_imagenes: int
    tokens_input: int
    tokens_output: int
    costo_usd: float
    modelo_catalogado: bool
    es_local: bool = False
    notas: list[str] = field(default_factory=list)

    @property
    def tokens_totales(self) -> int:
        return self.tokens_input + self.tokens_output

    def resumen(self) -> str:
        if self.es_local:
            return (
                f"Proveedor: {self.proveedor} (LOCAL)\n"
                f"Páginas a procesar: {self.n_items}\n\n"
                "COSTO ESTIMADO: $0.00 USD (modelo local, sin cargo de API)."
            )
        lineas = [
            f"Proveedor / modelo: {self.proveedor} · {self.modelo}",
            f"Páginas a procesar: {self.n_items}  (de ellas {self.n_imagenes} por visión)",
            f"Tokens estimados de entrada:  {self.tokens_input:,}",
            f"Tokens estimados de salida:   {self.tokens_output:,}",
            f"Tokens totales (aprox.):      {self.tokens_totales:,}",
            "",
            f"COSTO ESTIMADO: ${self.costo_usd:,.4f} USD",
        ]
        if not self.modelo_catalogado:
            lineas.append("")
            lineas.append(
                "⚠ Modelo sin precio catalogado: estimado con el precio más alto "
                "conocido (cota superior). El costo real puede ser MENOR."
            )
        lineas.extend(self.notas)
        lineas.append("")
        lineas.append(
            f"(Precios verificados el {PRECIOS_VERIFICADOS_EL}. Estimación aproximada; "
            "tokens de imagen acotados a ~1600/imagen. Costo real se mide del usage.)"
        )
        return "\n".join(lineas)


def estimar_lote_ocr(
    n_paginas: int,
    proveedor: str,
    modelo: str,
    n_vision: int = 0,
    chars_promedio_texto: int = 3000,
    prompt_overhead_chars: int = 700,
    tokens_salida_por_pagina: int = 4096,
) -> EstimacionCosto:
    """Estima tokens y costo de mejorar `n_paginas` con IA (visión + corrección).

    Alineado con `ocr_llm.mejorar_lote`:
    - `n_vision` páginas van por VISIÓN: cuestan ~1600 tokens de imagen + el prompt.
    - el resto va por CORRECCIÓN de texto: ~`chars_promedio_texto` (cap 6000 en el
      motor) + el prompt.
    - salida acotada por max_tokens (4096) por página. Cota superior: la respuesta
      real suele ser menor, así el costo tiende a sobreestimar (prudente).

    `chars_promedio_texto` es el promedio de caracteres OCR por página; ajústalo a
    los datos reales si se conoce.
    """
    proveedor = (proveedor or "").strip().lower()
    if proveedor in PROVEEDORES_LOCALES:
        return EstimacionCosto(
            proveedor=proveedor, modelo=modelo, n_items=n_paginas, n_imagenes=n_vision,
            tokens_input=0, tokens_output=0, costo_usd=0.0,
            modelo_catalogado=True, es_local=True,
        )

    precio, catalogado = _precio_de(modelo)
    overhead = int(prompt_overhead_chars / CARACTERES_POR_TOKEN)

    n_vision = max(0, min(n_vision, n_paginas))
    n_texto = n_paginas - n_vision

    tokens_input = (
        n_vision * (TOKENS_IMAGEN_COTA + overhead)
        + n_texto * (estimar_tokens("x" * min(chars_promedio_texto, 6000)) + overhead)
    )
    tokens_output = tokens_salida_por_pagina * n_paginas
    costo = _costo(tokens_input, tokens_output, precio)

    notas: list[str] = []
    if n_paginas == 0:
        notas.append("No hay páginas candidatas (todas sobre el umbral de confianza).")

    return EstimacionCosto(
        proveedor=proveedor, modelo=modelo, n_items=n_paginas, n_imagenes=n_vision,
        tokens_input=tokens_input, tokens_output=tokens_output, costo_usd=costo,
        modelo_catalogado=catalogado,
    )


@dataclass
class CostoReal:
    proveedor: str
    modelo: str
    tokens_input: int
    tokens_output: int
    costo_usd: float
    modelo_catalogado: bool

    @property
    def tokens_totales(self) -> int:
        return self.tokens_input + self.tokens_output


def costo_real_desde_usages(proveedor: str, modelo: str, usages: list) -> CostoReal:
    """Suma los `usage` de varias respuestas y calcula el costo real.

    Soporta el `usage` del SDK Anthropic (`input_tokens`/`output_tokens`/
    `cache_creation_input_tokens`) y el de OpenAI (`prompt_tokens`/
    `completion_tokens`), como objeto del SDK o como dict. ollama (local) = 0.
    Respuestas sin usage se ignoran.
    """
    proveedor = (proveedor or "").strip().lower()
    if proveedor in PROVEEDORES_LOCALES:
        return CostoReal(proveedor, modelo, 0, 0, 0.0, True)

    precio, catalogado = _precio_de(modelo)

    def _g(u, *campos):
        if u is None:
            return 0
        for c in campos:
            v = u.get(c) if isinstance(u, dict) else getattr(u, c, None)
            if v:
                return int(v)
        return 0

    tokens_in = 0
    tokens_out = 0
    for u in usages:
        tokens_in += _g(u, "input_tokens", "prompt_tokens") + _g(u, "cache_creation_input_tokens")
        tokens_out += _g(u, "output_tokens", "completion_tokens")

    return CostoReal(
        proveedor=proveedor, modelo=modelo,
        tokens_input=tokens_in, tokens_output=tokens_out,
        costo_usd=_costo(tokens_in, tokens_out, precio),
        modelo_catalogado=catalogado,
    )
