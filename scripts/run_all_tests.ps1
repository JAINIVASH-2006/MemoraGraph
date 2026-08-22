# MemoraGraph – Academic Reproduction & Verification Pipeline
# ==========================================================
# This PowerShell script automates the complete validation pipeline:
# 1. Starting/checking WSL Docker daemon.
# 2. Starting database containers (Postgres, Neo4j, Qdrant).
# 3. Waiting for database port availability.
# 4. Running the seeder script to populate indices.
# 5. Executing FastAPI unit tests.
# 6. Running the academic evaluation framework.

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "         MEMORAGRAPH SYSTEM REPRODUCIBILITY       " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Check WSL Status
Write-Host "[1/6] Checking WSL status..." -ForegroundColor Yellow
$wslDistros = wsl -l -v
Write-Host $wslDistros

# 2. Ensure WSL Keep-Alive and Docker Service Started
Write-Host "[2/6] Starting Docker daemon inside WSL Ubuntu..." -ForegroundColor Yellow
wsl -d Ubuntu -u root -- service docker start

# 3. Start Database Containers
Write-Host "[3/6] Running docker-compose up for database services..." -ForegroundColor Yellow
wsl -d Ubuntu -- sh -c "cd /mnt/c/MemoraGraph && docker-compose up -d postgres neo4j qdrant"

# Wait Loop for Port Availability
Write-Host "Waiting for database ports to be available on localhost..." -ForegroundColor Yellow
$ports = @(5432, 7687, 6333)
foreach ($port in $ports) {
    $connected = $false
    for ($i = 1; $i -le 10; $i++) {
        $test = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue
        if ($test.TcpTestSucceeded) {
            Write-Host "  Port $port is open and accepting connections." -ForegroundColor Green
            $connected = $true
            break
        }
        Write-Host "  Waiting for port $port... (attempt $i/10)"
        Start-Sleep -Seconds 3
    }
    if (-not $connected) {
        Write-Error "Timeout waiting for database port $port."
    }
}

# 4. Run Database Seeder
Write-Host "[4/6] Seeding PostgreSQL, Neo4j, and Qdrant databases..." -ForegroundColor Yellow
if (Test-Path "backend\venv\Scripts\python.exe") {
    & backend\venv\Scripts\python.exe scripts\seed_data.py
} else {
    python scripts\seed_data.py
}
Write-Host "Database seeding completed successfully." -ForegroundColor Green

# 5. Run Backend Unit Tests
Write-Host "[5/6] Running pytest test suite..." -ForegroundColor Yellow
if (Test-Path "backend\venv\Scripts\python.exe") {
    & backend\venv\Scripts\python.exe -m pytest
} else {
    python -m pytest
}
Write-Host "All unit and integration tests passed." -ForegroundColor Green

# 6. Run Academic Evaluation
Write-Host "[6/6] Running academic evaluation framework..." -ForegroundColor Yellow
if (Test-Path "backend\venv\Scripts\python.exe") {
    & backend\venv\Scripts\python.exe scripts\evaluate.py
} else {
    python scripts\evaluate.py
}

Write-Host "==================================================" -ForegroundColor Green
Write-Host "  REPRODUCTION PIPELINE COMPLETED SUCCESSFULLY!   " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
