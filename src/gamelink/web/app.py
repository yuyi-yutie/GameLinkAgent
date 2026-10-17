"""FastAPI application: the local HTTP surface in front of the pipeline."""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from gamelink import __version__
from gamelink.errors import GameLinkError
from gamelink.pipeline.jobs import JobManager
from gamelink.resources import static_root
from gamelink.web.routes import files, jobs, meta
from gamelink.web.security import LocalOnlyMiddleware

BUILD_HINT = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>GameLink Agent</title>
<style>body{font-family:system-ui,sans-serif;margin:3rem auto;max-width:44rem;line-height:1.7}
code{background:#f2f2f2;padding:.15rem .35rem;border-radius:4px}</style></head>
<body><h1>前端尚未构建</h1>
<p>后端已经就绪，但还没有可用的界面。在仓库根目录执行：</p>
<pre><code>cd web
npm install
npm run build</code></pre>
<p>构建产物会写到 <code>src/gamelink/web/static/</code>，然后刷新本页即可。</p>
<p>开发模式下可以用 <code>npm run dev</code>（Vite 会把 <code>/api</code> 代理到本服务）。</p>
</body></html>
"""


def create_app(workspace: str | Path | None = None) -> FastAPI:
    root = Path(workspace or Path.cwd()).resolve()
    app = FastAPI(
        title="GameLink Agent",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.workspace = root
    app.state.jobs = JobManager(root)
    app.add_middleware(LocalOnlyMiddleware)
    app.include_router(meta.router)
    app.include_router(files.router)
    app.include_router(jobs.router)

    @app.exception_handler(GameLinkError)
    async def gamelink_error(request: Request, exc: GameLinkError) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"error": str(exc), "kind": type(exc).__name__}
        )

    static = static_root()
    assets = static / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> HTMLResponse:
        if path.startswith("api/"):
            return JSONResponse({"error": "not found"}, status_code=404)
        index = static / "index.html"
        if not index.is_file():
            return HTMLResponse(BUILD_HINT, status_code=503)
        return HTMLResponse(index.read_text(encoding="utf-8"))

    return app


def serve(
    workspace: str | Path | None = None,
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Run the local UI server on the loopback interface."""
    import uvicorn

    app = create_app(workspace)
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
