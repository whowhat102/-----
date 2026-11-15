"""会话、聊天主流程、评分纠错、训练中心数据。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import sqlite3

from ..db import get_db, get_settings
from ..schemas import ChatRequest, FeedbackRequest, SessionCreate, SessionUpdate
from ..engine.llm import LLMError, chat_completion
from ..engine.mock import mock_reply
from ..engine.prompt import build_system_prompt

router = APIRouter()

HUMAN_MARKER = "[转人工]"


def _session_out(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "persona_id": row["persona_id"],
            "scenario_id": row["scenario_id"], "audience_id": row["audience_id"],
            "needs_human": row["needs_human"], "created_at": row["created_at"],
            "updated_at": row["updated_at"]}


def _msg_out(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "session_id": row["session_id"], "role": row["role"],
            "content": row["content"], "rating": row["rating"],
            "meta": json.loads(row["meta"] or "{}"), "created_at": row["created_at"]}


def _name(conn, table: str, rid) -> str:
    if not rid:
        return ""
    row = conn.execute(f"SELECT name FROM {table} WHERE id=?", (rid,)).fetchone()
    return row["name"] if row else ""


# ---------------------------------------------------------------- 会话
@router.get("/api/sessions")
def list_sessions(conn=Depends(get_db)):
    return [_session_out(r) for r in
            conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC, id DESC")]


@router.post("/api/sessions")
def create_session(req: SessionCreate, conn=Depends(get_db)):
    title = req.title or "·".join(x for x in [
        _name(conn, "scenarios", req.scenario_id),
        _name(conn, "audiences", req.audience_id)] if x) or "新会话"
    cur = conn.execute(
        "INSERT INTO sessions (title, persona_id, scenario_id, audience_id)"
        " VALUES (?,?,?,?)",
        (title, req.persona_id, req.scenario_id, req.audience_id))
    conn.commit()
    return _session_out(conn.execute("SELECT * FROM sessions WHERE id=?",
                                     (cur.lastrowid,)).fetchone())


@router.get("/api/sessions/{sid}")
def get_session(sid: int, conn=Depends(get_db)):
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(404, "会话不存在")
    return _session_out(row)


@router.put("/api/sessions/{sid}")
def update_session(sid: int, req: SessionUpdate, conn=Depends(get_db)):
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(404, "会话不存在")
    persona_id = req.persona_id if req.persona_id is not None else row["persona_id"]
    scenario_id = req.scenario_id if req.scenario_id is not None else row["scenario_id"]
    audience_id = req.audience_id if req.audience_id is not None else row["audience_id"]
    title = req.title or "·".join(x for x in [
        _name(conn, "scenarios", scenario_id),
        _name(conn, "audiences", audience_id)] if x) or row["title"]
    conn.execute(
        "UPDATE sessions SET title=?, persona_id=?, scenario_id=?, audience_id=?,"
        " updated_at=datetime('now','localtime') WHERE id=?",
        (title, persona_id, scenario_id, audience_id, sid))
    conn.commit()
    return _session_out(conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone())


@router.delete("/api/sessions/{sid}")
def delete_session(sid: int, conn=Depends(get_db)):
    cur = conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "会话不存在")
    return {"ok": True}


@router.get("/api/sessions/{sid}/messages")
def get_messages(sid: int, conn=Depends(get_db)):
    if conn.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone() is None:
        raise HTTPException(404, "会话不存在")
    return [_msg_out(r) for r in
            conn.execute("SELECT * FROM messages WHERE session_id=? ORDER BY id",
                         (sid,))]


# ---------------------------------------------------------------- 聊天主流程
@router.post("/api/chat")
async def chat(req: ChatRequest, conn=Depends(get_db)):
    session = conn.execute("SELECT * FROM sessions WHERE id=?",
                           (req.session_id,)).fetchone()
    if session is None:
        raise HTTPException(404, "会话不存在")

    persona = conn.execute("SELECT * FROM personas WHERE id=?",
                           (session["persona_id"],)).fetchone() \
        if session["persona_id"] else None
    scenario = conn.execute("SELECT * FROM scenarios WHERE id=?",
                            (session["scenario_id"],)).fetchone() \
        if session["scenario_id"] else None
    audience = conn.execute("SELECT * FROM audiences WHERE id=?",
                            (session["audience_id"],)).fetchone() \
        if session["audience_id"] else None
    settings = get_settings(conn)

    # 保存来访者消息
    conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)",
                 (req.session_id, "user", req.message))

    history = [{"role": "assistant" if m["role"] == "bot" else "user",
                "content": m["content"]}
               for m in conn.execute(
                   "SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 12",
                   (req.session_id,)).fetchall()][::-1]
    bot_count = conn.execute(
        "SELECT COUNT(*) AS c FROM messages WHERE session_id=? AND role='bot'",
        (req.session_id,)).fetchone()["c"]

    matched: list = []
    used_correction = False
    error = None

    if settings["mode"] == "llm":
        built = build_system_prompt(conn, persona, scenario, audience,
                                    req.message, bot_count,
                                    bool(settings["disclose_bot"]))
        matched = [h["title"] for h in built["hits"]]
        used_correction = bool(built["corrections"])
        try:
            reply = await chat_completion(settings, built["prompt"], history)
            engine = "llm"
        except LLMError as exc:
            # 真实引擎失败 → 降级模拟引擎，保证对话不中断
            error = str(exc)
            reply, matched, _, used_correction = mock_reply(
                conn, persona, scenario, bot_count, req.message,
                bool(settings["disclose_bot"]))
            engine = "mock(fallback)"
    else:
        reply, matched, _, used_correction = mock_reply(
            conn, persona, scenario, bot_count, req.message,
            bool(settings["disclose_bot"]))
        engine = "mock"

    # 解析转人工标记
    needs_human = HUMAN_MARKER in reply
    reply = reply.replace(HUMAN_MARKER, "").strip()

    meta = {"engine": engine, "knowledge": matched,
            "used_correction": used_correction}
    if error:
        meta["error"] = error

    conn.execute(
        "INSERT INTO messages (session_id, role, content, meta) VALUES (?,?,?,?)",
        (req.session_id, "bot", reply, json.dumps(meta, ensure_ascii=False)))
    if needs_human:
        conn.execute("UPDATE sessions SET needs_human=1 WHERE id=?", (req.session_id,))
    conn.execute("UPDATE sessions SET updated_at=datetime('now','localtime')"
                 " WHERE id=?", (req.session_id,))
    conn.commit()

    return {"reply": reply, "engine": engine, "matched_knowledge": matched,
            "needs_human": bool(session["needs_human"] or needs_human),
            "error": error}


# ---------------------------------------------------------------- 评分与纠错
@router.post("/api/feedback")
def feedback(req: FeedbackRequest, conn=Depends(get_db)):
    msg = conn.execute("SELECT * FROM messages WHERE id=?",
                       (req.message_id,)).fetchone()
    if msg is None:
        raise HTTPException(404, "消息不存在")
    conn.execute("UPDATE messages SET rating=? WHERE id=?",
                 (req.rating, req.message_id))

    # 👎 + 纠错内容 → 写入训练中心（问题取该条回复前面最近一句来访者消息）
    if req.rating == -1 and req.correction:
        prev = conn.execute(
            "SELECT content FROM messages WHERE session_id=? AND role='user' AND id<?"
            " ORDER BY id DESC LIMIT 1", (msg["session_id"], req.message_id)).fetchone()
        question = prev["content"] if prev else ""
        conn.execute(
            "INSERT INTO corrections (question, bad_reply, corrected_reply, session_id)"
            " VALUES (?,?,?,?)",
            (question, msg["content"], req.correction, msg["session_id"]))
    conn.commit()
    return {"ok": True}


class CorrectionUpdate(BaseModel):
    active: int


@router.get("/api/corrections")
def list_corrections(conn=Depends(get_db)):
    return [{"id": r["id"], "question": r["question"], "bad_reply": r["bad_reply"],
             "corrected_reply": r["corrected_reply"], "session_id": r["session_id"],
             "active": r["active"], "created_at": r["created_at"]}
            for r in conn.execute("SELECT * FROM corrections ORDER BY id DESC")]


@router.put("/api/corrections/{cid}")
def toggle_correction(cid: int, req: CorrectionUpdate, conn=Depends(get_db)):
    cur = conn.execute("UPDATE corrections SET active=? WHERE id=?",
                       (req.active, cid))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "纠错记录不存在")
    return {"ok": True}


@router.delete("/api/corrections/{cid}")
def delete_correction(cid: int, conn=Depends(get_db)):
    cur = conn.execute("DELETE FROM corrections WHERE id=?", (cid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "纠错记录不存在")
    return {"ok": True}
