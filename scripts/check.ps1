$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$startedAt = Get-Date

function Resolve-Python {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python was not found. Create .venv or install Python before running the release check."
}

function Resolve-Node {
    if ($env:NODE_EXE -and (Test-Path $env:NODE_EXE)) {
        return $env:NODE_EXE
    }

    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCommand) {
        return $nodeCommand.Source
    }

    $localCandidates = @(
        (Join-Path $env:ProgramFiles "nodejs\node.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe"),
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe")
    )

    foreach ($candidate in $localCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Node.js was not found. Install Node.js 24+ or set NODE_EXE to node.exe."
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [scriptblock] $Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
}

Push-Location $projectRoot
try {
    $python = Resolve-Python
    $node = Resolve-Node

    Write-Host "MicroScore release check"
    Write-Host "Python: $python"
    Write-Host "Node:   $node"

    Invoke-Step "Run Python unit and integration tests" {
        & $python -m unittest discover -s tests
    }

    Invoke-Step "Check Python syntax" {
        & $python -m compileall src\microscore src\microscore_api src\train_model.py tests
    }

    Invoke-Step "Run research smoke test" {
        & $python src\train_model.py --data data\raw\credit_risk_dataset.csv --top-features 8
    }

    Invoke-Step "Run regional and decision smoke test" {
        & $python -m microscore --regional --decision --top-features 4
    }

    Invoke-Step "Check frontend JavaScript syntax" {
        & $node --check apps\web\app.js
        & $node --check apps\web\mock-api.js
        & $node --check scripts\static-demo-smoke.js
    }

    Invoke-Step "Run static demo smoke test" {
        & $node scripts\static-demo-smoke.js
    }

    Invoke-Step "Check whitespace in git diff" {
        & git diff --check
    }

    $elapsed = New-TimeSpan -Start $startedAt -End (Get-Date)
    Write-Host ""
    Write-Host ("All checks passed in {0:n1}s. Ship it carefully." -f $elapsed.TotalSeconds) -ForegroundColor Green
}
finally {
    Pop-Location
}
