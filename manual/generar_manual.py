"""manual/generar_manual.py — Compone el manual de usuario de Bashkar Station.

El manual **no se escribe a mano entero**: la referencia de los 30 paneles se
genera desde `core/guia_modulos.py`, que es la misma fuente que alimenta la
ayuda dentro de la aplicación. Así el manual no puede contradecir a la interfaz:
si se corrige una guía en el código, el manual se corrige al regenerarlo.

Lo que sí se escribe a mano son los capítulos narrativos —el marco
metodológico y los recorridos de trabajo—, en `contenido/*.md`.

Salida: un **único archivo HTML autocontenido** (estilos incrustados, sin
recursos externos) que se abre desde cualquier carpeta o memoria USB sin
conexión, y del que se obtiene el PDF con:

    python generar_manual.py --pdf

Uso:
    python manual/generar_manual.py            # solo HTML
    python manual/generar_manual.py --pdf      # HTML + PDF (necesita Chrome/Edge)
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROYECTO = RAIZ.parent
CONTENIDO = RAIZ / "contenido"
SALIDA = RAIZ / "salida"
ESTILOS = RAIZ / "estilos.css"

sys.path.insert(0, str(PROYECTO))

MARCA_REF = "{{REFERENCIA_PANELES}}"

TITULO = "Bashkar Station"
SUBTITULO = "Manual de uso y guía metodológica"
AUTOR = "Fabián Gulla"
INSTITUCION = "Instituto Caro y Cuervo · Bogotá, Colombia"


# ── Markdown ────────────────────────────────────────────────────────────────

def _md_a_html(texto: str) -> str:
    """Convierte Markdown a HTML. markdown-it-py sigue CommonMark."""
    from markdown_it import MarkdownIt
    md = MarkdownIt("commonmark", {"typographer": True})
    md.enable(["table", "strikethrough", "smartquotes", "replacements"])
    return md.render(texto)


def _slug(texto: str) -> str:
    t = re.sub(r"[^\w\s-]", "", texto.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", t).strip("-")


# ── Numeración y sumario ────────────────────────────────────────────────────

class Numerador:
    """Numera partes (I, II…) y capítulos, y recoge el sumario.

    Se hace en Python y no con contadores CSS porque el sumario tiene que
    existir como enlaces reales en el HTML: es lo que hace el documento
    navegable en pantalla, y CSS no puede generar enlaces.
    """

    ROMANOS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII"]

    def __init__(self):
        self.parte = 0
        self.capitulo = 0
        self.sumario: list[dict] = []

    def procesar(self, bloque: str) -> str:
        """Numera los h1 (partes) y h2 (capítulos) y les pone ancla."""
        def _h1(m):
            self.parte += 1
            titulo = m.group(1).strip()
            ancla = _slug(f"parte-{self.parte}-{titulo}")
            self.sumario.append({"nivel": 1, "texto": titulo, "ancla": ancla,
                                 "num": self.ROMANOS[self.parte]})
            return (f'<h1 id="{ancla}" class="parte">'
                    f'<span class="parte-num">Parte {self.ROMANOS[self.parte]}</span>'
                    f'<span class="parte-tit">{html.escape(titulo)}</span></h1>')

        def _h2(m):
            self.capitulo += 1
            titulo = m.group(1).strip()
            ancla = _slug(f"cap-{self.capitulo}-{titulo}")
            self.sumario.append({"nivel": 2, "texto": titulo, "ancla": ancla,
                                 "num": str(self.capitulo)})
            return (f'<h2 id="{ancla}" class="capitulo">'
                    f'<span class="cap-num">{self.capitulo}</span>'
                    f'{html.escape(titulo)}</h2>')

        bloque = re.sub(r"<h1>(.*?)</h1>", _h1, bloque, flags=re.S)
        bloque = re.sub(r"<h2>(.*?)</h2>", _h2, bloque, flags=re.S)
        return bloque

    def html_sumario(self) -> str:
        filas = []
        for e in self.sumario:
            if e["nivel"] == 1:
                filas.append(
                    f'<li class="sum-parte"><a href="#{e["ancla"]}">'
                    f'<span class="sum-num">Parte {e["num"]}</span>'
                    f'<span class="sum-tit">{html.escape(e["texto"])}</span></a></li>')
            else:
                filas.append(
                    f'<li class="sum-cap"><a href="#{e["ancla"]}">'
                    f'<span class="sum-num">{e["num"]}</span>'
                    f'<span class="sum-tit">{html.escape(e["texto"])}</span></a></li>')
        return "<ol class='sumario'>" + "\n".join(filas) + "</ol>"


# ── Avisos ──────────────────────────────────────────────────────────────────

# Sintaxis en los .md:   :::metodo Título opcional
#                        cuerpo
#                        :::
CLASES_AVISO = {
    "metodo": ("Nota metodológica", "metodo"),
    "aviso": ("Atención", "aviso"),
    "atajo": ("Atajo", "atajo"),
    "dato": ("Dato medido", "dato"),
}
_RE_AVISO = re.compile(r"^:::(\w+)[ \t]*(.*?)$\n(.*?)^:::[ \t]*$",
                       re.M | re.S)


def _expandir_avisos(texto: str) -> str:
    def _rep(m):
        clave, titulo, cuerpo = m.group(1), m.group(2).strip(), m.group(3)
        etiqueta, css = CLASES_AVISO.get(clave, ("Nota", "metodo"))
        cabecera = titulo or etiqueta
        return (f'<div class="aviso aviso-{css}">'
                f'<p class="aviso-tit">{html.escape(cabecera)}</p>\n'
                f'{_md_a_html(cuerpo)}</div>\n')
    return _RE_AVISO.sub(_rep, texto)


# ── Referencia de paneles, generada desde el código ──────────────────────────

GRUPOS = {
    "flujo": ("El flujo principal",
              "Los paneles que se recorren en orden para llevar un corpus "
              "desde las imágenes hasta el texto analizable."),
    "analisis": ("Análisis",
                 "Herramientas que se aplican sobre el corpus ya segmentado. "
                 "Ninguna es obligatoria: se eligen según la pregunta de "
                 "investigación."),
    "salida": ("Salida y control de calidad",
               "Lo que convierte el análisis en resultados citables, y lo que "
               "permite defender su fiabilidad."),
}


def _referencia_paneles() -> str:
    """Compone la referencia de los 30 paneles desde `core.guia_modulos`."""
    import app
    from core.guia_modulos import GUIA_MODULOS

    partes = []
    for grupo, (titulo_grupo, intro) in GRUPOS.items():
        paneles = [p for p in app.BashkarApp._PAGINAS if p[5] == grupo]
        if not paneles:
            continue
        partes.append(f'<h3 class="grupo">{html.escape(titulo_grupo)}</h3>')
        partes.append(f'<p class="grupo-intro">{html.escape(intro)}</p>')

        for pid, emoji, nombre, desc, _, _ in paneles:
            g = GUIA_MODULOS.get(pid, {})
            partes.append(f'<div class="panel" id="panel-{pid}">')
            partes.append(
                f'<h4 class="panel-tit"><span class="panel-emoji">{emoji}</span>'
                f'{html.escape(nombre)}</h4>')
            partes.append(f'<p class="panel-sub">{html.escape(desc)}</p>')
            for campo, etiqueta in (("que_es", "Qué es"),
                                    ("para_que", "Para qué sirve"),
                                    ("resultado", "Qué resultado da"),
                                    ("interpretar", "Cómo interpretarlo")):
                if g.get(campo):
                    partes.append(
                        f'<p class="panel-campo"><span class="campo-et">'
                        f'{etiqueta}</span> {html.escape(g[campo])}</p>')
            if not g:
                partes.append('<p class="panel-campo panel-sin-guia">'
                              'Sin guía detallada todavía.</p>')
            partes.append("</div>")
    return "\n".join(partes)


# ── Composición ─────────────────────────────────────────────────────────────

def _version_app() -> str:
    try:
        import app
        return app.APP_VERSION
    except Exception:                            # noqa: BLE001
        return "?"


def componer() -> str:
    if not CONTENIDO.is_dir():
        raise SystemExit(f"No existe {CONTENIDO}")

    num = Numerador()
    cuerpo: list[str] = []
    referencia_insertada = False
    for md in sorted(CONTENIDO.glob("*.md")):
        texto = md.read_text(encoding="utf-8")
        bloque = num.procesar(_md_a_html(_expandir_avisos(texto)))

        # La referencia se inyecta DESPUÉS de convertir el Markdown. El
        # marcador tiene que sobrevivir al conversor: un byte nulo no sirve
        # (CommonMark obliga a sustituir U+0000 por U+FFFD, y el reemplazo
        # posterior no encontraba nada — la referencia entera desaparecía en
        # silencio). Se usa el propio `{{...}}`, que markdown-it deja intacto
        # envuelto en un párrafo.
        if MARCA_REF in bloque:
            bloque = re.sub(rf"<p>\s*{re.escape(MARCA_REF)}\s*</p>",
                            _referencia_paneles(), bloque)
            bloque = bloque.replace(MARCA_REF, _referencia_paneles())
            referencia_insertada = True

        cuerpo.append(f'<section class="cap">{bloque}</section>')

    if not referencia_insertada:
        raise SystemExit(
            f"El marcador {MARCA_REF} no aparece en ningún archivo de "
            f"contenido/. La referencia de paneles quedaría fuera del manual.")

    estilos = ESTILOS.read_text(encoding="utf-8") if ESTILOS.exists() else ""
    hoy = date.today().strftime("%d de %B de %Y")
    meses = {"January": "enero", "February": "febrero", "March": "marzo",
             "April": "abril", "May": "mayo", "June": "junio",
             "July": "julio", "August": "agosto", "September": "septiembre",
             "October": "octubre", "November": "noviembre",
             "December": "diciembre"}
    for en, es in meses.items():
        hoy = hoy.replace(en, es)

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITULO} — {SUBTITULO}</title>
<style>{estilos}</style>
</head>
<body>

<header class="portada">
  <div class="portada-marca">⬡</div>
  <h1 class="portada-tit">{TITULO}</h1>
  <p class="portada-sub">{SUBTITULO}</p>
  <div class="portada-regla"></div>
  <p class="portada-meta">
    Versión {_version_app()} · {hoy}<br>
    {AUTOR}<br>
    {INSTITUCION}
  </p>
</header>

<nav class="sumario-pagina">
  <h2 class="sumario-tit">Sumario</h2>
  {num.html_sumario()}
</nav>

<main>
{"".join(cuerpo)}
</main>

<footer class="colofon">
  <p>Manual generado desde el código fuente de Bashkar Station.
     La referencia de paneles procede de <code>core/guia_modulos.py</code>,
     la misma fuente que alimenta la ayuda dentro de la aplicación.</p>
  <p>Bashkar Station es software libre bajo licencia Apache 2.0.<br>
     <span class="url">github.com/fabiangulla-pixel/Bashkar-Station</span></p>
</footer>

</body>
</html>
"""


def _navegador() -> str | None:
    for c in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if Path(c).exists():
            return c
    return None


def generar_pdf(html_path: Path) -> Path | None:
    """Imprime el HTML a PDF con Chrome/Edge sin abrir ventana.

    Se usa el navegador y no una librería porque respeta el CSS `@page`
    (portada sin folio, saltos controlados, cabeceras) tal como se diseñó.
    """
    nav = _navegador()
    if not nav:
        print("No se encontró Chrome ni Edge: se omite el PDF.")
        return None
    pdf = html_path.with_suffix(".pdf")
    subprocess.run([
        nav, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf}", html_path.as_uri(),
    ], check=False, capture_output=True, timeout=300)
    return pdf if pdf.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera el manual de Bashkar Station")
    ap.add_argument("--pdf", action="store_true", help="además, imprimir a PDF")
    args = ap.parse_args()

    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / "Manual_Bashkar_Station.html"
    doc = componer()

    # Comprobación de integridad: que TODOS los paneles registrados hayan
    # llegado al documento. Una vez la referencia entera desapareció sin
    # avisar por un marcador mal elegido; con esto no puede repetirse.
    import app
    faltan = [n for _, _, n, _, _, _ in app.BashkarApp._PAGINAS
              if html.escape(n) not in doc]
    if faltan:
        print(f"AVISO: {len(faltan)} panel(es) no aparecen en el manual: "
              f"{', '.join(faltan)}")
        return 1

    destino.write_text(doc, encoding="utf-8")
    kb = destino.stat().st_size / 1024
    print(f"HTML: {destino}  ({kb:.0f} KB) · "
          f"{len(app.BashkarApp._PAGINAS)} paneles documentados")

    if args.pdf:
        pdf = generar_pdf(destino)
        if pdf:
            print(f"PDF : {pdf}  ({pdf.stat().st_size/1024/1024:.2f} MB)")
        else:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
