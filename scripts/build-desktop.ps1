param([switch]$RebuildFrontend)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonExe = "python"
$env:PYTHONPATH = Join-Path $root "pydeps"
$env:CHEMEX_RUNTIME_ROOT = Join-Path $root ".desktop-runtime"
$env:PYTHONNOUSERSITE = "1"
$env:PYTHONUSERBASE = Join-Path $root ".pyuserbase"

Push-Location $root
try {
  $distIndex = Join-Path $root "dist\index.html"
  if ($RebuildFrontend -or -not (Test-Path $distIndex)) {
    cmd /d /c "set PATH=D:\Program Files\nodejs;%PATH%&& npm.cmd run build"
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE." }
  }
  New-Item -ItemType Directory -Force $env:PYTHONUSERBASE | Out-Null
  & $pythonExe -m PyInstaller --noconfirm --clean --distpath desktop-dist --workpath build\desktop ChemEx.spec
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with exit code $LASTEXITCODE." }
}
finally {
  Pop-Location
}
