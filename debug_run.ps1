$ErrorActionPreference = 'Stop'
try {
    .\start_demo.ps1
} catch {
    Write-Host "`n--- ERROR DETECTED ---" -ForegroundColor Red
    $Error[0] | Format-List -Property * -Force | Out-File -FilePath demo_error.log
    Write-Host "Error details written to demo_error.log" -ForegroundColor Yellow
}
