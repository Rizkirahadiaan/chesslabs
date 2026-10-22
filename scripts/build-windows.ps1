[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'windows-common.ps1')
try {
    Push-Location $script:ProjectRoot
    Assert-ChessLabVenv
    # build_portable juga menjalankan preflight sehingga pemanggilan langsung aman.
    Invoke-ChessLabPython -Arguments @('packaging/build_portable.py')
    Write-Host 'PASS Hasil tervalidasi: outputs\licensed\ChessLab-Coach.exe'
} catch {
    Write-Host ('FAIL Build: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
