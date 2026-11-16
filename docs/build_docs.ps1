# Regenera los tres documentos PDF con los datos actuales del motor.
#   1) Presentación de la herramienta  -> Escritorio
#   2) Guía completa (personal)        -> Escritorio (LaTeX: requiere XeLaTeX/MiKTeX)
#   3) Documentación técnica           -> Escritorio y docs/ (se versiona en el repositorio)
$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
$desk = Join-Path ([Environment]::GetFolderPath("Desktop")) "RF Workbench - Documentos"
New-Item -ItemType Directory -Force $desk | Out-Null
Push-Location (Join-Path $PSScriptRoot "src")
try {
  & $py presentacion.py (Join-Path $desk "1 - Presentación RF Engineering Workbench.pdf")
  & $py guia_latex.py (Join-Path $desk "2 - Guía completa (personal).pdf")
  & $py documentacion_tecnica.py (Join-Path $desk "3 - Documentación técnica (GitHub).pdf")
  Copy-Item (Join-Path $desk "3 - Documentación técnica (GitHub).pdf") (Join-Path $PSScriptRoot "RF_Engineering_Workbench_Documentacion_Tecnica.pdf") -Force
} finally { Pop-Location }
Get-ChildItem $desk -Filter *.pdf | ForEach-Object { "{0}  ({1:N0} KB)" -f $_.Name, ($_.Length / 1KB) }
