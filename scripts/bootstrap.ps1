param(
    [switch]$InstallDev
)

$ErrorActionPreference = "Stop"

function Remove-StaleVenv {
    if (Test-Path .venv) {
        Write-Host "Removing existing .venv ..."
        Remove-Item .venv -Recurse -Force
    }
}

function New-Venv {
    $candidates = @(
        @("python"),
        @("py", "-3.12"),
        @("py", "-3.11"),
        @("py", "-3"),
        @("python3")
    )

    foreach ($cmd in $candidates) {
        $exe = $cmd[0]
        $args = $cmd[1..($cmd.Count - 1)]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
            continue
        }
        Write-Host "Creating virtual environment with: $($cmd -join ' ')"
        & $exe @args -m venv .venv
        if ($LASTEXITCODE -eq 0 -and (Test-Path .venv/Scripts/Activate.ps1)) {
            return
        }
        Write-Warning "Failed to create venv using $($cmd -join ' ')."
        if (Test-Path .venv) {
            Remove-Item .venv -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    throw "Python 3.11+ is not installed or accessible (python, py, python3)."
}

function Assert-VenvExists {
    if (-not (Test-Path .venv/Scripts/Activate.ps1)) {
        throw "Virtual environment creation failed; '.venv\\Scripts\\Activate.ps1' not found."
    }
}

Remove-StaleVenv
New-Venv
Assert-VenvExists

$activate = Resolve-Path .venv/Scripts/Activate.ps1
Write-Host "Activating virtual environment..."
. $activate

Write-Host "Installing base dependencies..."
pip install --upgrade pip
pip install -e .

if ($InstallDev) {
    Write-Host "Installing dev dependencies..."
    pip install .[dev]
}

Write-Host "Bootstrap complete."
