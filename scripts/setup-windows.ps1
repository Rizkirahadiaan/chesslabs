[CmdletBinding()]
param([string]$Python)
. (Join-Path $PSScriptRoot 'windows-common.ps1')

try {
    Push-Location $script:ProjectRoot
    Write-Host 'Mencari CPython 3.13 x64; instalasi Python global tidak diubah.'
    $taskCandidates = @()
    if ($Python) {
        $taskCandidates += $Python
    } elseif (Test-Path -LiteralPath $script:ProjectPython) {
        $taskCandidates += $script:ProjectPython
    } else {
        $taskLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($taskLauncher) {
            & $taskLauncher.Source -0p
            # Python launcher yang belum memiliki 3.13 menulis stderr. Di PS 5.1
            # ini tidak boleh menghentikan pencarian kandidat lokal berikutnya.
            $taskSavedPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                $taskFound = & $taskLauncher.Source -3.13 -E -s -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0 -and $taskFound) { $taskCandidates += $taskFound }
            } finally {
                $ErrorActionPreference = $taskSavedPreference
            }
        }
        $taskCandidates += (Join-Path $script:ProjectRoot '.tools\python313\python.exe')
        $taskCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($taskCommand) { $taskCandidates += $taskCommand.Source }
    }
    $taskSelected = $null
    foreach ($taskCandidate in $taskCandidates) {
        if (-not (Test-Path -LiteralPath $taskCandidate -PathType Leaf)) { continue }
        & $taskCandidate -E -s -c "import sys,sysconfig; sys.exit(0 if sys.version_info[:2]==(3,13) and sysconfig.get_platform()=='win-amd64' and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)"
        if ($LASTEXITCODE -eq 0) { $taskSelected = $taskCandidate; break }
    }
    if (-not $taskSelected) {
        throw 'CPython 3.13 x64 standar tidak ditemukan. Pasang berdampingan dari https://www.python.org/downloads/windows/ (sertakan pip dan Tcl/Tk), lalu ulangi dengan -Python <path-python313.exe>. Python 3.14 belum disertifikasi untuk lock proyek ini.'
    }
    if (-not (Test-Path -LiteralPath $script:ProjectPython)) {
        if (Test-Path -LiteralPath (Join-Path $script:ProjectRoot '.venv')) {
            throw 'Folder .venv ada tetapi rusak. Pindahkan/backup folder tersebut secara manual lalu ulangi setup.'
        }
        Invoke-ChessLabPython -Interpreter $taskSelected -Arguments @('-m','venv','.venv')
    }
    Invoke-ChessLabPython -Arguments @('-c',"import sys,sysconfig; assert sys.version_info[:2]==(3,13) and sysconfig.get_platform()=='win-amd64' and not sysconfig.get_config_var('Py_GIL_DISABLED'), '.venv harus CPython 3.13 x64 standar; backup/pindahkan .venv lalu ulangi setup'")
    Invoke-ChessLabPython -Arguments @('-m','pip','--isolated','install','--index-url','https://pypi.org/simple','-r','requirements-build.txt')
    Invoke-ChessLabPython -Arguments @('-m','pip','--isolated','install','--no-deps','--no-build-isolation','--force-reinstall','-e','.')
    Invoke-ChessLabPython -Arguments @('-m','pip','check')
    Invoke-ChessLabPython -Arguments @('-c',"import sys; sys.path.insert(0,'scripts'); from build_support import validate_environment,validate_dependencies; validate_environment(); validate_dependencies(); print('PASS Import berasal dari checkout ini dan dependency sesuai lock.')")
    Invoke-ChessLabPython -Arguments @('scripts/preflight_build.py')
    Write-Host 'PASS Setup selesai. Gunakan .venv\Scripts\python.exe untuk seluruh perintah berikutnya.'
} catch {
    Write-Host ('FAIL Setup: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Jika hanya konfigurasi/aset yang belum tersedia, jalankan .\scripts\init-chesslab-config.ps1 -StockfishPath <EXE-resmi> lalu ulangi setup.'
    exit 1
} finally {
    Pop-Location
}
