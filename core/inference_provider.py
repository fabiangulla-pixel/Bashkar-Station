"""core/inference_provider.py — Capa única de despacho a proveedores LLM.

Unifica el árbol de decisión por `proveedor` (claude/openai/gemini/ollama/
lmstudio) que antes estaba copiado por separado en `core/ocr_llm.py`,
`core/ner_engine.py` y `core/extractor_multimodal.py`. Antes, cambiar cómo se
invoca un proveedor exigía tocar los tres archivos por separado (y ya habían
divergido: `ner_engine.validar_con_llm` no soportaba openai/gemini mientras
los otros dos sí).

Diseño deliberado — NO posee las fábricas de cliente:
    `_cliente_claude` / `_cliente_openai` / `_cliente_lmstudio` siguen
    viviendo en `core/ocr_llm.py` (fuente canónica) y cada llamada las recibe
    inyectadas como parámetro. Así, los tests que hacen
    `monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", stub)` (ver
    tests/test_lmstudio_provider.py) siguen funcionando sin cambios: esta
    capa factoriza el árbol de decisión, no el punto de creación del
    cliente. Por la misma razón, el SDK de Gemini se importa de forma
    perezosa dentro de cada rama (nunca a nivel de módulo), igual que antes
    — es lo que permite a los tests parchear `sys.modules["google.
    generativeai"]` sin que importe qué módulo hizo el `import`.

Cada función devuelve un `ProviderResponse` con el texto y (si el SDK lo
trae) el objeto `usage` crudo, para que el llamante lo registre en su propio
acumulador de costo-IA (`core.ocr_llm._registrar_usage_valor`).
"""

from __future__ import annotations

from typing import Callable


class ProviderResponse:
    """Resultado uniforme de una llamada a proveedor: texto + usage crudo."""

    __slots__ = ("texto", "usage")

    def __init__(self, texto: str, usage=None):
        self.texto = texto
        self.usage = usage


def _mensajes(prompt: str, system: str | None) -> list[dict]:
    msgs = [{"role": "system", "content": system}] if system else []
    msgs.append({"role": "user", "content": prompt})
    return msgs


def generate_text(
    proveedor: str,
    prompt: str,
    *,
    api_key: str,
    modelo: str | None = None,
    max_tokens: int = 4096,
    system: str | None = None,
    cliente_claude: Callable | None = None,
    cliente_openai: Callable | None = None,
    cliente_lmstudio: Callable | None = None,
    modelo_default_claude: str = "claude-sonnet-4-6",
    modelo_default_openai: str = "gpt-4o-mini",
    modelo_default_gemini: str = "gemini-1.5-flash",
    modelo_default_ollama: str = "llama3.1",
    host_ollama: str = "http://localhost:11434",
    timeout_ollama: int = 180,
) -> ProviderResponse:
    """Texto → texto (o texto → JSON en bruto, según el prompt). Sin visión.

    El llamante resuelve `host_ollama` ANTES de llamar (algunos módulos
    permiten pasar una URL propia en `api_key`, otros no) — esta función no
    reinterpreta `api_key` como posible URL, solo usa lo que se le pasó.
    """
    if proveedor == "claude":
        if cliente_claude is None:
            raise ValueError("Proveedor 'claude' requiere cliente_claude")
        client = cliente_claude(api_key)
        kwargs = {"model": modelo or modelo_default_claude, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        msg = client.messages.create(**kwargs)
        return ProviderResponse(msg.content[0].text.strip(), usage=getattr(msg, "usage", None))

    if proveedor == "openai":
        if cliente_openai is None:
            raise ValueError("Proveedor 'openai' requiere cliente_openai")
        client = cliente_openai(api_key)
        resp = client.chat.completions.create(
            model=modelo or modelo_default_openai, max_tokens=max_tokens,
            messages=_mensajes(prompt, system))
        return ProviderResponse(resp.choices[0].message.content.strip(), usage=getattr(resp, "usage", None))

    if proveedor == "gemini":
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError("Instala google-generativeai: pip install google-generativeai") from e
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(modelo or modelo_default_gemini)
        texto_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = m.generate_content(texto_prompt)
        return ProviderResponse(resp.text.strip())

    if proveedor == "ollama":
        import requests as _req
        prompt_final = f"{system}\n\n{prompt}" if system else prompt
        resp = _req.post(
            f"{host_ollama}/api/generate",
            json={"model": modelo or modelo_default_ollama, "prompt": prompt_final, "stream": False},
            timeout=timeout_ollama,
        )
        resp.raise_for_status()
        return ProviderResponse(resp.json().get("response", "").strip())

    if proveedor == "lmstudio":
        if cliente_lmstudio is None:
            raise ValueError("Proveedor 'lmstudio' requiere cliente_lmstudio")
        host = api_key if api_key and api_key.startswith("http") else "http://localhost:1234"
        client = cliente_lmstudio(host)
        resp = client.chat.completions.create(
            model=modelo or "local-model", max_tokens=max_tokens,
            messages=_mensajes(prompt, system))
        return ProviderResponse(resp.choices[0].message.content.strip(), usage=getattr(resp, "usage", None))

    raise ValueError(f"Proveedor desconocido: {proveedor}")


def generate_vision(
    proveedor: str,
    prompt: str,
    img_b64: str,
    media_type: str,
    *,
    api_key: str,
    modelo: str | None = None,
    max_tokens: int = 4096,
    json_mode: bool = False,
    cliente_claude: Callable | None = None,
    cliente_openai: Callable | None = None,
    cliente_lmstudio: Callable | None = None,
    modelo_default_claude: str = "claude-sonnet-4-6",
    modelo_default_openai: str = "gpt-4o",
    modelo_default_gemini: str = "gemini-1.5-flash",
    modelo_default_ollama: str = "llava",
    host_ollama: str = "http://localhost:11434",
    timeout_ollama: int = 120,
) -> ProviderResponse:
    """Imagen (+ prompt) → texto o JSON en bruto (`json_mode=True` fuerza
    salida JSON nativa donde el proveedor lo soporta: OpenAI response_format,
    Gemini response_mime_type, Ollama format=json)."""
    if proveedor == "claude":
        if cliente_claude is None:
            raise ValueError("Proveedor 'claude' requiere cliente_claude")
        client = cliente_claude(api_key)
        msg = client.messages.create(
            model=modelo or modelo_default_claude, max_tokens=max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                {"type": "text", "text": prompt},
            ]}])
        return ProviderResponse(msg.content[0].text.strip(), usage=getattr(msg, "usage", None))

    if proveedor == "openai":
        if cliente_openai is None:
            raise ValueError("Proveedor 'openai' requiere cliente_openai")
        client = cliente_openai(api_key)
        kwargs = {"model": modelo or modelo_default_openai, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": [
                      {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_b64}"}},
                      {"type": "text", "text": prompt},
                  ]}]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return ProviderResponse(resp.choices[0].message.content.strip(), usage=getattr(resp, "usage", None))

    if proveedor == "gemini":
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError("Instala google-generativeai: pip install google-generativeai") from e
        import base64 as _b64
        import io as _io

        import PIL.Image
        genai.configure(api_key=api_key)
        model_kwargs = {}
        if json_mode:
            model_kwargs["generation_config"] = {
                "response_mime_type": "application/json", "temperature": 0.0}
        m = genai.GenerativeModel(modelo or modelo_default_gemini, **model_kwargs)
        pil_img = PIL.Image.open(_io.BytesIO(_b64.b64decode(img_b64)))
        resp = m.generate_content([prompt, pil_img])
        return ProviderResponse(resp.text.strip())

    if proveedor == "ollama":
        import requests as _req
        payload = {"model": modelo or modelo_default_ollama, "prompt": prompt,
                   "images": [img_b64], "stream": False}
        if json_mode:
            payload["format"] = "json"
        resp = _req.post(f"{host_ollama}/api/generate", json=payload, timeout=timeout_ollama)
        resp.raise_for_status()
        return ProviderResponse(resp.json().get("response", "").strip())

    if proveedor == "lmstudio":
        if cliente_lmstudio is None:
            raise ValueError("Proveedor 'lmstudio' requiere cliente_lmstudio")
        host = api_key if api_key and api_key.startswith("http") else "http://localhost:1234"
        client = cliente_lmstudio(host)
        resp = client.chat.completions.create(
            model=modelo or "local-model", max_tokens=max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ]}])
        return ProviderResponse(resp.choices[0].message.content.strip(), usage=getattr(resp, "usage", None))

    raise ValueError(f"Proveedor desconocido: {proveedor}")
