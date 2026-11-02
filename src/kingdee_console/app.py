"""FastAPI 应用入口 —— `uvicorn kingdee_console.app:app` 或 `kingdee-console` 启动。"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kingdee_console import tenancy
from kingdee_console.routers import a2a, chat, dashboard, events, ontology


@asynccontextmanager
async def _lifespan(app: FastAPI):
    tenancy.ensure_seed_data()
    yield


def _static_dir() -> Path | None:
    """生产镜像（Dockerfile.console）把前端 `npm run build` 的产物放这里；
    本地开发走 `npm run dev`（5173 端口 + /api 代理），不设这个变量就不挂载。
    """
    raw = os.environ.get("KINGDEE_CONSOLE_STATIC_DIR")
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def create_app() -> FastAPI:
    app = FastAPI(title="Kingdee Console", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
    )

    app.include_router(dashboard.router)
    app.include_router(chat.router)
    app.include_router(a2a.router)
    app.include_router(events.router)
    app.include_router(ontology.router)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    static_dir = _static_dir()
    if static_dir is not None:
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="console-assets")

        index_file = static_dir / "index.html"

        @app.get("/{full_path:path}")
        async def spa(full_path: str) -> FileResponse:
            # 单页应用：非 /api 的路径（/、/chat、/ontology…）都交给前端路由，
            # 全部回落到 index.html；真正的 404（不存在的静态文件）仍按原样处理。
            candidate = static_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_file)

    return app


app = create_app()


def main() -> None:
    import uvicorn
    host = os.environ.get("KINGDEE_CONSOLE_HOST", "0.0.0.0")
    port = int(os.environ.get("KINGDEE_CONSOLE_PORT", "8787"))
    uvicorn.run("kingdee_console.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
