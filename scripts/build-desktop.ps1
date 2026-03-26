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
  $projectVenv = Join-Path $root '.venv-dev\Scripts\python.exe'
  if (Test-Path $projectVenv) {
    return $projectVenv
  }

  $candidates = @(
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

function Get-DesktopReleaseName([string]$root) {
  $packagePath = Join-Path $root 'package.json'
  $package = Get-Content -Raw $packagePath | ConvertFrom-Json
  if (-not $package.version) {
    throw "package.json does not define a version: $packagePath"
  }

  return "ChemEx-v$($package.version)-win64"
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

function Publish-DesktopRelease(
  [string]$root,
  [string]$packageDir,
  [string]$archivePath,
  [string]$releaseName
) {
  $releaseRoot = Join-Path $root 'desktop-dist-release'
  $releaseDir = Join-Path $releaseRoot $releaseName
  $releasePackageDir = Join-Path $releaseDir 'ChemEx'
  $releaseArchivePath = Join-Path $releaseRoot ($releaseName + '.7z')

  New-Item -ItemType Directory -Force $releaseRoot | Out-Null

  if (Test-Path $releaseDir) {
    Remove-Item -Recurse -Force $releaseDir -ErrorAction SilentlyContinue
  }

  New-Item -ItemType Directory -Force $releaseDir | Out-Null
  Copy-Item -Path $packageDir -Destination $releasePackageDir -Recurse -Force

  if (Test-Path $releaseArchivePath) {
    Remove-Item -Force $releaseArchivePath -ErrorAction SilentlyContinue
  }

  Copy-Item -Path $archivePath -Destination $releaseArchivePath -Force
  Write-Host "Release package published: $releasePackageDir"
  Write-Host "Release archive published: $releaseArchivePath"
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
    Remove-Item -Force $tempArchivePath -ErrorAction SilentlyContinue
  }

  Write-Host "Creating archive: $tempArchivePath"
  & $sevenZip a -t7z -mx=9 -mmt=on $tempArchivePath $packageDir
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

function Remove-DesktopBuildWorkdirs([string]$root) {
  $workdirs = @(
    (Join-Path $root 'build\desktop'),
    (Join-Path $root 'build\desktop-release'),
    (Join-Path $root 'build\desktop-work'),
    (Join-Path $root 'build\desktop-work-release')
  )

  foreach ($workdir in $workdirs) {
    if (Test-Path $workdir) {
      Remove-Item -Recurse -Force $workdir -ErrorAction SilentlyContinue
      if (Test-Path $workdir) {
        Write-Warning "Could not remove build workdir (in use?): $workdir"
      } else {
        Write-Host "Removed build workdir: $workdir"
      }
    }
  }
}

function Prune-DesktopArtifacts([string]$root, [string]$releaseName) {
  $distRoot = Join-Path $root 'desktop-dist'
  $releaseRoot = Join-Path $root 'desktop-dist-release'
  $keepReleaseDir = Join-Path $releaseRoot $releaseName
  $keepReleaseArchive = Join-Path $releaseRoot ($releaseName + '.7z')

  if (Test-Path $distRoot) {
    Remove-Item -Recurse -Force $distRoot -ErrorAction SilentlyContinue
    if (Test-Path $distRoot) {
      Write-Warning "Could not remove build artifact (in use?): $distRoot"
    } else {
      Write-Host "Removed build artifact: $distRoot"
    }
  }

  if (Test-Path $releaseRoot) {
    Get-ChildItem -Force $releaseRoot | ForEach-Object {
      if ($_.FullName -ne $keepReleaseDir -and $_.FullName -ne $keepReleaseArchive) {
        Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
        if (Test-Path $_.FullName) {
          Write-Warning "Could not remove stale release artifact (in use?): $($_.FullName)"
        } else {
          Write-Host "Removed stale release artifact: $($_.FullName)"
        }
      }
    }
  }
}

$root = Resolve-PhysicalPath $scriptRoot
$releaseName = Get-DesktopReleaseName $root
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'ChemExDesktopBuild'
$pythonUserBase = Join-Path $runtimeRoot 'pyuserbase'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
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
    & $pythonExe -m PyInstaller --noconfirm --clean --distpath desktop-dist --workpath build\desktop-work ChemEx.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with exit code $LASTEXITCODE." }
  } elseif (-not (Test-Path (Join-Path $root 'desktop-dist\ChemEx\ChemEx.exe'))) {
    throw 'ArchiveOnly mode requires an existing desktop package at desktop-dist\ChemEx\ChemEx.exe.'
  }

  Invoke-Archive $root
  Publish-DesktopRelease $root (Join-Path $root 'desktop-dist\ChemEx') (Join-Path $root 'desktop-dist\ChemEx.7z') $releaseName
  Remove-DesktopBuildWorkdirs $root
  Prune-DesktopArtifacts $root $releaseName
}
finally {
  Pop-Location
}



