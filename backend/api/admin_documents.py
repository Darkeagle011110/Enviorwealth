"""
Admin Panel API — Document Corpus Management.
Upload, replace, list, and soft-delete RAG corpus documents.
All changes trigger automatic re-chunking and re-embedding.
"""

import os, shutil, hashlib
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models.database import get_db
from models.orm_models import KnowledgeDocument, KnowledgeChunk
from config.settings import settings

router = APIRouter()




def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── GET /api/admin/documents ──────────────────────────────────────────────────
@router.get("/documents")
async def list_documents(db: Session = Depends(get_db)):
    """List all active corpus documents with metadata."""
    docs = db.query(KnowledgeDocument).filter_by(is_active=True).order_by(
        KnowledgeDocument.created_at.desc()
    ).all()

    result = []
    for doc in docs:
        chunk_count = db.query(KnowledgeChunk).filter_by(document_id=doc.id).count()
        result.append({
            "id": str(doc.id),
            "title": doc.title,
            "version": doc.version,
            "effective_date": str(doc.effective_date) if doc.effective_date else None,
            "jurisdiction": doc.jurisdiction,
            "doc_type": doc.doc_type,
            "standard_body": doc.standard_body,
            "retrieval_date": str(doc.retrieval_date),
            "chunk_count": chunk_count,
            "source_url": doc.source_url,
            "created_at": str(doc.created_at),
        })
    return {"documents": result, "total": len(result)}


# ── POST /api/admin/documents/upload ─────────────────────────────────────────
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    version: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    jurisdiction: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None),
    standard_body: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a new document to the RAG corpus.
    Automatically triggers chunking + embedding (async task).
    """
    # Save file to disk
    upload_dir = settings.uploaded_docs_path
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    file_hash = _file_hash(file_path)

    # Check for duplicate
    existing = db.query(KnowledgeDocument).filter_by(file_hash=file_hash, is_active=True).first()
    if existing:
        os.remove(file_path)
        return {"message": "Document already exists in corpus", "document_id": str(existing.id)}

    # Create DB record
    doc = KnowledgeDocument(
        title=title,
        version=version,
        publication_date=None,
        effective_date=date.fromisoformat(effective_date) if effective_date else None,
        jurisdiction=jurisdiction,
        doc_type=doc_type,
        standard_body=standard_body,
        file_path=file_path,
        file_hash=file_hash,
        source_url=source_url,
        retrieval_date=date.today(),
        is_active=True,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Trigger async chunking + embedding
    # (In production this would be a Celery task; for Phase 1 we do it inline)
    try:
        from rag.chunker import chunk_document
        from rag.embedder import embed_and_store_chunks
        chunks = chunk_document(file_path, str(doc.id), title)
        await embed_and_store_chunks(chunks, str(doc.id), db)
        chunk_count = len(chunks)
        status = "indexed"
    except Exception as e:
        chunk_count = 0
        status = f"upload_ok_indexing_failed: {str(e)[:100]}"

    return {
        "document_id": str(doc.id),
        "title": title,
        "chunk_count": chunk_count,
        "status": status,
        "message": f"Document uploaded and {status}.",
    }


# ── PUT /api/admin/documents/{doc_id}/replace ─────────────────────────────────
@router.put("/documents/{doc_id}/replace")
async def replace_document(
    doc_id: str,
    file: UploadFile = File(...),
    version: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Replace an existing document with a new version.
    The old document is soft-deleted (archived, not erased).
    Old chunks are retained with superseded_by pointer; new chunks are indexed.
    """
    old_doc = db.query(KnowledgeDocument).filter_by(id=doc_id, is_active=True).first()
    if not old_doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Save new file
    upload_dir = settings.uploaded_docs_path
    os.makedirs(upload_dir, exist_ok=True)
    new_path = os.path.join(upload_dir, f"v_{file.filename}")
    with open(new_path, "wb") as f:
        content = await file.read()
        f.write(content)

    new_hash = _file_hash(new_path)

    # Create new doc record
    new_doc = KnowledgeDocument(
        title=old_doc.title,
        version=version or old_doc.version,
        jurisdiction=old_doc.jurisdiction,
        doc_type=old_doc.doc_type,
        standard_body=old_doc.standard_body,
        effective_date=date.fromisoformat(effective_date) if effective_date else old_doc.effective_date,
        file_path=new_path,
        file_hash=new_hash,
        source_url=old_doc.source_url,
        retrieval_date=date.today(),
        is_active=True,
    )
    db.add(new_doc)
    db.flush()

    # Soft-delete old doc
    old_doc.is_active = False
    old_doc.superseded_by = new_doc.id
    db.commit()
    db.refresh(new_doc)

    # Re-index new document
    try:
        from rag.chunker import chunk_document
        from rag.embedder import embed_and_store_chunks
        chunks = chunk_document(new_path, str(new_doc.id), new_doc.title)
        await embed_and_store_chunks(chunks, str(new_doc.id), db)
        chunk_count = len(chunks)
        status = "re-indexed"
    except Exception as e:
        chunk_count = 0
        status = f"upload_ok_indexing_failed: {str(e)[:100]}"

    return {
        "new_document_id": str(new_doc.id),
        "supersedes": doc_id,
        "chunk_count": chunk_count,
        "status": status,
        "message": f"Document replaced and {status}. Previous version archived.",
    }


# ── DELETE /api/admin/documents/{doc_id} ──────────────────────────────────────
@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
):
    """Soft-delete: mark document as inactive (removed from active retrieval)."""
    doc = db.query(KnowledgeDocument).filter_by(id=doc_id, is_active=True).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.is_active = False
    db.commit()

    return {"message": f"Document '{doc.title}' removed from active retrieval (archived, not deleted)."}
