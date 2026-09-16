# ギターTABメーカーをダブルクリック起動できるアプリにビルドする（Windows）。
# clone直後の状態からでも、これ1本で venv 作成〜依存インストール〜ビルドまで完結する。
$ErrorActionPreference = "Stop"

# PowerShellは外部コマンドの終了コードを自動でエラー扱いしないため、
# 失敗したら即座にスクリプトを止める。
function Invoke-Checked {
    param([string]$Description)
    & $args[0] @($args[1..($args.Length - 1)])
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Description が失敗しました (exit code $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
}

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    Write-Host "venv を作成しています…"
    Invoke-Checked "venvの作成" python -m venv .venv
}

$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
$venvPyInstaller = Join-Path (Get-Location) ".venv\Scripts\pyinstaller.exe"

Write-Host "Python依存関係を確認しています…"
Invoke-Checked "pipの更新" $venvPython -m pip install --quiet --upgrade pip
Invoke-Checked "依存関係のインストール" $venvPython -m pip install --quiet -r requirements.txt

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "フロントエンドの依存関係をインストールしています…"
    Push-Location frontend
    Invoke-Checked "npm install" npm install
    Pop-Location
}

Write-Host "フロントエンドをビルドしています…"
Push-Location frontend
Invoke-Checked "フロントエンドのビルド" npm run build
Pop-Location

if (-not (Test-Path $venvPyInstaller)) {
    Write-Error "pyinstaller が見つかりません ($venvPyInstaller)。依存関係のインストールに失敗している可能性があります。"
    exit 1
}

Write-Host "PyInstaller でアプリをビルドしています…"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist\GuitarTabMaker

Invoke-Checked "PyInstallerビルド" $venvPyInstaller `
    --name "GuitarTabMaker" `
    --windowed `
    --noconfirm `
    --add-data "frontend/dist;frontend/dist" `
    --collect-all music21 `
    --collect-submodules pydantic `
    --collect-submodules pydantic_core `
    --hidden-import webview.platforms.edgechromium `
    --hidden-import clr_loader `
    app/desktop.py

Write-Host "完成: dist\GuitarTabMaker\GuitarTabMaker.exe"
