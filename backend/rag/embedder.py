"""
Embedder — generates embeddings and stores them in pgvector.
Supports OpenAI text-embedding-3-large (primary) with local
sentence-transformers fallback.
"""

from __future__ import annotations
import logging
from typing import List
from sqlalchemy.orm import Session

from rag.chunker import DocumentChunk
from models.orm_models import KnowledgeChunk
from config.settings import settings

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
    db: Session,
    batch_size: int = 50,
) -> int:
    """
    Embed document chunks and store them in the pgvector table.
    Returns the number of chunks stored.
    """
    if not chunks:
        return 0

    stored = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.embed_text for c in batch]

        try:
            embeddings = await _get_embeddings(texts)
        except Exception as e:
            logger.error(f"Embedding batch {i} failed: {e}")
            raise

        for chunk, embedding in zip(batch, embeddings):
            record = KnowledgeChunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                doc_summary=chunk.doc_summary,
                embedding=embedding,
                metadata_=chunk.metadata,
            )
            db.merge(record)
            stored += 1

    db.commit()
    logger.info(f"Stored {stored} chunks for document {document_id}")
    return stored
