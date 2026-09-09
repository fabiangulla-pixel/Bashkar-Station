@echo off
REM check.bat - CI local para Bashkar Station
REM Corre: sintaxis (py_compile) + lint (ruff) + tests (pytest)
REM Uso: check.bat

setlocal enabledelayedexpansion
cd /d "%~dp0"
set FALLO=0

REM ---------------------------------------------------------------
REM Elegir interprete. NUNCA "python" a secas: el hook pre-commit
REM corre este .bat desde cmd.exe, que no hereda el entorno de un
REM venv activado en otra consola, y en un equipo con varios Python
REM instalados "python" puede ser uno sin dependencias. Ese fallo se
REM ve como "hay tests en rojo" cuando en realidad no se corrio nada.
REM Prioridad: BASHKAR_PYTHON > venv activo > .venv/venv del repo > PATH.
REM ---------------------------------------------------------------
set "PY="
if defined BASHKAR_PYTHON if exist "%BASHKAR_PYTHON%" set "PY=%BASHKAR_PYTHON%"
if not defined PY if defined VIRTUAL_ENV if exist "%VIRTUAL_ENV%\Scripts\python.exe" set "PY=%VIRTUAL_ENV%\Scripts\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY set "PY=python"

echo Interprete: %PY%
"%PY%" -c "import sys; print('Python', sys.version.split()[0])"
if errorlevel 1 (
    echo [FALLO] el interprete %PY% no arranca
    exit /b 1
)

REM Herramientas de desarrollo ausentes: es un entorno mal montado,
REM no codigo roto. Se distingue para no confundir los dos casos.
"%PY%" -c "import pytest, ruff" 2>nul
if errorlevel 1 (
    echo [FALLO] a este interprete le faltan pytest y/o ruff.
    echo         Instala las dependencias de desarrollo:
    echo             "%PY%" -m pip install -r requirements-dev.txt
    echo         O apunta BASHKAR_PYTHON al python del venv del proyecto.
    exit /b 1
)

echo.
echo ============================================================
echo  1/3  py_compile app.py
echo ============================================================
"%PY%" -m py_compile app.py
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
"%PY%" -m ruff check .
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
"%PY%" -m pytest -q
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
