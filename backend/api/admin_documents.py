"""
Admin Panel API — Document Corpus Management.
Upload, replace, list, and soft-delete RAG corpus documents.
All changes trigger automatic re-chunking and re-embedding.
"""

import os, shutil, hashlib
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from models.mongodb import get_db
from models.schemas import KnowledgeDocumentDoc
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
async def list_documents(db: AsyncIOMotorDatabase = Depends(get_db)):
    """List all active corpus documents with metadata."""
    cursor = db.knowledge_documents.find({"is_active": True}).sort("created_at", -1)
    docs = await cursor.to_list(length=None)

    result = []
    for doc in docs:
        chunk_count = await db.knowledge_chunks.count_documents({"document_id": doc["id"]})
        
        created_at = doc.get("created_at")
        
        result.append({
            "id": doc["id"],
            "title": doc.get("title"),
            "version": doc.get("version"),
            "effective_date": doc.get("effective_date"),
            "jurisdiction": doc.get("jurisdiction"),
            "doc_type": doc.get("doc_type"),
            "standard_body": doc.get("standard_body"),
            "retrieval_date": doc.get("retrieval_date"),
            "chunk_count": chunk_count,
            "source_url": doc.get("source_url"),
            "created_at": created_at.isoformat() if created_at else None,
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
    db: AsyncIOMotorDatabase = Depends(get_db),
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
    existing = await db.knowledge_documents.find_one({"file_hash": file_hash, "is_active": True})
    if existing:
        os.remove(file_path)
        return {"message": "Document already exists in corpus", "document_id": existing["id"]}

    # Create DB record
    doc_record = KnowledgeDocumentDoc(
        title=title,
        version=version,
        publication_date=None,
        effective_date=effective_date,
        jurisdiction=jurisdiction,
        doc_type=doc_type,
        standard_body=standard_body,
        file_path=file_path,
        file_hash=file_hash,
        source_url=source_url,
        retrieval_date=str(date.today()),
        is_active=True,
    )
    await db.knowledge_documents.insert_one(doc_record.model_dump())

    # Trigger async chunking + embedding
    # (In production this would be a Celery task; for Phase 1 we do it inline)
    try:
        from rag.chunker import chunk_document
        from rag.embedder import embed_and_store_chunks
        chunks = chunk_document(file_path, doc_record.id, title)
        await embed_and_store_chunks(chunks, doc_record.id, title, True)
        chunk_count = len(chunks)
        status = "indexed"
    except Exception as e:
        chunk_count = 0
        status = f"upload_ok_indexing_failed: {str(e)[:100]}"

    return {
        "document_id": doc_record.id,
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
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Replace an existing document with a new version.
    The old document is soft-deleted (archived, not erased).
    Old chunks are retained with superseded_by pointer; new chunks are indexed.
    """
    old_doc_dict = await db.knowledge_documents.find_one({"id": doc_id, "is_active": True})
    if not old_doc_dict:
        raise HTTPException(status_code=404, detail="Document not found")
        
    old_doc = KnowledgeDocumentDoc(**old_doc_dict)

    # Save new file
    upload_dir = settings.uploaded_docs_path
    os.makedirs(upload_dir, exist_ok=True)
    new_path = os.path.join(upload_dir, f"v_{file.filename}")
    with open(new_path, "wb") as f:
        content = await file.read()
        f.write(content)

    new_hash = _file_hash(new_path)

    # Create new doc record
    new_doc = KnowledgeDocumentDoc(
        title=old_doc.title,
        version=version or old_doc.version,
        jurisdiction=old_doc.jurisdiction,
        doc_type=old_doc.doc_type,
        standard_body=old_doc.standard_body,
        effective_date=effective_date or old_doc.effective_date,
        file_path=new_path,
        file_hash=new_hash,
        source_url=old_doc.source_url,
        retrieval_date=str(date.today()),
        is_active=True,
    )
    await db.knowledge_documents.insert_one(new_doc.model_dump())

    # Soft-delete old doc
    await db.knowledge_documents.update_one(
        {"id": doc_id},
        {"$set": {"is_active": False, "superseded_by": new_doc.id}}
    )
    
    # Soft delete Qdrant points
    try:
        from models.qdrant_client import get_async_qdrant
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        qdrant = get_async_qdrant()
        
        # We find points by document_id and set is_active=False
        # Note: In Qdrant, we can update payload by filter
        await qdrant.set_payload(
            collection_name=settings.qdrant_collection_name,
            payload={"is_active": False},
            points=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]
            )
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to soft delete old Qdrant chunks: {e}")

    # Re-index new document
    try:
        from rag.chunker import chunk_document
        from rag.embedder import embed_and_store_chunks
        chunks = chunk_document(new_path, new_doc.id, new_doc.title)
        await embed_and_store_chunks(chunks, new_doc.id, new_doc.title, True)
        chunk_count = len(chunks)
        status = "re-indexed"
    except Exception as e:
        chunk_count = 0
        status = f"upload_ok_indexing_failed: {str(e)[:100]}"

    return {
        "new_document_id": new_doc.id,
        "supersedes": doc_id,
        "chunk_count": chunk_count,
        "status": status,
        "message": f"Document replaced and {status}. Previous version archived.",
    }


# ── DELETE /api/admin/documents/{doc_id} ──────────────────────────────────────
@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Soft-delete: mark document as inactive (removed from active retrieval)."""
    doc_dict = await db.knowledge_documents.find_one({"id": doc_id, "is_active": True})
    if not doc_dict:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.knowledge_documents.update_one(
        {"id": doc_id},
        {"$set": {"is_active": False}}
    )
    
    try:
        from models.qdrant_client import get_async_qdrant
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        qdrant = get_async_qdrant()
        
        await qdrant.set_payload(
            collection_name=settings.qdrant_collection_name,
            payload={"is_active": False},
            points=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]
            )
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to soft delete old Qdrant chunks: {e}")

    return {"message": f"Document '{doc_dict.get('title')}' removed from active retrieval (archived, not deleted)."}
