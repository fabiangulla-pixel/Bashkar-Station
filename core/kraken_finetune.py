"""
core/kraken_finetune.py — Adaptar el reconocedor Kraken al corpus propio.

## Por qué este módulo

La ruta CHURRO-3B transcribe *Estampa* donde Tesseract devuelve cero, pero cuesta
~12 GB de RAM y minutos por zona: es un modelo general de 3 000 millones de
parámetros al que hay que explicarle en cada página qué es una revista de 1939.
`modelos/catmus-print-fondue-large.mlmodel` pesa 22 MB y transcribe en segundos;
lo que le falta no es capacidad, es haber visto *esta* tipografía, *este* papel y
*esta* ortografía. Eso se arregla con datos, no con más parámetros.

Un modelo pequeño **especializado** puede superar a uno general enorme en el
corpus para el que se especializó, y es la práctica estándar en HTR: es lo que
hacen Transkribus y eScriptorium por dentro. El resultado es además un artefacto
citable —un modelo con su CER medido sobre un estándar de oro— y no solo una
mejora de producto.

## El hueco que este módulo tapa

`core/kraken_trainer.py` ya exportaba pares (imagen_de_página, texto_de_página).
Pero `ketos train` entrena un reconocedor **de líneas**: necesita cada línea
recortada con su transcripción. Con la página entera y su texto entero no puede
saber qué trozo de imagen corresponde a qué renglón.

El puente es la **alineación forzada**: se segmenta la página en líneas con un
modelo de layout, y luego se reparte el texto conocido entre esas líneas usando
un modelo base. De ahí salen los pares línea↔texto que sí se pueden entrenar.

## El flujo completo

    1. recolectar_ground_truth()  ← este módulo: saca el texto humano de la BD
    2. exportar_dataset()         ← este módulo: escribe imagen + texto por página
    3. kraken segment             ← líneas de cada página (ALTO/PageXML)
    4. ketos align                ← reparte el texto entre las líneas
    5. ketos train --resize union ← afina el modelo base sobre esas líneas
    6. core/benchmark_ocr.py      ← mide el CER contra el estándar de oro

Los pasos 3-5 son procesos externos: `plan_ketos()` los devuelve como datos para
que el script los ejecute y los documente en la bitácora del proyecto.

## Aviso sobre las banderas de la CLI

La interfaz de `ketos` cambió entre Kraken 4 y 5 (`align` es de la 4.2 en
adelante y sus opciones se movieron). Los comandos de `plan_ketos()` están
escritos para la serie 5.x y **el script verifica cada subcomando con `--help`
antes de lanzarlo**, en vez de darlo por bueno: es preferible parar con el texto
de ayuda delante a descubrir a las tres horas que se entrenó con la opción que
no era.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "ParEntrenamiento",
    "recolectar_ground_truth",
    "emparejar_con_imagenes",
    "exportar_dataset",
    "plan_ketos",
    "diagnostico",
    "MODELO_BASE",
    "PAGINAS_MINIMAS",
]

# El modelo que se afina. CATMUS está entrenado sobre impresos europeos de los
# siglos XV-XX: es el punto de partida más cercano a prensa hispanoamericana de
# los años treinta que hay publicado.
MODELO_BASE = "catmus-print-fondue-large.mlmodel"

# Por debajo de esto no vale la pena lanzar un entrenamiento: el modelo
# memorizaría las pocas páginas vistas en vez de aprender la tipografía. No es
# un umbral mágico, es el punto donde la literatura de HTR empieza a reportar
# mejoras estables al afinar un modelo base ya competente.
PAGINAS_MINIMAS = 20

# Una página con cuatro palabras sueltas es casi siempre un fallo de OCR que
# nadie llegó a corregir, no una página corta de verdad.
CARACTERES_MINIMOS_PAGINA = 200

# Porcentaje mínimo de caracteres (sin contar espaciado) que la transcripción
# debe cambiar respecto al OCR crudo para considerarse una corrección de verdad.
#
# El número sale de la aritmética del problema, no de una preferencia: si el OCR
# de partida fuera tan bueno que corregirlo cambia menos del 0,5 % de los
# caracteres, no habría motivo para afinar un modelo. Un ground truth real sobre
# microfilm de la BNC cambia del orden del 5-15 %.
#
# En `Proyecto_04_Mar_2026.db` las 47 páginas del número de marzo cambian el
# 0,035 % de media: son OCR reformateado, no transcripción. Sin este umbral, el
# entrenamiento habría corrido durante horas sobre datos que solo pueden
# empeorar el modelo, y sin nada en pantalla que lo advirtiera.
CORRECCION_MINIMA_PCT = 0.5


@dataclass
class ParEntrenamiento:
    """Una página con transcripción humana, lista para alinear."""
    numero: str
    pagina: str
    texto: str
    imagen: Path | None = None

    @property
    def clave(self) -> str:
        """Identidad de la página, independiente de cómo se llamara el número."""
        return f"{_normalizar_numero(self.numero)}/{self.pagina}"

    @property
    def caracteres(self) -> int:
        return len(self.texto)


@dataclass
class ResultadoDataset:
    pares: list[ParEntrenamiento] = field(default_factory=list)
    sin_imagen: list[ParEntrenamiento] = field(default_factory=list)
    descartados_cortos: int = 0
    descartados_solo_reformateo: int = 0
    descartados_correccion_trivial: int = 0
    correccion_media_descartada: list[float] = field(default_factory=list)
    duplicados_fusionados: int = 0
    caracteres: int = 0
    destino: Path | None = None

    @property
    def suficiente(self) -> bool:
        return len(self.pares) >= PAGINAS_MINIMAS


def _esqueleto(texto: str) -> str:
    """El texto sin espaciado ni guiones de corte de línea.

    Sirve para responder «¿esto se corrigió de verdad o solo se reformateó?».
    Dos textos con el mismo esqueleto dicen exactamente los mismos caracteres.

    El guion de corte se elimina seguido de **cualquier** espacio, no solo de un
    salto de línea: quien desenvuelve renglones cambiando `\\n` por un espacio
    deja `- ` en medio de la palabra, y quien los borra a mano no deja nada. Las
    dos cosas son reformateo, y si el esqueleto no las igualara, la diferencia
    entre convenciones se contaría como si fuera corrección de texto.
    """
    return re.sub(r"\s+", "", re.sub(r"-\s+", "", texto or ""))


def porcentaje_corregido(crudo: str, humano: str) -> float:
    """Cuánto se corrigió de verdad, en % de caracteres, ignorando el espaciado.

    Se compara sobre los esqueletos para que reformatear no cuente como corregir.
    """
    import difflib

    a, b = _esqueleto(crudo), _esqueleto(humano)
    if not a and not b:
        return 0.0
    if not a or not b:
        return 100.0
    return (1.0 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()) * 100.0


def _solo_reformateo(crudo: str, humano: str) -> bool:
    """True si el único cambio fue juntar renglones y quitar espacios.

    **Esta es la comprobación más importante del módulo.** La pantalla de
    normalización de Bashkar precarga el OCR y desenvuelve los renglones; si la
    investigadora guarda sin corregir caracteres, queda un registro que *parece*
    transcripción —difiere del crudo, tiene miles de caracteres— y no lo es.

    Medido sobre `Proyecto_04_Mar_2026.db` el 2026-08-10: las 47 páginas del
    número de marzo pasan el filtro ingenuo de «difiere del crudo», pero el
    cambio real fuera del espaciado es del **0,035 % de los caracteres** —
    guiones sobrantes de unir renglones. El OCR de la BNC sigue entero, con
    «Rila» por «Rifa» incluido.

    Entrenar un reconocedor contra eso le enseña los errores del OCR de origen:
    el modelo no puede salir mejor que sus objetivos. Y para HTR es doblemente
    inservible, porque al desenvolver los renglones se destruye la estructura de
    líneas que la alineación forzada necesita.
    """
    return _esqueleto(crudo) == _esqueleto(humano)


def _normalizar_numero(numero: str) -> str:
    """Reduce las variantes del nombre de un número a una sola clave.

    Hace falta porque la misma entrega aparece en la base con tres nombres
    distintos según por qué pantalla entró —"Estampa año 2-2(17)_18 de marzo de
    1939", el mismo con prefijo "Completo_", y una versión con guiones bajos y
    sin paréntesis—. Contarlos como tres corpus distintos inflaría por cuatro el
    tamaño aparente del ground truth, y entrenar con la misma página repetida
    cuatro veces la sobrepondera sin aportar ni un ejemplo nuevo.
    """
    txt = unicodedata.normalize("NFKD", numero or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower()
    txt = re.sub(r"^completo[_\s-]+", "", txt)
    txt = re.sub(r"[^a-z0-9]+", "", txt)
    return txt


def recolectar_ground_truth(
    db_path,
    caracteres_minimos: int = CARACTERES_MINIMOS_PAGINA,
) -> ResultadoDataset:
    """Extrae de la base del proyecto las páginas con transcripción humana.

    Lee `normalizaciones`, que guarda `ocr_crudo` y `norm_usuario` por página.
    Solo sirve lo que la investigadora tocó de verdad: si `norm_usuario` es
    idéntico al OCR crudo, nadie lo corrigió y entrenar con eso le enseñaría al
    modelo justo los errores que se quieren eliminar.

    Ante duplicados de la misma página se queda con la transcripción **más
    larga**: corregir es casi siempre añadir (lo que el OCR se comió), así que la
    versión más larga es la más trabajada.
    """
    resultado = ResultadoDataset()
    con = sqlite3.connect(str(db_path))
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        filas = con.execute(
            "SELECT numero, pagina, ocr_crudo, norm_usuario FROM normalizaciones"
        ).fetchall()
    except sqlite3.Error:
        return resultado          # base sin la tabla: proyecto vacío, no un error
    finally:
        con.close()

    mejores: dict[str, ParEntrenamiento] = {}
    vistos = 0
    for numero, pagina, crudo, humano in filas:
        texto = (humano or "").strip()
        if not texto:
            continue
        if texto == (crudo or "").strip():
            continue              # copia sin editar del OCR: no es ground truth
        if _solo_reformateo(crudo or "", texto):
            resultado.descartados_solo_reformateo += 1
            continue              # se desenvolvieron renglones, no se corrigió nada
        pct = porcentaje_corregido(crudo or "", texto)
        if pct < CORRECCION_MINIMA_PCT:
            resultado.descartados_correccion_trivial += 1
            resultado.correccion_media_descartada.append(pct)
            continue              # unos guiones sueltos no son una transcripción
        if len(texto) < caracteres_minimos:
            resultado.descartados_cortos += 1
            continue

        par = ParEntrenamiento(numero=numero or "", pagina=pagina or "", texto=texto)
        vistos += 1
        previo = mejores.get(par.clave)
        if previo is None or len(texto) > len(previo.texto):
            mejores[par.clave] = par

    resultado.pares = sorted(mejores.values(), key=lambda p: p.clave)
    resultado.duplicados_fusionados = vistos - len(resultado.pares)
    resultado.caracteres = sum(p.caracteres for p in resultado.pares)
    return resultado


def emparejar_con_imagenes(
    resultado: ResultadoDataset,
    dirs_imagenes: list[Path] | tuple[Path, ...],
) -> ResultadoDataset:
    """Busca la imagen de cada página entre los directorios dados.

    Sin imagen no hay par entrenable, y las imágenes de página no viven en la
    base: Bashkar las rerenderiza del PDF cuando hacen falta. Las páginas sin
    imagen no se descartan en silencio — van a `sin_imagen` para que el informe
    pueda decir exactamente qué falta rerenderizar.
    """
    indice: dict[str, Path] = {}
    for d in dirs_imagenes:
        d = Path(d)
        if not d.is_dir():
            continue
        for img in d.rglob("*"):
            if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
                indice.setdefault(img.stem.lower(), img)

    con_imagen, sin_imagen = [], []
    for par in resultado.pares:
        img = indice.get(par.pagina.lower())
        if img is None:
            sin_imagen.append(par)
        else:
            par.imagen = img
            con_imagen.append(par)

    resultado.pares = con_imagen
    resultado.sin_imagen = sin_imagen
    return resultado


def exportar_dataset(resultado: ResultadoDataset, destino) -> ResultadoDataset:
    """Escribe el dataset en disco: una imagen y un .gt.txt por página.

    El destino **debe estar en un disco local**. Google Drive sincroniza mientras
    se lee y en este proyecto ya costó un 6 % de lecturas fallidas en silencio
    sobre corpus grandes; un entrenamiento que lee cada página en cada época lo
    dispararía, y un error silencioso ahí no rompe nada: solo produce un modelo
    peor sin decir por qué.
    """
    import shutil

    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    for par in resultado.pares:
        if par.imagen is None:
            continue
        base = destino / f"{_normalizar_numero(par.numero)[:40]}_{par.pagina}"
        shutil.copy2(par.imagen, base.with_suffix(par.imagen.suffix))
        base.with_suffix(".gt.txt").write_text(par.texto, encoding="utf-8")

    resultado.destino = destino
    return resultado


def plan_ketos(
    dataset: Path,
    modelo_base: Path,
    salida: Path,
    epocas: int = 30,
) -> list[dict]:
    """Devuelve los pasos externos del entrenamiento, como datos.

    Se devuelven en vez de ejecutarse para que el script los pueda verificar
    contra la ayuda de la versión instalada, mostrarlos antes de lanzar un
    proceso de horas, y registrarlos en la bitácora del proyecto: un modelo cuyo
    entrenamiento no se puede reproducir no sirve para publicar.
    """
    dataset, modelo_base, salida = Path(dataset), Path(modelo_base), Path(salida)
    return [
        {
            "etapa": "segmentar",
            "subcomando": ["kraken", "segment"],
            "comando": ["kraken", "-a", "-i", "PAGINA.png", "PAGINA.xml",
                        "segment", "-bl"],
            "por_cada_pagina": True,
            "por_que": (
                "Detecta las líneas de texto y escribe sus coordenadas en ALTO. "
                "Es lo que convierte una página en unidades entrenables."
            ),
        },
        {
            "etapa": "alinear",
            "subcomando": ["ketos", "align"],
            "comando": ["ketos", "align", "-i", str(modelo_base),
                        "--format-type", "alto", "-o", "PAGINA.aligned.xml",
                        "PAGINA.xml"],
            "por_cada_pagina": True,
            "por_que": (
                "Alineación forzada: reparte la transcripción humana entre las "
                "líneas detectadas. Es el paso que faltaba para poder entrenar "
                "con transcripciones hechas a nivel de página."
            ),
        },
        {
            "etapa": "entrenar",
            "subcomando": ["ketos", "train"],
            "comando": ["ketos", "train", "-i", str(modelo_base),
                        "--resize", "union", "-f", "alto",
                        "-o", str(salida), "-N", str(epocas),
                        f"{dataset}/*.aligned.xml"],
            "por_cada_pagina": False,
            "por_que": (
                "Afina el modelo base en vez de entrenar desde cero: con unos "
                "miles de líneas, partir de cero daría un modelo peor que el "
                "base. `--resize union` conserva el alfabeto del modelo original "
                "y le añade los caracteres nuevos del corpus, en lugar de "
                "reemplazarlo y perder lo ya aprendido."
            ),
        },
        {
            "etapa": "medir",
            "subcomando": ["ketos", "test"],
            "comando": ["ketos", "test", "-m", f"{salida}_best.mlmodel",
                        "-f", "alto", f"{dataset}/*.aligned.xml"],
            "por_cada_pagina": False,
            "por_que": (
                "CER del modelo afinado. Para la comparación que importa —contra "
                "CHURRO y Tesseract sobre el estándar de oro— se usa "
                "core/benchmark_ocr.py, que mide las tres rutas igual."
            ),
        },
    ]


def diagnostico(db_path, dirs_imagenes, dir_modelos=None) -> dict:
    """Comprueba si hoy se puede entrenar, y si no, qué falta exactamente.

    Pensado para responder de un vistazo antes de invertir horas: cuántas
    páginas de ground truth hay, cuántas tienen imagen, si está el modelo base y
    si `ketos` existe en el PATH.
    """
    import shutil as _shutil

    res = recolectar_ground_truth(db_path)
    res = emparejar_con_imagenes(res, list(dirs_imagenes))

    dir_modelos = Path(dir_modelos) if dir_modelos else Path(__file__).parent.parent / "modelos"
    modelo = dir_modelos / MODELO_BASE
    if not modelo.exists():
        candidatos = list(dir_modelos.glob("*.mlmodel")) if dir_modelos.is_dir() else []
        modelo = candidatos[0] if candidatos else None

    faltantes = []
    descartadas_por_calidad = res.descartados_solo_reformateo + res.descartados_correccion_trivial
    if descartadas_por_calidad:
        media = (sum(res.correccion_media_descartada) / len(res.correccion_media_descartada)
                 if res.correccion_media_descartada else 0.0)
        faltantes.append(
            f"Transcripción de verdad: {descartadas_por_calidad} páginas se "
            f"descartaron porque no son ground truth — es el OCR con los "
            f"renglones desenvueltos (cambio real medio: {media:.3f} % de los "
            f"caracteres). Entrenar con eso le enseña al modelo los errores del "
            f"OCR de origen. Hay que transcribir a mano con el flujo de "
            f"core/estandar_oro.py."
        )
    if not res.pares and not descartadas_por_calidad:
        faltantes.append(
            f"Imágenes de página: hay {len(res.sin_imagen)} páginas transcritas "
            f"pero ninguna con su imagen en disco. Hay que rerenderizarlas desde "
            f"los PDF originales del corpus."
        )
    elif not res.pares:
        pass          # ya está dicho arriba: el problema es la calidad, no el conteo
    elif not res.suficiente:
        faltantes.append(
            f"Más ground truth: {len(res.pares)} páginas con imagen y texto, "
            f"hacen falta al menos {PAGINAS_MINIMAS}."
        )
    if modelo is None:
        faltantes.append(f"Modelo base: no hay ningún .mlmodel en {dir_modelos}")
    if _shutil.which("ketos") is None:
        faltantes.append(
            "Kraken: `ketos` no está en el PATH. Kraken no soporta Python 3.14; "
            "instálalo en un entorno de Python 3.12."
        )

    return {
        "paginas_con_texto": len(res.pares) + len(res.sin_imagen),
        "paginas_entrenables": len(res.pares),
        "paginas_sin_imagen": len(res.sin_imagen),
        "descartadas_por_calidad": descartadas_por_calidad,
        "caracteres": res.caracteres,
        "duplicados_fusionados": res.duplicados_fusionados,
        "lineas_estimadas": res.caracteres // 45,   # ~45 caracteres por renglón
        "modelo_base": str(modelo) if modelo else None,
        "ketos_disponible": _shutil.which("ketos") is not None,
        "se_puede_entrenar": not faltantes,
        "faltantes": faltantes,
    }
