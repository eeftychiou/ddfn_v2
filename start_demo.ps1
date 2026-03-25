# DDFN v2 System Launch Script (Single Terminal Demo)
# This script launches the full decentralized cluster as background jobs in THIS window.
# To stop all components, press Ctrl+C or close this terminal.
# 
# LAUNCH MODES DEMONSTRATED:
# - FMP Nodes 8010, 8011, 8012: CONFIGURED (auto-load HECC/LGGG/LCCC configurations)
# - FMP Node 8013: UNCONFIGURED (require manual setup via Airspace Config tab)

$ErrorActionPreference = "Stop"

# Kill any lingering Python processes from previous runs
Write-Host "Cleaning up any lingering Python processes..." -ForegroundColor Yellow
$ports = @(8001, 8010, 8011, 8012, 8013, 8050)
foreach ($port in $ports) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($conn in $connections) {
            if ($conn.OwningProcess -and $conn.OwningProcess -ne 0) {
                try {
                    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                    Write-Host "  Killed process using port $port (PID: $($conn.OwningProcess))" -ForegroundColor Gray
                } catch {}
            }
        }
    } catch {}
}
Start-Sleep -Seconds 2

# Set up environment
$ProjectRoot = (Get-Location).Path
$AIXM_PATH = "$ProjectRoot\AIXM\BD_2025-09-30_400005921419525.xml"
$BROKER_WS = "ws://127.0.0.1:8001/ws"
$PYTHON_EXE = "python"
$CONFIG_DIR = "$ProjectRoot\data\node_configs"

# Ensure config directory exists
New-Item -ItemType Directory -Force -Path $CONFIG_DIR | Out-Null

# Set a consistent API key for all services (prevents auth failures)
$DDFN_API_KEY = "demo-api-key-12345"
Write-Host "Using shared API key for all services" -ForegroundColor Gray

Write-Host "--- DDFN v2 Full System Launch (Background Mode) ---" -ForegroundColor Cyan
Write-Host "All components will run as background jobs. Output is supressed." -ForegroundColor Gray
Write-Host "" -ForegroundColor Gray
Write-Host "LAUNCH MODE DEMONSTRATION:" -ForegroundColor Yellow
Write-Host "  - FMP 8010, 8011, 8012: CONFIGURED (HECC/LGGG/LCCC configs)" -ForegroundColor Green
Write-Host "  - FMP 8013: UNCONFIGURED (manual setup required)" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to terminate the entire cluster.`n" -ForegroundColor Yellow

# ---------------------------------------------------------------------------
# FMP NODE CONFIGURATION SETUP
# ---------------------------------------------------------------------------
# Instead of creating configurations in this script, we use pre-existing 
# JSON files from $CONFIG_DIR. The source files are:
# - FMP_HECC.json
# - FMP_LGGG.json
# - FMP_LCCC.json
#
# We copy them to the node-specific expected paths before launch.
# ---------------------------------------------------------------------------

Write-Host "Setting up FMP Node configurations from pre-existing files..." -ForegroundColor Yellow

# Port 8010 -> HECC
if (Test-Path "$CONFIG_DIR\FMP_HECC.json") {
    Copy-Item -Path "$CONFIG_DIR\FMP_HECC.json" -Destination "$CONFIG_DIR\FMP_8010_DDFN_NODE.json" -Force
    Write-Host "  Prepared HECC config for Node 8010" -ForegroundColor Green
} else {
    Write-Host "  Warning: FMP_HECC.json not found in $CONFIG_DIR" -ForegroundColor Red
}

# Port 8011 -> LGGG
if (Test-Path "$CONFIG_DIR\FMP_LGGG.json") {
    Copy-Item -Path "$CONFIG_DIR\FMP_LGGG.json" -Destination "$CONFIG_DIR\FMP_8011_DDFN_NODE.json" -Force
    Write-Host "  Prepared LGGG config for Node 8011" -ForegroundColor Green
} else {
    Write-Host "  Warning: FMP_LGGG.json not found in $CONFIG_DIR" -ForegroundColor Red
}

# Port 8012 -> LCCC
if (Test-Path "$CONFIG_DIR\FMP_LCCC.json") {
    Copy-Item -Path "$CONFIG_DIR\FMP_LCCC.json" -Destination "$CONFIG_DIR\FMP_8012_DDFN_NODE.json" -Force
    Write-Host "  Prepared LCCC config for Node 8012" -ForegroundColor Green
} else {
    Write-Host "  Warning: FMP_LCCC.json not found in $CONFIG_DIR" -ForegroundColor Red
}

# Port 8013 -> UNCONFIGURED (Delete any existing config to ensure clean start)
if (Test-Path "$CONFIG_DIR\FMP_8013_DDFN_NODE.json") {
    Remove-Item -Path "$CONFIG_DIR\FMP_8013_DDFN_NODE.json" -Force
}
Write-Host "  Node 8013 set to UNCONFIGURED state.`n" -ForegroundColor White

$jobs = @()

function Start-DdfnJob {
    param(
        [string]$Name,
        [scriptblock]$ScriptBlock,
        [string]$LogName
    )
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] Starting $Name..." -ForegroundColor Green -NoNewline
    
    try {
        $job = Start-Job -Name $Name -ScriptBlock $ScriptBlock -ArgumentList $ProjectRoot, $BROKER_WS, $AIXM_PATH, $PYTHON_EXE, $DDFN_API_KEY
        
        # Quick check for immediate failure
        Start-Sleep -Milliseconds 500
        
        if ($job.State -eq 'Failed') {
            Write-Host " [FAILED IMMEDIATELY]" -ForegroundColor Red
            $errorOutput = Receive-Job -Job $job -Keep -ErrorAction SilentlyContinue
            if ($errorOutput) {
                Write-Host "  Startup Error: $errorOutput" -ForegroundColor Red
            }
            # Check for child job errors
            if ($job.ChildJobs[0].JobStateInfo.Reason) {
                Write-Host "  Error Reason: $($job.ChildJobs[0].JobStateInfo.Reason)" -ForegroundColor Red
            }
        } else {
            Write-Host " [PID: $($job.Id)]" -ForegroundColor Gray
        }
        
        return $job
    } catch {
        Write-Host " [EXCEPTION]" -ForegroundColor Red
        Write-Host "  Exception: $_" -ForegroundColor Red
        throw
    }
}

try {
    # 1. Start SWIM Broker
    $jobs += Start-DdfnJob "Broker" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_broker.log"
        & $py -m ddfn_v2.core.broker 2>&1 | Tee-Object -FilePath $logFile
    }

    Start-Sleep -Seconds 5

    # Wait for broker to be ready
    Write-Host "Waiting for broker to be ready..." -ForegroundColor Yellow
    $brokerReady = $false
    $attempts = 0
    while (-not $brokerReady -and $attempts -lt 30) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $brokerReady = $true
                Write-Host "Broker is ready!" -ForegroundColor Green
            }
        } catch {
            Start-Sleep -Milliseconds 500
            $attempts++
        }
    }
    if (-not $brokerReady) {
        Write-Host "Warning: Broker health check timed out, proceeding anyway..." -ForegroundColor Yellow
    }

    # 2. Start FMP Nodes
    # CONFIGURED nodes (8010, 8011, 8012) - load pre-existing FIR configs
    $jobs += Start-DdfnJob "FMP_Node_8010" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_fmp_8010.log"
        & $py -m ddfn_v2.services.fmp_service --port 8010 --broker $ws 2>&1 | Tee-Object -FilePath $logFile
    }
    $jobs += Start-DdfnJob "FMP_Node_8011" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_fmp_8011.log"
        & $py -m ddfn_v2.services.fmp_service --port 8011 --broker $ws 2>&1 | Tee-Object -FilePath $logFile
    }
    $jobs += Start-DdfnJob "FMP_Node_8012" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_fmp_8012.log"
        & $py -m ddfn_v2.services.fmp_service --port 8012 --broker $ws 2>&1 | Tee-Object -FilePath $logFile
    }
    
    # UNCONFIGURED node (8013) - no config files, require manual setup
    $jobs += Start-DdfnJob "FMP_Node_8013" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_fmp_8013.log"
        & $py -m ddfn_v2.services.fmp_service --port 8013 --broker $ws 2>&1 | Tee-Object -FilePath $logFile
    }

    # 3. Start Airport Nodes
    $jobs += Start-DdfnJob "Airport_LFPG" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_airport_lfpg.log"
        & $py -m ddfn_v2.services.airport_service LFPG --broker $ws --aixm "$aixm" --port 8020 2>&1 | Tee-Object -FilePath $logFile
    }
    $jobs += Start-DdfnJob "Airport_EDDF" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_airport_eddf.log"
        & $py -m ddfn_v2.services.airport_service EDDF --broker $ws --aixm "$aixm" --port 8021 2>&1 | Tee-Object -FilePath $logFile
    }
    $jobs += Start-DdfnJob "Airport_EGLL" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_airport_egll.log"
        & $py -m ddfn_v2.services.airport_service EGLL --broker $ws --aixm "$aixm" --port 8022 2>&1 | Tee-Object -FilePath $logFile
    }

    # 4. Start AOC Nodes
    $jobs += Start-DdfnJob "AOC_AFR" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_aoc_afr.log"
        & $py -m ddfn_v2.services.aoc_service AFR --broker $ws --aixm "$aixm" 2>&1 | Tee-Object -FilePath $logFile
    }
    $jobs += Start-DdfnJob "AOC_DLH" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_aoc_dlh.log"
        & $py -m ddfn_v2.services.aoc_service DLH --broker $ws --aixm "$aixm" 2>&1 | Tee-Object -FilePath $logFile
    }
    $jobs += Start-DdfnJob "AOC_BAW" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_aoc_baw.log"
        & $py -m ddfn_v2.services.aoc_service BAW --broker $ws --aixm "$aixm" 2>&1 | Tee-Object -FilePath $logFile
    }

    # 5. Start Sim Manager
    $jobs += Start-DdfnJob "Sim_Manager" {
        param($root, $ws, $aixm, $py, $api_key)
        $env:PYTHONPATH = "$root\src"
        $env:DDFN_API_KEY = $api_key
        Set-Location $root
        $logFile = "$root\logs\demo_sim_manager.log"
        & $py -m ddfn_v2.services.sim_manager --port 8050 --broker $ws 2>&1 | Tee-Object -FilePath $logFile
    }

    Write-Host "`nAll components launched successfully in the background!" -ForegroundColor Cyan
    Write-Host "--------------------------------------------------"
    Write-Host "Access Dashboards:" -ForegroundColor Yellow
    Write-Host "  Broker Audit:  http://127.0.0.1:8001"
    Write-Host "  Sim Manager:   http://127.0.0.1:8050"
    Write-Host "  FMP Instance 1: http://127.0.0.1:8010  <-- CONFIGURED (HECC loaded)" -ForegroundColor Green
    Write-Host "  FMP Instance 2: http://127.0.0.1:8011  <-- CONFIGURED (LGGG loaded)" -ForegroundColor Green
    Write-Host "  FMP Instance 3: http://127.0.0.1:8012  <-- CONFIGURED (LCCC loaded)" -ForegroundColor Green
    Write-Host "  FMP Instance 4: http://127.0.0.1:8013  <-- UNCONFIGURED (needs setup)" -ForegroundColor White
    Write-Host ""
    Write-Host "Note: First-time users can practice setup on 8013 or 8010." -ForegroundColor White -BackgroundColor DarkRed
    Write-Host "--------------------------------------------------"
    Write-Host "Use 'Get-Job' to see process status."
    Write-Host "Monitoring cluster state... (Ctrl+C to stop everything)"

    # Debug logging function
    function Write-DebugLog {
        param([string]$Message, [string]$Color = "Gray")
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Write-Host "[$timestamp] $Message" -ForegroundColor $Color
    }

    # Store job info for tracking
    $jobInfo = @{}
    foreach ($job in $jobs) {
        $jobInfo[$job.Name] = @{
            StartTime = Get-Date
            LogFile = "$ProjectRoot\logs\demo_$($job.Name.ToLower().Replace(' ', '_')).log"
        }
    }

    while ($true) {
        $allJobs = Get-Job
        $failed = $allJobs | Where-Object { $_.State -eq 'Failed' }
        $stopped = $allJobs | Where-Object { $_.State -ne 'Running' -and $_.State -ne 'Completed' -and $_.State -ne 'Failed' }
        $running = $allJobs | Where-Object { $_.State -eq 'Running' }
        $completed = $allJobs | Where-Object { $_.State -eq 'Completed' }
        
        # Report failed jobs with full diagnostics
        foreach ($job in $failed) {
            if (-not $jobInfo[$job.Name].Reported) {
                Write-Host "`n========================================" -ForegroundColor Red
                Write-Host "CRITICAL: Job '$($job.Name)' has FAILED!" -ForegroundColor Red
                Write-Host "========================================" -ForegroundColor Red
                
                # Get job output
                $output = Receive-Job -Job $job -Keep -ErrorAction SilentlyContinue
                if ($output) {
                    Write-Host "`nJob Output (last 50 lines):" -ForegroundColor Yellow
                    $output | Select-Object -Last 50 | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
                }
                
                # Get error details
                if ($job.ChildJobs[0].JobStateInfo.Reason) {
                    Write-Host "`nError Reason: $($job.ChildJobs[0].JobStateInfo.Reason)" -ForegroundColor Red
                }
                
                # Show log file tail if it exists
                $logFile = $jobInfo[$job.Name].LogFile
                if (Test-Path $logFile) {
                    Write-Host "`nLog file tail ($logFile):" -ForegroundColor Cyan
                    try {
                        $logContent = Get-Content $logFile -Tail 30 -ErrorAction SilentlyContinue
                        $logContent | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
                    } catch {
                        Write-Host "  (Could not read log file)" -ForegroundColor DarkGray
                    }
                }
                
                # Show process info if available
                if ($job.ChildJobs[0].PSChildJobs) {
                    Write-Host "`nJob Details:" -ForegroundColor Cyan
                    Write-Host "  Start Time: $($jobInfo[$job.Name].StartTime)" -ForegroundColor Gray
                    Write-Host "  State: $($job.State)" -ForegroundColor Gray
                    Write-Host "  Has More Data: $($job.HasMoreData)" -ForegroundColor Gray
                }
                
                Write-Host "========================================`n" -ForegroundColor Red
                $jobInfo[$job.Name].Reported = $true
            }
        }
        
        # Report stopped jobs (not failed, not completed)
        foreach ($job in $stopped) {
            if (-not $jobInfo[$job.Name].Reported) {
                Write-Host "`n========================================" -ForegroundColor DarkYellow
                Write-Host "WARNING: Job '$($job.Name)' has STOPPED unexpectedly!" -ForegroundColor DarkYellow
                Write-Host "State: $($job.State)" -ForegroundColor DarkYellow
                Write-Host "========================================" -ForegroundColor DarkYellow
                
                $output = Receive-Job -Job $job -Keep -ErrorAction SilentlyContinue
                if ($output) {
                    Write-Host "`nJob Output:" -ForegroundColor Yellow
                    $output | Select-Object -Last 30 | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
                }
                
                $logFile = $jobInfo[$job.Name].LogFile
                if (Test-Path $logFile) {
                    Write-Host "`nLog file tail ($logFile):" -ForegroundColor Cyan
                    try {
                        $logContent = Get-Content $logFile -Tail 20 -ErrorAction SilentlyContinue
                        $logContent | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
                    } catch {}
                }
                
                Write-Host "========================================`n" -ForegroundColor DarkYellow
                $jobInfo[$job.Name].Reported = $true
            }
        }
        
        # Periodic status summary
        $stoppedCount = $jobs.Count - $running.Count
        if ($stoppedCount -gt 0) {
            $failedCount = ($failed | Measure-Object).Count
            $completedCount = ($completed | Measure-Object).Count
            $otherStopped = $stoppedCount - $failedCount - $completedCount
            
            Write-Host "`n[$($allJobs.Count) jobs total] " -NoNewline -ForegroundColor Cyan
            Write-Host "Running: $($running.Count) | " -NoNewline -ForegroundColor Green
            Write-Host "Failed: $failedCount | " -NoNewline -ForegroundColor Red
            Write-Host "Completed: $completedCount | " -NoNewline -ForegroundColor Blue
            Write-Host "Other Stopped: $otherStopped" -ForegroundColor DarkYellow
            
            if ($failedCount -gt 0) {
                $failedNames = ($failed | Select-Object -ExpandProperty Name) -join ", "
                Write-Host "Failed jobs: $failedNames" -ForegroundColor Red
            }
            if ($otherStopped -gt 0) {
                $stoppedNames = ($stopped | Select-Object -ExpandProperty Name) -join ", "
                Write-Host "Stopped jobs: $stoppedNames" -ForegroundColor DarkYellow
            }
        }
        
        Start-Sleep -Seconds 5
    }

} finally {
    Write-Host "`nStopping all DDFN components..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job -Force
    Write-Host "Cleanup complete. Goodbye!" -ForegroundColor Cyan
}
