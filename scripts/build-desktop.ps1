param(
  [switch]$RebuildFrontend,
  [switch]$ArchiveOnly
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $PSScriptRoot

function Resolve-PhysicalPath([string]$path) {
  $item = Get-Item -LiteralPath $path -Force
  if ($item.PSObject.Properties.Match('Target').Count -gt 0 -and $item.Target) {
    return [string]$item.Target[0]
  }
  return $item.FullName
}

function Test-PyInstallerAvailable([string]$pythonExe) {
  try {
    & $pythonExe -m PyInstaller --version *> $null
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

function Get-PyInstallerCommand([string]$root) {
  $candidates = @(
    Join-Path $root '.venv-dev\Scripts\python.exe'
    Join-Path $root '.venv\Scripts\python.exe'
    'python'
  )

  foreach ($candidate in $candidates) {
    if (Test-PyInstallerAvailable $candidate) {
      return $candidate
    }
  }

  throw 'PyInstaller was not found. Install it into the project venv or another usable Python environment before running a full desktop build.'
}

function Get-7ZipCommand {
  $command = Get-Command 7z.exe -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }

  $candidates = @(
    'C:\Program Files\NVIDIA Corporation\NVIDIA App\7z.exe'
    'C:\Program Files\AMD\CIM\Bin64\7z.exe'
    'C:\Program Files\Gatan\7z.exe'
    'C:\Program Files\7-Zip\7z.exe'
  )

  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
      return $candidate
    }
  }

  throw '7z.exe was not found. Install 7-Zip or add it to PATH before creating the distribution archive.'
}

function Invoke-Archive([string]$root, [string]$archiveName = 'ChemEx.7z') {
  $sevenZip = Get-7ZipCommand
  $distDir = Join-Path $root 'desktop-dist'
  $packageDir = Join-Path $distDir 'ChemEx'
  $archivePath = Join-Path $distDir $archiveName
  $tempArchivePath = Join-Path $distDir ($archiveName + '.tmp')

  if (-not (Test-Path $packageDir)) {
    throw "Desktop package directory not found: $packageDir"
  }

  if (Test-Path $tempArchivePath) {
    Remove-Item -Force $tempArchivePath
  }

  Write-Host "Creating archive: $tempArchivePath"
  & $sevenZip a -t7z -mx=9 -mmt=on $tempArchivePath (Join-Path $packageDir '*')
  if ($LASTEXITCODE -ne 0) { throw "Archive build failed with exit code $LASTEXITCODE." }

  $replaced = $false
  for ($attempt = 1; $attempt -le 5; $attempt++) {
    try {
      if (Test-Path $archivePath) {
        Remove-Item -Force $archivePath -ErrorAction Stop
      }
      Move-Item -Force $tempArchivePath $archivePath -ErrorAction Stop
      $replaced = $true
      break
    } catch {
      if ($attempt -eq 5) {
        throw "Archive build succeeded, but replacing the final archive failed after 5 attempts: $($_.Exception.Message)"
      }
      Start-Sleep -Seconds 2
    }
  }

  if ($replaced) {
    Write-Host "Archive created: $archivePath"
  }
}

$root = Resolve-PhysicalPath $scriptRoot
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'ChemExDesktopBuild'
$pythonUserBase = Join-Path $runtimeRoot 'pyuserbase'
$env:PYTHONPATH = Join-Path $root 'pydeps'
$env:CHEMEX_RUNTIME_ROOT = $runtimeRoot
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONUSERBASE = $pythonUserBase

Push-Location $root
try {
  if (-not $ArchiveOnly) {
    $pythonExe = Get-PyInstallerCommand $root
    $distIndex = Join-Path $root 'dist\index.html'
    if ($RebuildFrontend -or -not (Test-Path $distIndex)) {
      cmd /d /c "set PATH=D:\Program Files\nodejs;%PATH%&& npm.cmd run build"
      if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE." }
    }

    New-Item -ItemType Directory -Force $pythonUserBase | Out-Null
    New-Item -ItemType Directory -Force $runtimeRoot | Out-Null
    & $pythonExe -m PyInstaller --noconfirm --clean --distpath desktop-dist --workpath build\desktop ChemEx.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with exit code $LASTEXITCODE." }
  } elseif (-not (Test-Path (Join-Path $root 'desktop-dist\ChemEx\ChemEx.exe'))) {
    throw 'ArchiveOnly mode requires an existing desktop package at desktop-dist\ChemEx\ChemEx.exe.'
  }

  Invoke-Archive $root
}
finally {
  Pop-Location
}
