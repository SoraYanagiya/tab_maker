"""スタンドアロンアプリのエントリポイント（pywebview + FastAPI）。

FastAPIサーバーをローカルの空きポートでバックグラウンド起動し、
ネイティブウィンドウ（pywebview）からそのURLを開く。ブラウザや外部通信は不要。
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request

import uvicorn
import webview

from app.main import app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_server(port: int) -> None:
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        loop="asyncio",
        http="h11",
    )
    uvicorn.Server(config).run()


def _wait_until_ready(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return
        except OSError:
            time.sleep(0.1)


def main() -> None:
    port = _free_port()
    threading.Thread(target=_run_server, args=(port,), daemon=True).start()
    _wait_until_ready(port)

    webview.create_window(
        "ギターTABメーカー",
        f"http://127.0.0.1:{port}",
        width=1360,
        height=900,
        min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
