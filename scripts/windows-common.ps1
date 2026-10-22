Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:ProjectPython = Join-Path $script:ProjectRoot '.venv\Scripts\python.exe'

function Invoke-ChessLabPython {
    param([string]$Interpreter = $script:ProjectPython, [string[]]$Arguments)
    # -E -s mengabaikan PYTHONHOME/PYTHONPATH dan editable global milik user.
    & $Interpreter -E -s @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Perintah Python gagal (kode $LASTEXITCODE). Periksa pesan sebelumnya dan docs/windows-build-guide.md."
    }
}

function Assert-ChessLabVenv {
    if (-not (Test-Path -LiteralPath $script:ProjectPython -PathType Leaf)) {
        throw 'Environment proyek belum ada. Jalankan .\scripts\setup-windows.ps1 dahulu.'
    }
}
