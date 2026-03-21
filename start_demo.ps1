# DDFN v2 System Launch Script (Single Terminal Demo)
# This script launches the full decentralized cluster as background jobs in THIS window.
# To stop all components, press Ctrl+C or close this terminal.

$ErrorActionPreference = "Stop"

# Set up environment
$ProjectRoot = (Get-Location).Path
$AIXM_PATH = "$ProjectRoot\AIXM\BD_2025-09-30_400005921419525.xml"
$BROKER_WS = "ws://127.0.0.1:8001/ws"
$PYTHON_EXE = "$ProjectRoot\.venv\Scripts\python.exe"

Write-Host "--- DDFN v2 Full System Launch (Background Mode) ---" -ForegroundColor Cyan
Write-Host "All components will run as background jobs. Output is supressed." -ForegroundColor Gray
Write-Host "IMPORTANT: FMP Nodes start UNCONFIGURED. You must perform initial setup in the UI." -ForegroundColor White -BackgroundColor DarkRed
Write-Host "Press Ctrl+C to terminate the entire cluster.`n" -ForegroundColor Yellow

$jobs = @()

function Start-DdfnJob {
    param(
        [string]$Name,
        [scriptblock]$ScriptBlock,
        [string]$LogName
    )
    Write-Host "Starting $Name..." -ForegroundColor Green
    $job = Start-Job -Name $Name -ScriptBlock $ScriptBlock -ArgumentList $ProjectRoot, $BROKER_WS, $AIXM_PATH, $PYTHON_EXE
    return $job
}

try {
    # 1. Start SWIM Broker
    $jobs += Start-DdfnJob "Broker" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.core.broker
    }

    Start-Sleep -Seconds 2

    # 2. Start FMP Nodes
    $jobs += Start-DdfnJob "FMP_Node_8013" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.fmp_service --port 8013 --broker $ws
    }
    $jobs += Start-DdfnJob "FMP_Node_8010" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.fmp_service --port 8010 --broker $ws
    }
    $jobs += Start-DdfnJob "FMP_Node_8011" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.fmp_service --port 8011 --broker $ws
    }
    $jobs += Start-DdfnJob "FMP_Node_8012" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.fmp_service --port 8012 --broker $ws
    }

    # 3. Start Airport Nodes
    $jobs += Start-DdfnJob "Airport_LFPG" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.airport_service LFPG --broker $ws --aixm "$aixm"
    }
    $jobs += Start-DdfnJob "Airport_EDDF" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.airport_service EDDF --broker $ws --aixm "$aixm"
    }
    $jobs += Start-DdfnJob "Airport_EGLL" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.airport_service EGLL --broker $ws --aixm "$aixm"
    }

    # 4. Start AOC Nodes
    $jobs += Start-DdfnJob "AOC_AFR" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.aoc_service AFR --broker $ws --aixm "$aixm"
    }
    $jobs += Start-DdfnJob "AOC_DLH" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.aoc_service DLH --broker $ws --aixm "$aixm"
    }
    $jobs += Start-DdfnJob "AOC_BAW" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.aoc_service BAW --broker $ws --aixm "$aixm"
    }

    # 5. Start Sim Manager
    $jobs += Start-DdfnJob "Sim_Manager" {
        param($root, $ws, $aixm, $py)
        $env:PYTHONPATH = "$root\src"
        Set-Location $root
        & $py -m ddfn_v2.services.sim_manager --port 8050 --broker $ws
    }

    Write-Host "`nAll components launched successfully in the background!" -ForegroundColor Cyan
    Write-Host "--------------------------------------------------"
    Write-Host "Access Dashboards:" -ForegroundColor Yellow
    Write-Host "  Broker Audit:  http://127.0.0.1:8001"
    Write-Host "  Sim Manager:   http://127.0.0.1:8050"
    Write-Host ""
    Write-Host "  FMP Instance 1: http://127.0.0.1:8013  <-- Recom. for LCCC" -ForegroundColor Cyan
    Write-Host "  FMP Instance 2: http://127.0.0.1:8010"
    Write-Host "  FMP Instance 3: http://127.0.0.1:8011"
    Write-Host "  FMP Instance 4: http://127.0.0.1:8012"
    Write-Host ""
    Write-Host "Note: First-time users MUST configure the node in 'Airspace Config' tab." -ForegroundColor White -BackgroundColor DarkRed
    Write-Host "--------------------------------------------------"
    Write-Host "Use 'Get-Job' to see process status."
    Write-Host "Monitoring cluster state... (Ctrl+C to stop everything)"

    while ($true) {
        $failed = Get-Job | Where-Object { $_.State -ne 'Running' -and $_.State -ne 'Completed' }
        foreach ($job in $failed) {
            Write-Host "`nERROR: Job '$($job.Name)' stopped! Output:" -ForegroundColor Red
            Receive-Job -Job $job -Keep | Write-Host -ForegroundColor Yellow
        }
        
        $running = Get-Job | Where-Object { $_.State -eq 'Running' }
        if ($running.Count -lt $jobs.Count) {
             Write-Host "Warning: $( ($jobs.Count - $running.Count) ) jobs have stopped!" -ForegroundColor Red
        }
        Start-Sleep -Seconds 5
    }

} finally {
    Write-Host "`nStopping all DDFN components..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job -Force
    Write-Host "Cleanup complete. Goodbye!" -ForegroundColor Cyan
}
