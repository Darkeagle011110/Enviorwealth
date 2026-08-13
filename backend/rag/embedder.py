"""
Embedder — generates embeddings and stores them in Qdrant (vectors) and MongoDB (metadata).
Supports OpenAI text-embedding-3-small (primary) with local
sentence-transformers fallback.
"""

from __future__ import annotations
import logging
import uuid
from typing import List

from rag.chunker import DocumentChunk
from config.settings import settings
from models.mongodb import get_database
from models.qdrant_client import get_async_qdrant
from qdrant_client.http.models import PointStruct

logger = logging.getLogger(__name__)


async def _embed_openai(texts: List[str]) -> List[List[float]]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        input=texts,
        model=settings.embedding_model,
    )
    return [item.embedding for item in response.data]


def _embed_local(texts: List[str]) -> List[List[float]]:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(settings.local_embedding_model)
    return model.encode(texts).tolist()


async def _get_embeddings(texts: List[str]) -> List[List[float]]:
    if settings.openai_api_key and settings.embedding_provider == "openai":
        try:
            return await _embed_openai(texts)
        except Exception as e:
            logger.warning(f"OpenAI embedding failed, falling back to local: {e}")
    return _embed_local(texts)


async def embed_and_store_chunks(
    chunks: List[DocumentChunk],
    document_id: str,
    title: str = "",
    is_active: bool = True,
    batch_size: int = 50,
) -> int:
    """
    Embed document chunks and store them in Qdrant (vectors) and MongoDB (text/metadata).
    Returns the number of chunks stored.
    """
    if not chunks:
        return 0

    db = get_database()
    qdrant = get_async_qdrant()
    collection_name = settings.qdrant_collection_name
    
    stored = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.embed_text for c in batch]

        try:
            embeddings = await _get_embeddings(texts)
        except Exception as e:
            logger.error(f"Embedding batch {i} failed: {e}")
            raise

        points = []
        mongo_docs = []
        
        for chunk, embedding in zip(batch, embeddings):
            chunk_id = str(uuid.uuid4())
            
            # MongoDB doc for reference
            mongo_docs.append({
                "id": chunk_id,
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "doc_summary": chunk.doc_summary,
                "metadata": chunk.metadata
            })
            
            # Qdrant point
            payload = {
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "doc_summary": chunk.doc_summary,
                "metadata": chunk.metadata,
                "document_title": title,
                "is_active": is_active
            }
            
            points.append(
                PointStruct(id=chunk_id, vector=embedding, payload=payload)
            )
            
        # Store in Qdrant
        await qdrant.upsert(
            collection_name=collection_name,
            points=points
        )
        
        # Store in MongoDB (for reference/admin display)
        if mongo_docs:
            from datetime import datetime, timezone
            for doc in mongo_docs:
                doc["created_at"] = datetime.now(timezone.utc)
            await db.knowledge_chunks.insert_many(mongo_docs)
            
        stored += len(batch)

    logger.info(f"Stored {stored} chunks for document {document_id}")
    return stored
