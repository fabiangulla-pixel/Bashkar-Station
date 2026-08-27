"""scripts/preparar_ground_truth.py — Prepara un subconjunto piloto para el
juez de ground truth (scripts/juez_ground_truth.py): redimensiona las
imágenes ya extraídas y las empareja con su texto candidato de OCR ya hecho.

Rutas hardcodeadas a propósito para este piloto puntual de
rev_estampa_mar_1939 (imágenes en C:/build_rf/estampa_paginas, candidatos en
_prueba5/03_ocr) — generalizar a argparse cuando se prepare un segundo número.

IMPORTANTE — desplazamiento de numeración: las imágenes usan numeración "bd"
con un desplazamiento hacia la página real del PDF (ver manifiesto.json del
origen: "desplazamiento_bd_a_pdf"), mientras que la carpeta de candidatos
numera 1:1 con la página del PDF. Emparejar por nombre de archivo idéntico
mezcla páginas de contenido distinto SIN avisar — así se generó el primer
piloto (27-ago-2026), y el juez de IA lo detectó (accuracy=0.0, "texto no
corresponde a la imagen") en vez de fallar en silencio. Cualquier corpus
nuevo debe verificar su propio desplazamiento antes de correr esto.
"""
import json
import shutil
from pathlib import Path

from PIL import Image

IMG_SRC = Path("C:/build_rf/estampa_paginas/rev_estampa_mar_1939")
TXT_SRC = Path("I:/Mi unidad/00_Programas y macros/Bashkar Station/bashkar_station/_prueba5/03_ocr/rev_estampa_mar_1939")
DEST = Path("I:/Mi unidad/00_Programas y macros/Bashkar Station/bashkar_station/ground_truth_piloto/rev_estampa_mar_1939")

# Verificado contra manifiesto.json de IMG_SRC: "desplazamiento_bd_a_pdf": 41,
# "pagina_bd":"p0002"->"pagina_pdf":43.
DESPLAZAMIENTO_BD_A_PDF = 41

MAX_LADO = 1500  # suficiente para legibilidad, corta drásticamente tokens de imagen
CALIDAD_JPEG = 82


def main() -> None:
    (DEST / "imagenes").mkdir(parents=True, exist_ok=True)
    (DEST / "candidatos").mkdir(parents=True, exist_ok=True)

    pares = []
    saltadas_sin_texto = []
    saltadas_sin_palabras = []

    for img_path in sorted(IMG_SRC.glob("p*.jpeg")):
        pid = img_path.stem  # ej. p0002 (numeración "bd")
        bd_num = int(pid[1:])
        pdf_num = bd_num + DESPLAZAMIENTO_BD_A_PDF
        txt_path = TXT_SRC / f"p{pdf_num:04d}.txt"
        if not txt_path.exists():
            saltadas_sin_texto.append(pid)
            continue
        texto = txt_path.read_text(encoding="utf-8", errors="replace")
        if len(texto.split()) < 15:
            saltadas_sin_palabras.append(pid)
            continue

        im = Image.open(img_path)
        im.thumbnail((MAX_LADO, MAX_LADO), Image.LANCZOS)
        dest_img = DEST / "imagenes" / f"{pid}.jpg"
        im.convert("RGB").save(dest_img, "JPEG", quality=CALIDAD_JPEG)

        dest_txt = DEST / "candidatos" / f"{pid}.txt"
        shutil.copy2(txt_path, dest_txt)

        pares.append({
            "pagina_id": pid,
            "imagen": f"imagenes/{pid}.jpg",
            "candidato": f"candidatos/{pid}.txt",
            "palabras_candidato": len(texto.split()),
            "bytes_imagen_original": img_path.stat().st_size,
            "bytes_imagen_reducida": dest_img.stat().st_size,
        })

    manifiesto = {
        "numero": "rev_estampa_mar_1939",
        "origen_imagenes": str(IMG_SRC),
        "origen_candidatos": str(TXT_SRC),
        "desplazamiento_bd_a_pdf_aplicado": DESPLAZAMIENTO_BD_A_PDF,
        "total_paginas": len(pares),
        "saltadas_sin_texto_candidato": saltadas_sin_texto,
        "saltadas_muy_pocas_palabras": saltadas_sin_palabras,
        "paginas": pares,
    }
    (DEST / "manifiesto_piloto.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Pares listos: {len(pares)}")
    print(f"Sin texto candidato: {len(saltadas_sin_texto)} {saltadas_sin_texto}")
    print(f"Muy pocas palabras: {len(saltadas_sin_palabras)} {saltadas_sin_palabras}")
    total_mb_orig = sum(p["bytes_imagen_original"] for p in pares) / 1024 / 1024
    total_mb_red = sum(p["bytes_imagen_reducida"] for p in pares) / 1024 / 1024
    print(f"Peso imagenes: {total_mb_orig:.1f}MB -> {total_mb_red:.1f}MB")


if __name__ == "__main__":
    main()
