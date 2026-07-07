@echo off
REM check.bat - CI local para Bashkar Station
REM Corre: sintaxis (py_compile) + lint (ruff) + tests (pytest)
REM Uso: check.bat

setlocal enabledelayedexpansion
cd /d "%~dp0"
set FALLO=0

echo ============================================================
echo  1/3  py_compile app.py
echo ============================================================
python -m py_compile app.py
if errorlevel 1 (
    echo [FALLO] app.py no compila
    set FALLO=1
) else (
    echo [OK] app.py compila
)

echo.
echo ============================================================
echo  2/3  ruff check
echo ============================================================
python -m ruff check .
if errorlevel 1 (
    echo [FALLO] ruff encontro problemas
    set FALLO=1
) else (
    echo [OK] ruff sin hallazgos
)

echo.
echo ============================================================
echo  3/3  pytest
echo ============================================================
python -m pytest -q
if errorlevel 1 (
    echo [FALLO] hay tests en rojo
    set FALLO=1
) else (
    echo [OK] suite en verde
)

echo.
echo ============================================================
if "%FALLO%"=="1" (
    echo [FALLO] check.bat termino con errores
    exit /b 1
) else (
    echo [OK] check.bat: todo en verde
    exit /b 0
)
