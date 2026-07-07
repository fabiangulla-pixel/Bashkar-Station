# crear_acceso_directo.ps1
# Crea un acceso directo de Bashkar Station en el Escritorio.
# Ejecutar: clic derecho > "Ejecutar con PowerShell"

$nombre    = "Bashkar Station"
$carpeta   = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat       = Join-Path $carpeta "Ejecutar.bat"
$icono     = Join-Path $carpeta "bashkar_station.ico"
$escritorio = [Environment]::GetFolderPath("Desktop")
$destino   = Join-Path $escritorio "$nombre.lnk"

$wsh  = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($destino)
$link.TargetPath       = $bat
$link.WorkingDirectory = $carpeta
$link.Description      = "Bashkar Station"
if (Test-Path $icono) { $link.IconLocation = $icono }
$link.Save()

Write-Host "Acceso directo creado en: $destino"
