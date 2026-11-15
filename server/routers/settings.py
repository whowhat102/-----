"""系统设置：模式切换、API 配置、合规开关、连接测试。"""
from fastapi import APIRouter, Depends
import sqlite3

from ..db import get_db, get_settings
from ..engine.llm import LLMError, test_connection
from ..schemas import SettingsIn

router = APIRouter()


def _out(row: sqlite3.Row) -> dict:
    return {"mode": row["mode"], "api_base_url": row["api_base_url"],
            "api_key": row["api_key"], "api_model": row["api_model"],
            "api_temperature": row["api_temperature"],
            "disclose_bot": row["disclose_bot"], "product_name": row["product_name"]}


@router.get("/api/settings")
def read_settings(conn=Depends(get_db)):
    return _out(get_settings(conn))


@router.put("/api/settings")
def update_settings(req: SettingsIn, conn=Depends(get_db)):
    conn.execute(
        "UPDATE settings SET mode=?, api_base_url=?, api_key=?, api_model=?,"
        " api_temperature=?, disclose_bot=?, product_name=? WHERE id=1",
        (req.mode, req.api_base_url.rstrip("/"), req.api_key, req.api_model,
         req.api_temperature, req.disclose_bot, req.product_name))
    conn.commit()
    return _out(get_settings(conn))


@router.post("/api/settings/test")
async def test_settings(req: SettingsIn, conn=Depends(get_db)):
    """用表单当前值（无需先保存）测试大模型连通性。"""
    row = {"api_key": req.api_key, "api_base_url": req.api_base_url.rstrip("/"),
           "api_model": req.api_model, "api_temperature": req.api_temperature}

    class _S(dict):
        def __getitem__(self, k):
            return dict.get(self, k)

    try:
        reply = await test_connection(_S(row))
        return {"ok": True, "message": f"连接成功，模型回复：{reply}"}
    except LLMError as exc:
        return {"ok": False, "message": str(exc)}
