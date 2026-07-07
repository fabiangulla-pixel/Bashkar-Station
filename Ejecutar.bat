@echo off
chcp 65001 >nul
title Bashkar Station

:: Moverse a la carpeta del .bat (funciona desde acceso directo)
cd /d "%~dp0"

:: Verificar Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python no encontrado en el sistema.
    echo  Descarga Python 3.9+ desde https://www.python.org/downloads/
    echo  Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

:: Primera vez: instalar dependencias
if not exist ".installed" (
    echo  Primer inicio - instalando dependencias...
    python instalar.py
    echo. > .installed
)

:: Lanzar aplicacion — si falla, mostrar error en vez de cerrar
python app.py
if %errorlevel% neq 0 (
    echo.
    echo  ============================================================
    echo   ERROR al iniciar Bashkar Station (codigo %errorlevel%)
    echo   Revisa el mensaje de error arriba.
    echo  ============================================================
    echo.
    pause
)
