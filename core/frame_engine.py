"""frame_engine — análisis de *encuadre* (framing) de artículos de prensa.

Operacionaliza el **Media Frames Corpus** (Boydstun et al.) adaptado a prensa
histórica: clasifica cada artículo según el ÁNGULO desde el que cubre el tema,
no solo su tono. Mientras el sentimiento dice "celebratorio/crítico", el framing
dice "desde qué marco": ¿se habla en clave de *modernidad*, de *guerra*, de
*identidad nacional*, de *mujer y costumbres*, de *canon cultural*…?

Motor portado de ¡Quac! (prensa contemporánea) y **recalibrado al dominio de
Estampa (Colombia, 1930-1940)**: los marcos electorales contemporáneos se
sustituyen por los marcos temáticos pertinentes a una revista ilustrada de los
años 30 (guerra de España, modernidad/progreso, mujer y vida social, cultura y
canon literario, nación e identidad, política, ciencia y tecnología, religión y
moral, economía, internacional).

Implementación **100% local**: léxico de marcadores en español por frame (sin
API key). Si el investigador provee API key, se puede afinar con el LLM
(opcional, ``clasificar_frame_llm``), pero NO es necesario. Funciones puras
texto→dict, en línea con los demás motores de ``core/``.
"""

from __future__ import annotations

import re

# Marcos agnósticos adaptados del Media Frames Corpus al español de la prensa
# ilustrada colombiana de 1930-1940. Cada frame tiene marcadores léxicos
# (lemas/raíces) frecuentes en el corpus Estampa. Las raíces sin tilde casan con
# texto OCR que a veces pierde acentos.
FRAMES: dict[str, dict] = {
    "guerra": {
        "etiqueta": "Guerra / conflicto (Guerra Civil española, Europa)",
        "marcadores": ["guerra", "frente", "batalla", "ejércit", "ejercit",
                       "tropa", "soldad", "bombarde", "trinchera", "ofensiva",
                       "republican", "franquist", "nacionalista", "fascis",
                       "milici", "fusil", "cañón", "canon de guerra", "asedio",
                       "valencia", "madrid sitiad", "barcelona", "españa en guerra",
                       "hitler", "mussolini", "armament", "victoria militar"],
    },
    "modernidad": {
        "etiqueta": "Modernidad / progreso / vida moderna",
        "marcadores": ["modern", "progres", "civilizaci", "adelanto", "novedad",
                       "automóvil", "automovil", "aviación", "aviacion", "rascacielos",
                       "eléctric", "electric", "máquina", "maquina", "industria",
                       "velocidad", "confort", "urbe", "metrópoli", "metropoli",
                       "rascaciel", "radio", "cine", "moda nueva", "vanguardia"],
    },
    "mujer_social": {
        "etiqueta": "Mujer / vida social / costumbres",
        "marcadores": ["mujer", "dama", "señorita", "señora", "elegancia", "moda",
                       "belleza", "hogar", "matrimonio", "novia", "sociedad",
                       "salón", "salon", "baile", "fiesta", "té", "recepci",
                       "coquetería", "coqueteria", "vestido", "femenin", "tocador",
                       "cosmétic", "cosmetic", "maquillaje", "peinado"],
    },
    "cultura": {
        "etiqueta": "Cultura / arte / canon literario",
        "marcadores": ["literatura", "poesía", "poesia", "poeta", "novela",
                       "escritor", "escritora", "arte", "pintor", "pintura",
                       "música", "musica", "teatro", "obra", "libro", "letras",
                       "intelectual", "academia", "clásic", "clasic", "verso",
                       "crónica", "cronica", "ensayo", "crítica literaria",
                       "crítica de arte"],
    },
    "nacion": {
        "etiqueta": "Nación / identidad / patria",
        "marcadores": ["patria", "nacional", "naci", "colombian", "bandera",
                       "himno", "héroe", "heroe", "próceres", "proceres",
                       "independencia", "república", "republica", "pueblo",
                       "raza", "tradici", "folclor", "folklor", "tierra",
                       "región", "region", "departament", "bogotá", "bogota"],
    },
    "politica": {
        "etiqueta": "Política / gobierno / Estado",
        "marcadores": ["gobierno", "president", "ministr", "congres", "senad",
                       "cámara", "camara", "partido", "liberal", "conservador",
                       "elección", "eleccion", "elector", "política", "politica",
                       "ley", "decreto", "reforma", "estado", "oposición",
                       "oposicion", "candidat", "alcald", "gobernador"],
    },
    "ciencia": {
        "etiqueta": "Ciencia / técnica / descubrimientos",
        "marcadores": ["ciencia", "científic", "cientific", "invento", "inventor",
                       "descubrimiento", "experimento", "laboratorio", "médic",
                       "medic", "medicina", "salud", "enfermedad", "cura",
                       "ingenier", "técnic", "tecnic", "física", "fisica",
                       "química", "quimica", "astronom", "biolog"],
    },
    "religion_moral": {
        "etiqueta": "Religión / moral / valores",
        "marcadores": ["dios", "iglesia", "católic", "catolic", "cristian",
                       "fe", "religi", "moral", "pecado", "virtud", "sacerdote",
                       "obispo", "misa", "oración", "oracion", "alma", "divin",
                       "sagrad", "santidad", "decencia", "honor", "dignidad"],
    },
    "economia": {
        "etiqueta": "Economía / comercio / negocios",
        "marcadores": ["económic", "economic", "comercio", "negoci", "industria",
                       "fábrica", "fabrica", "café", "cafe", "exportaci",
                       "precio", "mercado", "banco", "dinero", "peso", "riqueza",
                       "pobreza", "trabajador", "obrer", "salario", "fortuna",
                       "capital", "inversión", "inversion"],
    },
    "internacional": {
        "etiqueta": "Internacional / mundo / extranjero",
        "marcadores": ["internacional", "extranjer", "mundo", "europa",
                       "estados unidos", "norteaméric", "norteameric", "parís",
                       "paris", "londres", "nueva york", "alemania", "italia",
                       "francia", "rusia", "soviét", "soviet", "japón", "japon",
                       "frontera", "diplomá", "diploma", "tratado", "embajad"],
    },
}


def registrar_marcos_personalizados(marcos: dict) -> None:
    """Añade/extiende frames con vocabulario del dominio del investigador.

    ``marcos``: {clave_frame: [términos...]}. Si la clave ya existe, fusiona los
    marcadores; si no, crea el frame nuevo. Permite que el investigador adapte el
    encuadre a su corpus o número concreto sin tocar el código.
    """
    for clave, terminos in (marcos or {}).items():
        if not terminos:
            continue
        if clave in FRAMES:
            existentes = set(FRAMES[clave]["marcadores"])
            FRAMES[clave]["marcadores"] = list(
                existentes | {t.lower() for t in terminos})
        else:
            FRAMES[clave] = {
                "etiqueta": clave.replace("_", " ").title(),
                "marcadores": [t.lower() for t in terminos],
            }


def _contar_marcadores(texto_low: str) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for frame, info in FRAMES.items():
        n = 0
        for m in info["marcadores"]:
            # palabra/raíz como subcadena con frontera al inicio
            n += len(re.findall(r"\b" + re.escape(m), texto_low))
        if n:
            conteo[frame] = n
    return conteo


def analizar_frame(texto: str, top_n: int = 3) -> dict:
    """Detecta los encuadres dominantes de un artículo (offline, por léxico).

    Retorna:
      {frame_dominante, etiqueta, distribucion: [{frame, etiqueta, n, porcentaje}],
       total_marcadores}
    """
    if not texto or not texto.strip():
        return {"frame_dominante": None, "etiqueta": None,
                "distribucion": [], "total_marcadores": 0}

    conteo = _contar_marcadores(texto.lower())
    total = sum(conteo.values())
    if total == 0:
        return {"frame_dominante": None, "etiqueta": None,
                "distribucion": [], "total_marcadores": 0}

    dist = sorted(
        ({"frame": f, "etiqueta": FRAMES[f]["etiqueta"], "n": n,
          "porcentaje": round(100 * n / total, 1)}
         for f, n in conteo.items()),
        key=lambda d: -d["n"])

    dom = dist[0]
    return {
        "frame_dominante": dom["frame"],
        "etiqueta": dom["etiqueta"],
        "distribucion": dist[:top_n],
        "total_marcadores": total,
    }


def analizar_corpus_frames(articulos: dict) -> dict:
    """Aplica ``analizar_frame`` a un corpus {art_id: texto} y agrega resultados.

    Retorna {por_articulo: {art_id: <frame>}, distribucion_corpus: {frame: n},
    dominante_corpus, n_articulos}. Pensado para la sección de framing del paper.
    """
    por_articulo: dict[str, dict] = {}
    distribucion: dict[str, int] = {}
    for art_id, texto in (articulos or {}).items():
        r = analizar_frame(texto)
        por_articulo[art_id] = r
        f = r.get("frame_dominante")
        if f:
            distribucion[f] = distribucion.get(f, 0) + 1

    dominante = max(distribucion, key=distribucion.get) if distribucion else None
    return {
        "por_articulo": por_articulo,
        "distribucion_corpus": dict(sorted(
            distribucion.items(), key=lambda kv: -kv[1])),
        "dominante_corpus": dominante,
        "etiqueta_dominante": FRAMES[dominante]["etiqueta"] if dominante else None,
        "n_articulos": len(por_articulo),
    }


def cruce_seccion_frame(por_articulo: dict, seccion_de: dict) -> dict:
    """Matriz sección → distribución de frames dominantes.

    ``por_articulo``: {art_id: <resultado de analizar_frame>}, o bien
    {art_id: texto_crudo} — en cuyo caso se analiza al vuelo.
    ``seccion_de``:   {art_id: nombre_seccion}
    Útil para ver qué encuadre domina cada sección de la revista.
    """
    matriz: dict[str, dict] = {}
    for art_id, r in (por_articulo or {}).items():
        seccion = (seccion_de or {}).get(art_id) or "?"
        if isinstance(r, str):
            r = analizar_frame(r)
        frame = (r or {}).get("frame_dominante") if isinstance(r, dict) else None
        if not frame:
            continue
        d = matriz.setdefault(seccion, {})
        d[frame] = d.get(frame, 0) + 1
    return matriz


def clasificar_frame_llm(texto: str, api_key: str,
                         modelo: str = "claude-haiku-4-5-20251001") -> dict | None:
    """(Opcional) Afina el frame con Claude. Solo si el investigador da API key.

    Devuelve None si la librería/clave no están; el flujo sigue con el léxico.
    """
    try:
        import anthropic
    except ImportError:
        return None
    etiquetas = "\n".join(f"- {k}: {v['etiqueta']}" for k, v in FRAMES.items())
    prompt = (
        "Clasifica el ENCUADRE periodístico dominante de este artículo de prensa "
        "ilustrada colombiana de los años 1930 en UNA de estas categorías "
        "(responde solo la clave, p. ej. 'modernidad'):\n"
        f"{etiquetas}\n\nARTÍCULO:\n{texto[:4000]}\n\nClave:")
    try:
        cli = anthropic.Anthropic(api_key=api_key)
        msg = cli.messages.create(model=modelo, max_tokens=20,
                                  messages=[{"role": "user", "content": prompt}])
        clave = msg.content[0].text.strip().lower()
        clave = re.sub(r"[^a-z_]", "", clave)
        if clave in FRAMES:
            return {"frame_dominante": clave, "etiqueta": FRAMES[clave]["etiqueta"],
                    "distribucion": [{"frame": clave,
                                      "etiqueta": FRAMES[clave]["etiqueta"],
                                      "n": 1, "porcentaje": 100.0}],
                    "total_marcadores": 1, "fuente": "llm"}
    except Exception:
        return None
    return None
