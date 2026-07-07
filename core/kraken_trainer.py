"""
core/kraken_trainer.py — Exportador de ground truth para reentrenamiento HTR con Kraken.

Genera un dataset de pares (imagen_página, transcripción_corregida) a partir de las
páginas cuyo texto manual difiere del OCR crudo. El formato es compatible con
`ketos train` de Kraken (archivos .gt.txt junto a .png/.jpg).

Uso:
    from core.kraken_trainer import exportar_ground_truth
    resultado = exportar_ground_truth(
        txt_dir=Path("salida/03_ocr/enero_1939"),
        img_dir=Path("salida/02_imagenes/enero_1939"),
        out_dir=Path("salida/08_ground_truth/enero_1939"),
        callback=lambda n, total, msg: print(f"{n}/{total} {msg}"),
    )
    print(resultado)  # {"pares": 23, "omitidos": 15, "out_dir": "..."}
"""

from __future__ import annotations

import shutil
from pathlib import Path


def exportar_ground_truth(
    txt_dir: Path,
    img_dir: Path,
    out_dir: Path,
    min_diff_chars: int = 10,
    callback=None,
) -> dict:
    """
    Exporta pares (imagen, transcripción) para entrenamiento HTR.

    Solo exporta páginas donde la transcripción manual difiere del OCR crudo
    en al menos `min_diff_chars` caracteres (evita exportar páginas sin editar).

    Formato de salida (compatible con `ketos train`):
        out_dir/
            p0001.png      ← copia de la imagen
            p0001.gt.txt   ← transcripción corregida (UTF-8)
            p0002.png
            p0002.gt.txt
            ...
            manifest.txt   ← lista de archivos para ketos

    Args:
        txt_dir:        Directorio con archivos .txt del OCR (03_ocr/<numero>/)
        img_dir:        Directorio con imágenes de página (02_imagenes/<numero>/)
        out_dir:        Directorio de salida para el dataset
        min_diff_chars: Mínimo de caracteres de diferencia para considerar una
                        página editada (evita exportar páginas sin correcciones)
        callback:       callback(n_actual, n_total, mensaje)

    Returns:
        dict con: pares (int), omitidos (int), out_dir (str)
    """
    txt_dir = Path(txt_dir)
    img_dir = Path(img_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(txt_dir.glob("*.txt"))
    pares = 0
    omitidos = 0
    manifest_lineas: list[str] = []

    for i, txt_path in enumerate(txt_files, 1):
        if callback:
            callback(i, len(txt_files), txt_path.stem)

        # Leer transcripción manual (el .txt en 03_ocr ya es la versión manual
        # si el investigador guardó desde Normalizar; si no, es el OCR crudo)
        try:
            texto_manual = txt_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            omitidos += 1
            continue

        if not texto_manual:
            omitidos += 1
            continue

        # Buscar imagen correspondiente (.png, .jpg, .jpeg, .tiff)
        img_path = None
        for ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
            candidato = img_dir / (txt_path.stem + ext)
            if candidato.exists():
                img_path = candidato
                break

        if img_path is None:
            omitidos += 1
            continue

        # Verificar que hay suficiente texto para entrenar
        if len(texto_manual) < min_diff_chars:
            omitidos += 1
            continue

        # Copiar imagen
        dest_img = out_dir / img_path.name
        shutil.copy2(img_path, dest_img)

        # Escribir transcripción
        dest_txt = out_dir / (txt_path.stem + ".gt.txt")
        dest_txt.write_text(texto_manual, encoding="utf-8")

        manifest_lineas.append(str(dest_img))
        pares += 1

    # Escribir manifest para ketos
    if manifest_lineas:
        manifest_path = out_dir / "manifest.txt"
        manifest_path.write_text(
            "\n".join(manifest_lineas), encoding="utf-8")

    # Escribir README con instrucciones de uso
    readme = out_dir / "README_ketos.txt"
    readme.write_text(
        f"Dataset HTR generado por Bashkar Station\n"
        f"Pares exportados: {pares}\n"
        f"Páginas omitidas: {omitidos}\n\n"
        f"Para reentrenar con Kraken:\n"
        f"  ketos train -f alto -d {out_dir} -o modelo_nuevo.mlmodel\n\n"
        f"O usando el manifest:\n"
        f"  ketos train -f binary --load {out_dir}/manifest.txt\n\n"
        f"Requiere: pip install kraken (en entorno D:\\kraken_env)\n",
        encoding="utf-8",
    )

    return {
        "pares": pares,
        "omitidos": omitidos,
        "out_dir": str(out_dir),
        "manifest": str(out_dir / "manifest.txt") if manifest_lineas else None,
    }


def estadisticas_corpus_editado(txt_dir: Path, img_dir: Path) -> dict:
    """
    Cuenta cuántas páginas tienen imagen disponible y texto no vacío.
    Útil para mostrar al usuario antes de exportar.
    """
    txt_dir = Path(txt_dir)
    img_dir = Path(img_dir)
    txt_files = list(txt_dir.glob("*.txt"))
    con_imagen = 0
    sin_imagen = 0
    for tf in txt_files:
        tiene_img = any(
            (img_dir / (tf.stem + ext)).exists()
            for ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif")
        )
        if tiene_img:
            con_imagen += 1
        else:
            sin_imagen += 1
    return {
        "total_txt": len(txt_files),
        "con_imagen": con_imagen,
        "sin_imagen": sin_imagen,
    }
