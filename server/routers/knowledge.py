"""知识库 CRUD 与批量导入。"""
import json

from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from ..db import get_db
from ..schemas import KnowledgeImportIn, KnowledgeIn

router = APIRouter()


def _out(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "title": row["title"], "content": row["content"],
            "tags": json.loads(row["tags"] or "[]"),
            "category": row["category"] if "category" in row.keys() else "未分组"}


@router.get("/api/knowledge")
def list_knowledge(q: str = "", category: str = "", conn=Depends(get_db)):
    clauses = []
    params = []
    if q:
        like = f"%{q}%"
        clauses.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
        params.extend([like, like, like])
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = conn.execute("SELECT * FROM knowledge" + where + " ORDER BY id DESC", params).fetchall()
    return [_out(r) for r in rows]


@router.post("/api/knowledge")
def create_knowledge(req: KnowledgeIn, conn=Depends(get_db)):
    cur = conn.execute("INSERT INTO knowledge (title, content, tags, category) VALUES (?,?,?,?)",
                       (req.title, req.content, json.dumps(req.tags, ensure_ascii=False),
                        req.category.strip() or "未分组"))
    conn.commit()
    return _out(conn.execute("SELECT * FROM knowledge WHERE id=?", (cur.lastrowid,)).fetchone())


@router.put("/api/knowledge/{kid}")
def update_knowledge(kid: int, req: KnowledgeIn, conn=Depends(get_db)):
    cur = conn.execute("UPDATE knowledge SET title=?, content=?, tags=?, category=? WHERE id=?",
                       (req.title, req.content,
                        json.dumps(req.tags, ensure_ascii=False),
                        req.category.strip() or "未分组", kid))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "知识不存在")
    return _out(conn.execute("SELECT * FROM knowledge WHERE id=?", (kid,)).fetchone())


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
        category = parts[3].strip() if len(parts) > 3 and parts[3].strip() else "未分组"
        conn.execute("INSERT INTO knowledge (title, content, tags, category) VALUES (?,?,?,?)",
                     (parts[0], parts[1], json.dumps(tags, ensure_ascii=False), category))
        ok += 1
    conn.commit()
    return {"imported": ok, "failed": fail}


@router.get("/api/knowledge/categories")
def list_categories(conn=Depends(get_db)):
    rows = conn.execute("SELECT DISTINCT category FROM knowledge WHERE category IS NOT NULL AND category <> '' ORDER BY category").fetchall()
    categories = [r["category"] for r in rows]
    if "未分组" not in categories:
        categories.insert(0, "未分组")
    return categories
