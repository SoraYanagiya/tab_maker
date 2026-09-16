#!/usr/bin/env bash
# ギターTABメーカーをダブルクリック起動できるアプリにビルドする（macOS / Linux）。
# clone直後の状態からでも、これ1本で venv 作成〜依存インストール〜ビルドまで完結する。
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "venv を作成しています…"
  python3 -m venv .venv
fi

echo "Python依存関係を確認しています…"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

if [ ! -d frontend/node_modules ]; then
  echo "フロントエンドの依存関係をインストールしています…"
  (cd frontend && npm install)
fi

echo "フロントエンドをビルドしています…"
(cd frontend && npm run build)

echo "PyInstaller でアプリをビルドしています…"
rm -rf build dist/GuitarTabMaker.app dist/GuitarTabMaker

BUILD_ARGS=(
  --name "GuitarTabMaker"
  --windowed
  --noconfirm
  --add-data "frontend/dist:frontend/dist"
  --collect-all music21
  --collect-submodules pydantic
  --collect-submodules pydantic_core
)

if [ "$(uname -s)" = "Darwin" ]; then
  BUILD_ARGS+=(--hidden-import webview.platforms.cocoa)
else
  BUILD_ARGS+=(--hidden-import webview.platforms.gtk)
fi

.venv/bin/pyinstaller "${BUILD_ARGS[@]}" app/desktop.py

if [ -d "dist/GuitarTabMaker.app" ]; then
  echo "完成: dist/GuitarTabMaker.app"
else
  echo "完成: dist/GuitarTabMaker/GuitarTabMaker"
fi
