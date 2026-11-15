# Compila el motor RF (Python) a un ejecutable autónomo con PyInstaller -> build\engine-dist\rfwb-engine
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$py = "backend\.venv\Scripts\python.exe"
& $py -m PyInstaller --noconfirm --clean --name rfwb-engine --console `
  --distpath build\engine-dist --workpath build\pyi-work --specpath build `
  --paths backend --collect-submodules rfwb --collect-submodules numpy --collect-data skrf `
  --collect-submodules uvicorn --hidden-import matplotlib.backends.backend_agg `
  --exclude-module tkinter --exclude-module PyQt5 --exclude-module PySide6 --exclude-module IPython --exclude-module pytest `
  backend\run_engine.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló ($LASTEXITCODE)" }
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts\smoke_engine.ps1
