"""配置类 CRUD：人设 / 话术模板 / 场景 / 人群。"""
import json

from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from ..db import get_db
from ..schemas import AudienceIn, PersonaIn, ScenarioIn, ScriptIn

router = APIRouter()


def _persona_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "name": row["name"], "identity": row["identity"],
        "greeting": row["greeting"],
        "catchphrases": json.loads(row["catchphrases"] or "[]"),
        "emoji_style": row["emoji_style"],
        "colloquial": row["colloquial"], "warmth": row["warmth"],
        "formality": row["formality"], "is_default": row["is_default"],
    }


# ---------------------------------------------------------------- 人设
@router.get("/api/personas")
def list_personas(conn: sqlite3.Connection = Depends(get_db)):
    return [_persona_out(r) for r in
            conn.execute("SELECT * FROM personas ORDER BY is_default DESC, id")]


@router.post("/api/personas")
def create_persona(req: PersonaIn, conn=Depends(get_db)):
    if req.is_default:
        conn.execute("UPDATE personas SET is_default = 0")
    cur = conn.execute(
        "INSERT INTO personas (name, identity, greeting, catchphrases, emoji_style,"
        " colloquial, warmth, formality, is_default) VALUES (?,?,?,?,?,?,?,?,?)",
        (req.name, req.identity, req.greeting,
         json.dumps(req.catchphrases, ensure_ascii=False), req.emoji_style,
         req.colloquial, req.warmth, req.formality, req.is_default))
    conn.commit()
    return _persona_out(conn.execute("SELECT * FROM personas WHERE id=?",
                                     (cur.lastrowid,)).fetchone())


@router.put("/api/personas/{pid}")
def update_persona(pid: int, req: PersonaIn, conn=Depends(get_db)):
    if conn.execute("SELECT 1 FROM personas WHERE id=?", (pid,)).fetchone() is None:
        raise HTTPException(404, "人设不存在")
    if req.is_default:
        conn.execute("UPDATE personas SET is_default = 0")
    conn.execute(
        "UPDATE personas SET name=?, identity=?, greeting=?, catchphrases=?,"
        " emoji_style=?, colloquial=?, warmth=?, formality=?, is_default=? WHERE id=?",
        (req.name, req.identity, req.greeting,
         json.dumps(req.catchphrases, ensure_ascii=False), req.emoji_style,
         req.colloquial, req.warmth, req.formality, req.is_default, pid))
    conn.commit()
    return _persona_out(conn.execute("SELECT * FROM personas WHERE id=?", (pid,)).fetchone())


@router.delete("/api/personas/{pid}")
def delete_persona(pid: int, conn=Depends(get_db)):
    cur = conn.execute("DELETE FROM personas WHERE id=?", (pid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "人设不存在")
    return {"ok": True}


# ---------------------------------------------------------------- 话术模板
@router.get("/api/scripts")
def list_scripts(conn=Depends(get_db)):
    rows = conn.execute("SELECT * FROM scripts ORDER BY id").fetchall()
    out = [{"id": r["id"], "stage": r["stage"], "name": r["name"],
            "content": r["content"]} for r in rows]
    return out


@router.post("/api/scripts")
def create_script(req: ScriptIn, conn=Depends(get_db)):
    cur = conn.execute("INSERT INTO scripts (stage, name, content) VALUES (?,?,?)",
                       (req.stage, req.name, req.content))
    conn.commit()
    r = conn.execute("SELECT * FROM scripts WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"id": r["id"], "stage": r["stage"], "name": r["name"], "content": r["content"]}


@router.put("/api/scripts/{sid}")
def update_script(sid: int, req: ScriptIn, conn=Depends(get_db)):
    cur = conn.execute("UPDATE scripts SET stage=?, name=?, content=? WHERE id=?",
                       (req.stage, req.name, req.content, sid))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "话术不存在")
    return {"ok": True}


@router.delete("/api/scripts/{sid}")
def delete_script(sid: int, conn=Depends(get_db)):
    cur = conn.execute("DELETE FROM scripts WHERE id=?", (sid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "话术不存在")
    return {"ok": True}


# ---------------------------------------------------------------- 场景
@router.get("/api/scenarios")
def list_scenarios(conn=Depends(get_db)):
    return [{"id": r["id"], "name": r["name"], "description": r["description"],
             "strategy": r["strategy"]}
            for r in conn.execute("SELECT * FROM scenarios ORDER BY id")]


@router.post("/api/scenarios")
def create_scenario(req: ScenarioIn, conn=Depends(get_db)):
    cur = conn.execute("INSERT INTO scenarios (name, description, strategy) VALUES (?,?,?)",
                       (req.name, req.description, req.strategy))
    conn.commit()
    return {"id": cur.lastrowid, **req.model_dump()}


@router.put("/api/scenarios/{sid}")
def update_scenario(sid: int, req: ScenarioIn, conn=Depends(get_db)):
    cur = conn.execute("UPDATE scenarios SET name=?, description=?, strategy=? WHERE id=?",
                       (req.name, req.description, req.strategy, sid))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "场景不存在")
    return {"ok": True}


@router.delete("/api/scenarios/{sid}")
def delete_scenario(sid: int, conn=Depends(get_db)):
    cur = conn.execute("DELETE FROM scenarios WHERE id=?", (sid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "场景不存在")
    return {"ok": True}


# ---------------------------------------------------------------- 人群
@router.get("/api/audiences")
def list_audiences(conn=Depends(get_db)):
    return [{"id": r["id"], "name": r["name"], "description": r["description"],
             "tone_guide": r["tone_guide"]}
            for r in conn.execute("SELECT * FROM audiences ORDER BY id")]


@router.post("/api/audiences")
def create_audience(req: AudienceIn, conn=Depends(get_db)):
    cur = conn.execute("INSERT INTO audiences (name, description, tone_guide) VALUES (?,?,?)",
                       (req.name, req.description, req.tone_guide))
    conn.commit()
    return {"id": cur.lastrowid, **req.model_dump()}


@router.put("/api/audiences/{aid}")
def update_audience(aid: int, req: AudienceIn, conn=Depends(get_db)):
    cur = conn.execute("UPDATE audiences SET name=?, description=?, tone_guide=? WHERE id=?",
                       (req.name, req.description, req.tone_guide, aid))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "人群不存在")
    return {"ok": True}


@router.delete("/api/audiences/{aid}")
def delete_audience(aid: int, conn=Depends(get_db)):
    cur = conn.execute("DELETE FROM audiences WHERE id=?", (aid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "人群不存在")
    return {"ok": True}
