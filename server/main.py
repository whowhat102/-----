"""小熙客服 · FastAPI 入口：建表、挂路由、托管前端静态文件。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import db
from .routers import chat, config, knowledge
from .routers import settings as settings_api

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="小熙客服", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"ok": True, "product": "小熙客服", "version": "0.1.0"}


@app.post("/api/dev/reset")
def dev_reset():
    """开发辅助：清空业务数据并重灌演示种子（冒烟测试/演示复位用）。"""
    conn = db.get_conn()
    try:
        db.reseed(conn)
    finally:
        conn.close()
    return {"ok": True}


app.include_router(knowledge.router)
app.include_router(config.router)
app.include_router(chat.router)
app.include_router(settings_api.router)

# 静态前端（注册在最后，API 路由优先匹配）
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
