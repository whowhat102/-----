"""知识库 CRUD 与批量导入。"""
import json

from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from ..db import get_db
from ..schemas import KnowledgeImportIn, KnowledgeIn

router = APIRouter()


def _out(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "content": row["content"],
            "tags": json.loads(row["tags"] or "[]")}


@router.get("/api/knowledge")
def list_knowledge(q: str = "", conn=Depends(get_db)):
    if q:
        like = f"%{q}%"
        rows = conn.execute(
            "SELECT * FROM knowledge WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?"
            " ORDER BY id DESC", (like, like, like)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM knowledge ORDER BY id DESC").fetchall()
    return [_out(r) for r in rows]


@router.post("/api/knowledge")
def create_knowledge(req: KnowledgeIn, conn=Depends(get_db)):
    cur = conn.execute("INSERT INTO knowledge (title, content, tags) VALUES (?,?,?)",
                       (req.title, req.content, json.dumps(req.tags, ensure_ascii=False)))
    conn.commit()
    return _out(conn.execute("SELECT * FROM knowledge WHERE id=?",
                             (cur.lastrowid,)).fetchone())


@router.put("/api/knowledge/{kid}")
def update_knowledge(kid: int, req: KnowledgeIn, conn=Depends(get_db)):
    cur = conn.execute("UPDATE knowledge SET title=?, content=?, tags=? WHERE id=?",
                       (req.title, req.content,
                        json.dumps(req.tags, ensure_ascii=False), kid))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "知识不存在")
    return {"ok": True}


@router.delete("/api/knowledge/{kid}")
def delete_knowledge(kid: int, conn=Depends(get_db)):
    cur = conn.execute("DELETE FROM knowledge WHERE id=?", (kid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "知识不存在")
    return {"ok": True}


@router.post("/api/knowledge/import")
def import_knowledge(req: KnowledgeImportIn, conn=Depends(get_db)):
    """每行一条：`标题 | 内容 | 标签(逗号分隔，可选)`。"""
    ok, fail = 0, 0
    for line in req.text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            fail += 1
            continue
        tags = [t.strip() for t in parts[2].split("，")] if len(parts) > 2 and parts[2] else []
        tags = [t for sub in tags for t in sub.split(",") if t.strip()]
        conn.execute("INSERT INTO knowledge (title, content, tags) VALUES (?,?,?)",
                     (parts[0], parts[1], json.dumps(tags, ensure_ascii=False)))
        ok += 1
    conn.commit()
    return {"imported": ok, "failed": fail}
