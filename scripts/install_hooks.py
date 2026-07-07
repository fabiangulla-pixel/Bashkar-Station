"""Instala el hook de pre-commit que corre check.bat antes de cada commit.

Uso:  python scripts/install_hooks.py
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HOOK_PATH = RAIZ / ".git" / "hooks" / "pre-commit"

HOOK_CONTENIDO = """#!/bin/sh
# Pre-commit: corre check.bat (sintaxis + lint + tests) antes de cada commit.
# Instalado por scripts/install_hooks.py
# check.bat hace cd a su propia carpeta (%~dp0), asi que no dependemos de
# que cmd.exe herede el CWD de sh al spawnearlo (falla en algunas unidades).
ROOT="$(git rev-parse --show-toplevel)"
MSYS_NO_PATHCONV=1 cmd.exe /c "$ROOT/check.bat"
exit $?
"""


def main() -> None:
    if not (RAIZ / ".git").exists():
        print("[FALLO] no hay repositorio git en", RAIZ)
        raise SystemExit(1)

    HOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    HOOK_PATH.write_text(HOOK_CONTENIDO, encoding="utf-8", newline="\n")
    HOOK_PATH.chmod(0o755)
    print(f"[OK] hook instalado en {HOOK_PATH}")


if __name__ == "__main__":
    main()
