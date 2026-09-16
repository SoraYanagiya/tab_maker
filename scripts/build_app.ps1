# ギターTABメーカーをダブルクリック起動できるアプリにビルドする（Windows）。
# clone直後の状態からでも、これ1本で venv 作成〜依存インストール〜ビルドまで完結する。
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    Write-Host "venv を作成しています…"
    python -m venv .venv
}

Write-Host "Python依存関係を確認しています…"
& .venv\Scripts\pip.exe install --quiet --upgrade pip
& .venv\Scripts\pip.exe install --quiet -r requirements.txt

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "フロントエンドの依存関係をインストールしています…"
    Push-Location frontend
    npm install
    Pop-Location
}

Write-Host "フロントエンドをビルドしています…"
Push-Location frontend
npm run build
Pop-Location

Write-Host "PyInstaller でアプリをビルドしています…"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist\GuitarTabMaker

& .venv\Scripts\pyinstaller.exe `
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
