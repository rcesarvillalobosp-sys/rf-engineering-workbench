# Publica una versión: pruebas -> interfaz -> motor -> instalador -> GitHub Releases (repo público) -> etiqueta en el repo de código.
# Uso:
#   npm version patch --no-git-tag-version   (o minor / major)
#   git commit -am "Versión X.Y.Z"
#   npm run release
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$ver = (Get-Content package.json -Raw | ConvertFrom-Json).version
$tag = "v$ver"
$releasesRepo = "rcesarvillalobosp-sys/rf-engineering-workbench-releases"
Write-Host "== Publicando RF Engineering Workbench $tag ==" -ForegroundColor Green

if (git status --porcelain) { throw "Hay cambios sin confirmar. Haga commit antes de publicar." }
if ((git rev-parse --abbrev-ref HEAD) -ne "main") { throw "Publique desde la rama main." }
gh release view $tag --repo $releasesRepo *> $null
if ($LASTEXITCODE -eq 0) { throw "La versión $tag ya está publicada. Suba la versión con: npm version patch --no-git-tag-version" }

Write-Host "-- Pruebas del motor" -ForegroundColor Cyan
& backend\.venv\Scripts\python.exe -m pytest backend/tests -q
if ($LASTEXITCODE -ne 0) { throw "Las pruebas fallaron: no se publica." }

Write-Host "-- Interfaz" -ForegroundColor Cyan
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw "Fallo al compilar la interfaz." }

Write-Host "-- Motor (PyInstaller + prueba de humo)" -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_engine.ps1
if ($LASTEXITCODE -ne 0) { throw "Fallo al compilar el motor." }

Write-Host "-- Instalador y publicación" -ForegroundColor Cyan
$env:GH_TOKEN = (gh auth token)
npx electron-builder --win nsis --publish always
if ($LASTEXITCODE -ne 0) { throw "Fallo al generar o publicar el instalador." }
Remove-Item Env:GH_TOKEN

git tag -a $tag -m "Versión $ver"
git push origin main --follow-tags
Write-Host "== $tag publicada: https://github.com/$releasesRepo/releases/tag/$tag ==" -ForegroundColor Green
