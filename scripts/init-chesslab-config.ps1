[CmdletBinding()]
param([string]$StockfishPath, [string]$TemplatesDir, [switch]$NoPrompt)
. (Join-Path $PSScriptRoot 'windows-common.ps1')
try {
    Push-Location $script:ProjectRoot
    Assert-ChessLabVenv
    $taskArguments = @('scripts/init_chesslab_config.py')
    if (-not (Test-Path -LiteralPath 'config.json') -and -not $StockfishPath -and -not (Test-Path -LiteralPath 'engine\stockfish.exe')) {
        if ($NoPrompt) { throw 'Stockfish belum diprovision. Berikan -StockfishPath <EXE-resmi>; lihat docs/windows-build-guide.md.' }
        $StockfishPath = Read-Host 'Path Stockfish 19 EXE (ekstrak arsip resmi lengkap dengan Copying.txt, AUTHORS dan src/)'
        if (-not $StockfishPath) { throw 'Path Stockfish wajib diisi; config.json belum dibuat.' }
    }
    if ($StockfishPath) { $taskArguments += @('--stockfish-path',$StockfishPath) }
    if ($TemplatesDir) { $taskArguments += @('--templates-dir',$TemplatesDir) }
    Invoke-ChessLabPython -Arguments $taskArguments
} catch {
    Write-Host ('FAIL Konfigurasi: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
