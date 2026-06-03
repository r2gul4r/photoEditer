[CmdletBinding()]
param(
  [string] $RepoZipUrl = "https://github.com/r2gul4r/photoEditer/archive/refs/heads/main.zip",
  [string] $InstallDir = (Join-Path $env:USERPROFILE "TonePilot\photoEditer"),
  [switch] $Force,
  [switch] $NoRaw,
  [switch] $Launch,
  [switch] $DryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step {
  param([string] $Message)
  Write-Host "[photo-install] $Message" -ForegroundColor Cyan
}

function Write-Ok {
  param([string] $Message)
  Write-Host "[photo-install] $Message" -ForegroundColor Green
}

function Invoke-Checked {
  param(
    [string] $Description,
    [scriptblock] $Action
  )
  if ($DryRun) {
    Write-Host "[dry-run] $Description"
    return
  }
  & $Action
}

function Test-Command {
  param([string] $Name)
  return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Refresh-Path {
  $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machinePath;$userPath"
}

function Test-NodeReady {
  if (-not (Test-Command "node")) { return $false }
  if (-not (Test-Command "npm")) { return $false }
  try {
    $major = [int](& node -p "process.versions.node.split('.')[0]")
    return $major -ge 20
  } catch {
    return $false
  }
}

function Test-PythonReady {
  $checks = @(
    @("py", "-3.12", "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"),
    @("py", "-3.11", "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"),
    @("python", "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
  )
  foreach ($check in $checks) {
    $cmd = $check[0]
    if (-not (Test-Command $cmd)) { continue }
    $args = $check[1..($check.Length - 1)]
    $previousErrorActionPreference = $ErrorActionPreference
    try {
      $ErrorActionPreference = "SilentlyContinue"
      & $cmd @args > $null 2> $null
      if ($LASTEXITCODE -eq 0) { return $true }
    } catch {
      # Treat launcher errors such as "No installed Python found" as not ready.
    } finally {
      $ErrorActionPreference = $previousErrorActionPreference
    }
  }
  return $false
}

function Install-WingetPackage {
  param(
    [string] $Id,
    [string] $Name
  )
  if ($DryRun) {
    Write-Host "[dry-run] winget install $Id"
    return
  }

  if (-not (Test-Command "winget")) {
    throw "winget is not available. Install $Name manually, then run this installer again."
  }

  Write-Step "Installing $Name with winget..."
  Invoke-Checked "winget install $Id" {
    & winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
      throw "winget failed to install $Name."
    }
  }
  Refresh-Path
}

function Ensure-SystemDependencies {
  if (Test-NodeReady) {
    Write-Ok "Node.js and npm are ready."
  } else {
    Install-WingetPackage -Id "OpenJS.NodeJS.LTS" -Name "Node.js LTS"
    if (-not $DryRun -and -not (Test-NodeReady)) {
      throw "Node.js is still unavailable. Open a new PowerShell window and rerun this installer."
    }
  }

  if (Test-PythonReady) {
    Write-Ok "Python 3.11+ is ready."
  } else {
    Install-WingetPackage -Id "Python.Python.3.12" -Name "Python 3.12"
    if (-not $DryRun -and -not (Test-PythonReady)) {
      throw "Python is still unavailable. Open a new PowerShell window and rerun this installer."
    }
  }
}

function Test-PhotoRepository {
  param([string] $Path)
  $packageJson = Join-Path $Path "package.json"
  if (-not (Test-Path $packageJson)) { return $false }

  try {
    $package = Get-Content -LiteralPath $packageJson -Raw | ConvertFrom-Json
    return $package.name -eq "tonepilot-local" -and $package.bin.photo -eq "scripts/photo.mjs"
  } catch {
    return $false
  }
}

function Install-Repository {
  if (Test-PhotoRepository -Path $InstallDir) {
    Write-Ok "Repository already exists: $InstallDir"
    return
  }

  if ((Test-Path $InstallDir) -and -not $Force) {
    throw "Install directory already exists but is not a valid photoEditer checkout: $InstallDir. Use -Force to replace it."
  }

  $parent = Split-Path -Parent $InstallDir
  $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("photoediter-install-" + [guid]::NewGuid().ToString("N"))
  $zipPath = Join-Path $tempRoot "photoEditer.zip"
  $extractDir = Join-Path $tempRoot "extract"

  Invoke-Checked "download repository zip" {
    if (Test-Path $InstallDir) {
      Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $parent, $tempRoot, $extractDir | Out-Null
    Write-Step "Downloading repository..."
    Invoke-WebRequest -UseBasicParsing -Uri $RepoZipUrl -OutFile $zipPath
    Write-Step "Extracting repository..."
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force
    $sourceDir = Get-ChildItem -LiteralPath $extractDir -Directory | Select-Object -First 1
    if (-not $sourceDir) {
      throw "Downloaded archive did not contain a repository folder."
    }
    Move-Item -LiteralPath $sourceDir.FullName -Destination $InstallDir
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
  }

  if ($DryRun) {
    Write-Host "[dry-run] repository would be installed: $InstallDir"
  } else {
    Write-Ok "Repository installed: $InstallDir"
  }
}

function Register-PhotoCommand {
  Write-Step "Registering photo command..."
  Invoke-Checked "npm link" {
    Push-Location $InstallDir
    try {
      & npm link
      if ($LASTEXITCODE -ne 0) {
        throw "npm link failed."
      }
    } finally {
      Pop-Location
    }
  }
}

function Install-ProjectDependencies {
  $args = @("scripts/photo.mjs", "install")
  if ($NoRaw) {
    $args += "--no-raw"
  }

  Write-Step "Installing project dependencies..."
  Invoke-Checked "photo install" {
    Push-Location $InstallDir
    try {
      & node @args
      if ($LASTEXITCODE -ne 0) {
        throw "photo install failed."
      }
    } finally {
      Pop-Location
    }
  }
}

function Start-PhotoDev {
  Write-Step "Starting local web app..."
  Invoke-Checked "photo dev" {
    Push-Location $InstallDir
    try {
      & node "scripts/photo.mjs" "dev"
    } finally {
      Pop-Location
    }
  }
}

Write-Step "TonePilot Local installer"
Write-Step "Install directory: $InstallDir"

Ensure-SystemDependencies
Install-Repository
Register-PhotoCommand
Install-ProjectDependencies

Write-Ok "Install complete."
Write-Host ""
Write-Host "Next command:"
Write-Host "  photo dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "If PowerShell cannot find 'photo' immediately, open a new PowerShell window and run it again."

if ($Launch) {
  Start-PhotoDev
}
