# test_failclosed.ps1 — Phase 5 Network Isolation Verification
# Run from ClawGlove repo root: .\scripts\test_failclosed.ps1

$ErrorActionPreference = "Stop"
$PASS  = "[PASS]"
$FAIL  = "[FAIL]"
$INFO  = "[INFO]"
$TOTAL_PASS = 0
$TOTAL_FAIL = 0

function Write-Pass($msg) { Write-Host "  $PASS $msg" -ForegroundColor Green;  $script:TOTAL_PASS++ }
function Write-Fail($msg) { Write-Host "  $FAIL $msg" -ForegroundColor Red;    $script:TOTAL_FAIL++ }
function Write-Info($msg) { Write-Host "  $INFO $msg" -ForegroundColor Cyan }

function Run-IsolationTest($container, $test) {
    $out = docker exec $container python isolation_test.py $test 2>&1
    return @{ ExitCode = $LASTEXITCODE; Output = $out }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ClawGlove Phase 5 - Fail-Closed Network Isolation Test   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start stack
Write-Host "[1/5] Starting Docker stack..." -ForegroundColor Yellow
docker compose up -d --build | Out-Null
Write-Info "Waiting 25s for services to initialise..."
Start-Sleep -Seconds 25

docker cp docker\isolation_test.py clawglove-screenwriter-agent:/app/isolation_test.py | Out-Null
docker cp docker\isolation_test.py clawglove-director-agent:/app/isolation_test.py | Out-Null
Write-Info "isolation_test.py deployed to agent containers"

# Step 2: Sidecar health
Write-Host ""
Write-Host "[2/5] Verifying sidecar health..." -ForegroundColor Yellow
$health = docker inspect --format="{{.State.Health.Status}}" clawglove-sidecar 2>&1
if ($health -match "healthy") { Write-Pass "Sidecar healthy" }
else { Write-Fail "Sidecar not healthy: $health" }

# Step 3: Network isolation
Write-Host ""
Write-Host "[3/5] Testing network isolation (direct access must be blocked)..." -ForegroundColor Yellow

$r = Run-IsolationTest "clawglove-screenwriter-agent" "direct"
if ($r.ExitCode -eq 0) { Write-Pass "Screenwriter: $($r.Output)" }
else { Write-Fail "Screenwriter: $($r.Output)" }

$r = Run-IsolationTest "clawglove-director-agent" "direct"
if ($r.ExitCode -eq 0) { Write-Pass "Director: $($r.Output)" }
else { Write-Fail "Director: $($r.Output)" }

# Step 4a: Proxy route
Write-Host ""
Write-Host "[4a/5] Testing proxy route (sidecar must intercept traffic)..." -ForegroundColor Yellow

$r = Run-IsolationTest "clawglove-screenwriter-agent" "proxy"
if ($r.ExitCode -eq 0) { Write-Pass "Screenwriter: $($r.Output)" }
else { Write-Fail "Screenwriter: $($r.Output)" }

$r = Run-IsolationTest "clawglove-director-agent" "proxy"
if ($r.ExitCode -eq 0) { Write-Pass "Director: $($r.Output)" }
else { Write-Fail "Director: $($r.Output)" }

# Step 4b: Daemon TCP
Write-Host ""
Write-Host "[4b/5] Testing daemon TCP reachability..." -ForegroundColor Yellow

$r = Run-IsolationTest "clawglove-screenwriter-agent" "daemon"
if ($r.ExitCode -eq 0) { Write-Pass "Screenwriter: $($r.Output)" }
else { Write-Fail "Screenwriter: $($r.Output)" }

$r = Run-IsolationTest "clawglove-director-agent" "daemon"
if ($r.ExitCode -eq 0) { Write-Pass "Director: $($r.Output)" }
else { Write-Fail "Director: $($r.Output)" }

# Step 5: Fail-closed
Write-Host ""
Write-Host "[5/5] Testing fail-closed (stopping sidecar)..." -ForegroundColor Yellow
Write-Info "Stopping clawglove-sidecar..."
docker stop clawglove-sidecar | Out-Null
Start-Sleep -Seconds 3

$r = Run-IsolationTest "clawglove-screenwriter-agent" "failclosed"
if ($r.ExitCode -eq 0) { Write-Pass "Screenwriter fail-closed: $($r.Output)" }
else { Write-Fail "Screenwriter fail-closed BREACH: $($r.Output)" }

$r = Run-IsolationTest "clawglove-director-agent" "failclosed"
if ($r.ExitCode -eq 0) { Write-Pass "Director fail-closed: $($r.Output)" }
else { Write-Fail "Director fail-closed BREACH: $($r.Output)" }

Write-Info "Restarting clawglove-sidecar..."
docker start clawglove-sidecar | Out-Null
Start-Sleep -Seconds 12

$r = Run-IsolationTest "clawglove-screenwriter-agent" "daemon"
if ($r.ExitCode -eq 0) { Write-Pass "Sidecar recovered: $($r.Output)" }
else { Write-Fail "Sidecar recovery failed: $($r.Output)" }

# Summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
$color = if ($TOTAL_FAIL -eq 0) { "Green" } else { "Red" }
Write-Host "  RESULT: $TOTAL_PASS passed / $TOTAL_FAIL failed" -ForegroundColor $color
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($TOTAL_FAIL -eq 0) {
    Write-Host "  Phase 5 COMPLETE - fail-closed network isolation verified." -ForegroundColor Green
    Write-Host "  Run next: .\scripts\cgbench_docker.ps1" -ForegroundColor Cyan
} else {
    Write-Host "  Phase 5 INCOMPLETE - fix failures before running CGBench." -ForegroundColor Red
    exit 1
}
