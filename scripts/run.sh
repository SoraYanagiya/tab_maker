#!/usr/bin/env bash
# ギターTAB譜メーカーを起動する（必要ならフロントエンドをビルドしてから）
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "エラー: .venv がありません。README のセットアップを実行してください。" >&2
  exit 1
fi

if [ ! -d frontend/dist ]; then
  echo "フロントエンドをビルドしています…"
  (cd frontend && npm run build)
fi

echo "http://127.0.0.1:8000 で起動します"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}"
