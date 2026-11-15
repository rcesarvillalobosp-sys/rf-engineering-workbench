# Prueba de humo del motor empaquetado: arranque, autoverificación, UI, Touchstone+skrf, adaptación, PDF y SQLite.
param([string]$Exe = "build\engine-dist\rfwb-engine\rfwb-engine.exe", [int]$Port = 47699)
$ErrorActionPreference = "Stop"
$data = Join-Path $env:TEMP "rfwb-smoke-$Port"; Remove-Item -Recurse -Force $data -ErrorAction SilentlyContinue
$env:RFWB_DATA_DIR = $data
if (-not $env:RFWB_UI_DIST) { $env:RFWB_UI_DIST = (Resolve-Path "frontend\dist").Path }
$err = Join-Path $env:TEMP "rfwb-smoke-err.txt"
$p = Start-Process $Exe -ArgumentList "--port $Port" -PassThru -WindowStyle Hidden -RedirectStandardError $err
$base = "http://127.0.0.1:$Port"
try {
  $h = $null
  for ($i = 0; $i -lt 90 -and -not $h; $i++) { Start-Sleep -Milliseconds 500; try { $h = Invoke-RestMethod "$base/api/health" -TimeoutSec 1 } catch {} ; if ($p.HasExited) { break } }
  if (-not $h) { throw "El motor no arrancó: $(Get-Content $err -Tail 8 | Out-String)" }
  "health      : ok (skrf $($h.skrf))"
  $st = Invoke-RestMethod "$base/api/selftest"; "selftest    : $($st.passed)/$($st.total)"
  "ui          : $((Invoke-WebRequest -UseBasicParsing "$base/").Content -match 'RF Engineering Workbench')"
  $ts = Invoke-RestMethod -Method Post "$base/api/touchstone/parse" -ContentType 'application/json' -Body (@{ filename = 'a.s1p'; text = "# MHz S RI R 50`n100 0.1 0.2`n200 0.3 -0.1`n" } | ConvertTo-Json)
  "touchstone  : skrf ok = $($ts.skrf_check.ok)"
  $m = Invoke-RestMethod -Method Post "$base/api/match/design" -ContentType 'application/json' -Body (@{ method = 'STUB2'; zl = '60-j80'; zs = '50'; f0 = '2GHz'; d1_lambda = 0 } | ConvertTo-Json)
  "matching    : $($m.solutions.Count) soluciones, VSWR $($m.solutions[0].vswr_after)"
  $rep = @{ title = 't'; items = @(@{ title = 'Γ Ω ∠'; module = 'x'; origin = 'calculated'; results = @(, @('Γ', '0.3 ∠ 32°')); smith = @{ z0 = 50; points = @(); traces = @() }; plots = @(@{ title = 'p'; ylabel = 'dB'; x = @(1e9, 2e9); series = @(@{ name = 's'; y = @(-10, -90) }) }) }) } | ConvertTo-Json -Depth 8
  $pdf = Join-Path $env:TEMP "rfwb-smoke.pdf"
  Invoke-WebRequest -UseBasicParsing -Method Post "$base/api/reports/pdf" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($rep)) -OutFile $pdf
  $txt = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($pdf))
  "pdf         : $((Get-Item $pdf).Length) bytes, DejaVu embebida = $($txt -match 'DejaVu')"
  $lib = Invoke-RestMethod "$base/api/library?category=coax"
  "sqlite      : $(Test-Path (Join-Path $data 'workbench.sqlite3')), $($lib.items.Count) cables genéricos"
} finally {
  if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
}
