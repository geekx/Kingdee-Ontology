"""FastAPI 应用入口 —— `uvicorn kingdee_console.app:app` 或 `kingdee-console` 启动。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kingdee_console import tenancy
from kingdee_console.routers import a2a, chat, dashboard


@asynccontextmanager
async def _lifespan(app: FastAPI):
    tenancy.ensure_seed_data()
    yield


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

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    return app


app = create_app()


def main() -> None:
    import uvicorn
    uvicorn.run("kingdee_console.app:app", host="0.0.0.0", port=8787, reload=False)


if __name__ == "__main__":
    main()
