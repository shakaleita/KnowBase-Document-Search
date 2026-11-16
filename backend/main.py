APP_TITLE = 'KnowBase'
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
import sqlite3, os
from contextlib import contextmanager
from pathlib import Path

DB = Path(os.environ.get("APP_DB", str(Path(__file__).parent / "app.db")))
app = FastAPI(title=APP_TITLE, version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])

@contextmanager
def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def rows(cursor):
    return [dict(r) for r in cursor.fetchall()]

def setup(sql):
    with db() as con:
        con.executescript(sql)

@app.get("/api/health")
def health():
    return {"ok": True, "service": APP_TITLE}


setup("""CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,source TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT 'General');CREATE VIRTUAL TABLE IF NOT EXISTS doc_fts USING fts5(title,body,content='documents',content_rowid='id');CREATE TRIGGER IF NOT EXISTS doc_ai AFTER INSERT ON documents BEGIN INSERT INTO doc_fts(rowid,title,body) VALUES(new.id,new.title,new.body);END;""")
setup("""CREATE TRIGGER IF NOT EXISTS doc_ad AFTER DELETE ON documents BEGIN
 INSERT INTO doc_fts(doc_fts,rowid,title,body) VALUES('delete',old.id,old.title,old.body); END;
 CREATE TRIGGER IF NOT EXISTS doc_au AFTER UPDATE ON documents BEGIN
 INSERT INTO doc_fts(doc_fts,rowid,title,body) VALUES('delete',old.id,old.title,old.body);
 INSERT INTO doc_fts(rowid,title,body) VALUES(new.id,new.title,new.body); END;""")
class Document(BaseModel):
    title:str
    body:str
    source:str=""
    category:str="General"
@app.get('/api/items')
def items():
    with db() as c:return rows(c.execute('SELECT id,title,body,source,category FROM documents ORDER BY id DESC'))
@app.post('/api/items',status_code=201)
def create_item(d:Document):
    if not d.title.strip() or not d.body.strip():raise HTTPException(422,'Document requires title and body')
    with db() as c:
        cur=c.execute('INSERT INTO documents(title,body,source,category) VALUES(?,?,?,?)',(d.title,d.body,d.source,d.category))
        return dict(c.execute('SELECT * FROM documents WHERE id=?',(cur.lastrowid,)).fetchone())
@app.get('/api/search')
def search(q:str):
    if not q.strip():return []
    terms=' OR '.join('"'+t.replace('"','')+'"' for t in q.split()[:8] if t.replace('"',''))
    if not terms:return []
    with db() as c:
        return rows(c.execute("SELECT d.id,d.title,d.source,d.category,snippet(doc_fts,1,'[',']','...',18) AS snippet FROM doc_fts JOIN documents d ON d.id=doc_fts.rowid WHERE doc_fts MATCH ? ORDER BY bm25(doc_fts) LIMIT 20",(terms,)))
@app.get('/api/summary')
def summary():
    with db() as c:return rows(c.execute('SELECT category AS label, COUNT(*) AS value FROM documents GROUP BY category'))


# v0.3: editable full-text knowledge base
@app.put('/api/items/{document_id}')
def edit_document(document_id: int, doc: Document):
    if not doc.title.strip() or not doc.body.strip():
        raise HTTPException(422,'Document requires title and body')
    with db() as con:
        prior=con.execute('SELECT * FROM documents WHERE id=?',(document_id,)).fetchone()
        if not prior:raise HTTPException(404,'Document not found')
        con.execute('INSERT INTO document_revisions(document_id,title,body,source,category) VALUES(?,?,?,?,?)',
                    (document_id,prior['title'],prior['body'],prior['source'],prior['category']))
        cur=con.execute('UPDATE documents SET title=?,body=?,source=?,category=? WHERE id=?',
           (doc.title,doc.body,doc.source,doc.category,document_id))
        if not cur.rowcount:
            raise HTTPException(404,'Document not found')
        return dict(con.execute('SELECT * FROM documents WHERE id=?',(document_id,)).fetchone())

@app.delete('/api/items/{document_id}',status_code=204)
def delete_document(document_id: int):
    with db() as con:
        if not con.execute('DELETE FROM documents WHERE id=?',(document_id,)).rowcount:
            raise HTTPException(404,'Document not found')


setup("""CREATE TABLE IF NOT EXISTS document_revisions(
 id INTEGER PRIMARY KEY,document_id INTEGER NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,
 source TEXT NOT NULL,category TEXT NOT NULL,changed_at TEXT DEFAULT CURRENT_TIMESTAMP);""")

@app.get('/api/documents/{document_id}/history')
def document_history(document_id:int):
    with db() as con:
        if not con.execute('SELECT 1 FROM documents WHERE id=?',(document_id,)).fetchone():
            raise HTTPException(404,'Document not found')
        return rows(con.execute('SELECT * FROM document_revisions WHERE document_id=? ORDER BY id DESC',(document_id,)))

from security import install_auth
install_auth(app,DB)
