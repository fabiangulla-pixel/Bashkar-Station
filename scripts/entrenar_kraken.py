#!/usr/bin/env python
"""
scripts/entrenar_kraken.py — Afinar el reconocedor Kraken sobre el corpus propio.

Convierte las transcripciones que la investigadora ya corrigió a mano en un
modelo de OCR especializado en *su* corpus. La lógica vive en
`core/kraken_finetune.py`; esto es el guion que la ejecuta y deja constancia.

    # Ver si hoy se puede entrenar y qué falta (no toca nada):
    python scripts/entrenar_kraken.py --diagnostico

    # Preparar el dataset y entrenar:
    python scripts/entrenar_kraken.py \\
        --db       Proyecto_04_Mar_2026.db \\
        --imagenes D:/corpus/estampa/02_imagenes \\
        --salida   D:/entrenamiento/estampa

## Dos avisos que ahorran horas

**Python.** Kraken no soporta Python 3.14 (el intérprete por defecto de este
equipo). Hay un 3.12 instalado; el script lo detecta y lo dice en vez de fallar
a mitad de camino:

    C:\\Users\\Lenovo\\AppData\\Local\\Programs\\Python\\Python312\\python.exe -m venv D:/venv-kraken
    D:/venv-kraken/Scripts/pip install kraken

**Disco.** `--salida` debe estar en un disco local, nunca en I:\\ (Google Drive).
El entrenamiento relee cada línea en cada época; sobre una carpeta sincronizada
este proyecto ya midió ~6 % de lecturas fallidas en silencio, y una lectura
fallida ahí no rompe nada: solo produce un modelo peor sin decir por qué.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import kraken_finetune as kf  # noqa: E402

# La consola de Windows sigue abriendo en cp1252, que no tiene ni los filetes ni
# los ✔/✖ de este informe: sin esto el script muere con UnicodeEncodeError al
# imprimir la primera línea, y el diagnóstico no llega a verse. `replace` en vez
# de `strict` porque un carácter que no se pueda dibujar no puede tumbar un
# informe correcto.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

UNIDADES_SINCRONIZADAS = ("i:", "g:")   # Google Drive en este equipo


def _imprimir_diagnostico(d: dict) -> None:
    print("\n── Ground truth disponible " + "─" * 40)
    print(f"  Páginas con transcripción humana : {d['paginas_con_texto']}")
    print(f"  …con imagen en disco (entrenables): {d['paginas_entrenables']}")
    print(f"  …sin imagen                       : {d['paginas_sin_imagen']}")
    print(f"  Descartadas por NO ser transcripción: {d['descartadas_por_calidad']}")
    print(f"  Duplicados fusionados             : {d['duplicados_fusionados']}")
    print(f"  Caracteres                        : {d['caracteres']:,}")
    print(f"  Líneas estimadas                  : {d['lineas_estimadas']:,}")
    print(f"  Modelo base                       : {d['modelo_base'] or '— no encontrado'}")
    print(f"  ketos en el PATH                  : {'sí' if d['ketos_disponible'] else 'no'}")

    if d["se_puede_entrenar"]:
        print("\n  ✔ Se puede entrenar.")
    else:
        print("\n  ✖ Todavía no se puede entrenar. Falta:")
        for f in d["faltantes"]:
            print(f"      · {f}")


def _verificar_subcomando(subcomando: list[str]) -> tuple[bool, str]:
    """Comprueba que el subcomando existe en la versión instalada de Kraken.

    La CLI de ketos cambió entre Kraken 4 y 5. Preguntarle a la herramienta en
    vez de confiar en la documentación cuesta un segundo y evita descubrir a las
    tres horas que se entrenó con la opción equivocada.
    """
    try:
        p = subprocess.run([*subcomando, "--help"], capture_output=True,
                           text=True, timeout=60)
        return p.returncode == 0, (p.stdout or p.stderr)[:400]
    except FileNotFoundError:
        return False, f"{subcomando[0]} no está instalado o no está en el PATH."
    except subprocess.TimeoutExpired:
        return False, "El comando no respondió en 60 s."


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="Proyecto_04_Mar_2026.db",
                    help="Base del proyecto con la tabla normalizaciones")
    ap.add_argument("--imagenes", nargs="*", default=[],
                    help="Directorios donde buscar las imágenes de página")
    ap.add_argument("--salida", help="Dónde escribir dataset y modelo (disco LOCAL)")
    ap.add_argument("--modelos", default=None, help="Directorio del modelo base")
    ap.add_argument("--epocas", type=int, default=30)
    ap.add_argument("--diagnostico", action="store_true",
                    help="Solo informar qué hay y qué falta; no escribe nada")
    args = ap.parse_args()

    d = kf.diagnostico(args.db, args.imagenes, dir_modelos=args.modelos)
    _imprimir_diagnostico(d)

    if args.diagnostico:
        return 0
    if not d["se_puede_entrenar"]:
        print("\nNo se lanza el entrenamiento. Resuelve lo de arriba primero.")
        return 1
    if not args.salida:
        print("\nFalta --salida (directorio de trabajo en disco local).")
        return 2

    salida = Path(args.salida)
    if str(salida).lower()[:2] in UNIDADES_SINCRONIZADAS:
        print(f"\n✖ {salida} está en una unidad sincronizada. Usa un disco local.")
        return 2

    # 1-2. Dataset
    res = kf.emparejar_con_imagenes(kf.recolectar_ground_truth(args.db), args.imagenes)
    res = kf.exportar_dataset(res, salida / "dataset")
    print(f"\n✔ Dataset escrito en {res.destino} ({len(res.pares)} páginas)")

    # 3-6. Pasos externos, verificando la CLI antes de gastar horas
    plan = kf.plan_ketos(salida / "dataset", Path(d["modelo_base"]),
                         salida / "modelo_estampa", epocas=args.epocas)
    print("\n── Plan de entrenamiento " + "─" * 42)
    for paso in plan:
        ok, ayuda = _verificar_subcomando(paso["subcomando"])
        marca = "✔" if ok else "✖"
        print(f"\n  {marca} [{paso['etapa']}] {' '.join(paso['comando'])}")
        print(f"      {paso['por_que']}")
        if not ok:
            print(f"      ⚠ No se pudo verificar el subcomando:\n      {ayuda}")

    print("\nRevisa el plan y ejecútalo. El entrenamiento son horas: conviene "
          "lanzarlo con la máquina libre.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
