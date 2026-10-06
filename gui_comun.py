"""gui_comun.py — Lo que comparten app.py y los paneles de la GUI.

Antes (sesión 71, primera tanda) los paneles recibían estos nombres por
``paneles.sincronizar(globals())``: funcionaba, pero ningún analizador podía
comprobarlo y un panel no podía importar de ``app`` (ejecutado como
``python app.py`` el módulo se llama ``__main__`` y ``import app`` crearía
una SEGUNDA copia, con otro ``ST``). Aquí viven una sola vez y se importan
explícitamente.

Los colores del tema cambian en caliente (modo claro/oscuro), así que no se
exportan como constantes sino a través del objeto ``TEMA``:
``TEMA.CONTENT_BG``. ``app._aplicar_paleta`` lo actualiza.
"""

from __future__ import annotations

from ui_redesign import Theme as _T

APP_VERSION = "13.0"


class _Tema:
    """Paleta activa. Atributos: CONTENT_BG, CARD_BG, TXT_PRI… (los de
    ``_PALETA_DARK`` de app.py). Se leen en cada uso, así que un cambio de
    tema llega a todo el código que los consulta."""

    def actualizar(self, paleta: dict) -> None:
        self.__dict__.update(paleta)

    def __getattr__(self, nombre):
        raise AttributeError(f"el tema no define el color {nombre!r} "
                             "(¿falta en _PALETA_DARK/_PALETA_LIGHT de app.py?)")


TEMA = _Tema()


# Símbolo por capa vigente de una página en el panel Normalizar. La lista
# distingue lo que revisó una persona de lo que solo corrigió una máquina.
_SIMBOLOS_ESTADO_NORM = {"revisado": "✓", "corregido_ia": "◐", "ocr": "○",
                         "sin_datos": "·"}


def _simbolo_estado_norm(bloque: dict) -> str:
    from datos.normalizaciones import estado_epistemico
    return _SIMBOLOS_ESTADO_NORM[estado_epistemico(bloque)]


def _registrar_error(mensaje: str, exc: BaseException | None = None) -> None:
    from core.registro_errores import registrar
    registrar(mensaje, exc)


def _autor_local() -> str:
    """Nombre de la cuenta local, para firmar las revisiones humanas."""
    try:
        import getpass
        return getpass.getuser() or "investigador"
    except Exception:
        return "investigador"


# Serie categórica para gráficos: cobre, teal, azul, verde, púrpura, ámbar…
PALETTE=[_T.COPPER, _T.TEAL, _T.BLUE, _T.GREEN, _T.PURPLE, _T.AMBER,
         _T.COPPER_2, _T.RED]

COLABS_DEFAULT = ("Jorge Zalamea\nLeón de Greiff\nGermán Arciniegas\n"
                  "Eduardo Carranza\nHernando Téllez\nLeo Matiz\n"
                  "Gilberto Owen\nFernando Martínez")

CAMPOS_DEFAULT = {
    "Nación":      ["colombia","colombiano","patria","nación","nacional","bogotá","república","gobierno","pueblo"],
    "Modernidad":  ["moderno","modernidad","progreso","técnica","industrial","máquina","radio","cine","automóvil","avión"],
    "Género":      ["mujer","mujeres","femenino","familia","hogar","moda","maternidad","belleza","matrimonio"],
    "Ciudad":      ["ciudad","urbano","calle","barrio","edificio","capital","plaza","parque","comercio"],
    "Guerra/Eur.": ["guerra","europa","español","alemania","fascismo","exilio","refugiado","francia","nazismo"],
    "Cultura":     ["literatura","arte","poesía","novela","música","teatro","escritor","artista","libro"],
}


# Estado de la sesión de la GUI. La clase vive en core/estado.py (fuente única
# compartida con servidor_web.py); aquí se instancia el singleton.
from core.estado import Estado  # noqa: E402

ST = Estado()


# El OCR por visión vive ENTERO en core/ocr_llm.py. Aquí hubo durante mucho
# tiempo una copia propia, `_ocr_vision_multiproveedor`, que la Ruta 2 de la
# GUI llamaba en vez de la de core: sin el prompt calibrado contra las 46
# páginas del juez de ground truth, sin registrar el gasto de IA, sin filtrar
# los rechazos del modelo, sin lmstudio y devolviendo "" en silencio ante un
# proveedor desconocido. Eliminada: `tests/test_ocr_vision_sin_duplicado.py`
# impide que vuelva.
_MODELO_VISION_DEFECTO = "claude-sonnet-4-6"


def _resolver_api_key_modelo(etapa: str) -> tuple[str, str]:
    """
    Devuelve (api_key, modelo_id) para la etapa indicada.
    Retorna ("", "") si ST.ia_habilitada es False (modo offline).

    Lógica:
    1. Si ST.ia_habilitada es False → retorna ("", "") para bloquear cualquier llamada a API
    2. Lee ST.modelos_etapa[etapa] → "proveedor/modelo"
    3. Busca la api_key en ST.api_keys[proveedor]
    4. Si no hay clave específica, cae a ST.api_key (legado)
    """
    if not getattr(ST, "ia_habilitada", False):
        return "", ""

    modelo_full = ST.modelos_etapa.get(etapa, "")
    if "/" in modelo_full:
        proveedor, modelo_id = modelo_full.split("/", 1)
    else:
        proveedor, modelo_id = "anthropic", modelo_full

    # Ollama no necesita API key — devuelve la URL del servidor como "key"
    if proveedor == "ollama":
        api_key = ST.api_keys.get("ollama", "http://localhost:11434").strip()
        return api_key or "http://localhost:11434", modelo_id

    api_key = ST.api_keys.get(proveedor, "").strip()
    if not api_key:
        api_key = ST.api_key  # fallback legado

    return api_key, modelo_id
