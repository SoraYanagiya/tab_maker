#!/usr/bin/env bash
# ギターTABメーカーをダブルクリック起動できる .app にビルドする（macOS スタンドアロン版）
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "エラー: .venv がありません。README のセットアップを実行してください。" >&2
  exit 1
fi

echo "フロントエンドをビルドしています…"
(cd frontend && npm run build)

echo "PyInstaller でアプリをビルドしています…"
rm -rf build dist/GuitarTabMaker.app

.venv/bin/pyinstaller \
  --name "GuitarTabMaker" \
  --windowed \
  --noconfirm \
  --add-data "frontend/dist:frontend/dist" \
  --collect-all music21 \
  --collect-submodules pydantic \
  --collect-submodules pydantic_core \
  --hidden-import webview.platforms.cocoa \
  app/desktop.py

echo "完成: dist/GuitarTabMaker.app"
