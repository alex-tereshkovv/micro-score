$ErrorActionPreference = "Stop"

$python = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $python = ".venv\Scripts\python.exe"
}

Write-Host "Running unit tests..."
& $python -m unittest discover -s tests

Write-Host "Checking Python syntax..."
& $python -m compileall src\microscore src\microscore_api src\train_model.py tests

Write-Host "Running training smoke test..."
& $python src\train_model.py --data data\raw\credit_risk_dataset.csv --top-features 8

Write-Host "Running regional and decision smoke test..."
& $python -m microscore --regional --decision --top-features 4
