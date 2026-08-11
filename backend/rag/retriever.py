"""
RAG Retriever — pgvector cosine-similarity search.

G1 FIX: Replaces the mock retriever that returned a single hardcoded chunk.
Now performs real vector similarity search against the knowledge_chunks table
using pgvector's cosine distance operator (<=>).

Fall-through behavior:
  - If embeddings are unavailable → returns []  (triggers unanswerable logging)
  - If DB is unavailable         → returns []  (triggers unanswerable logging)
  - Never returns fabricated mock data in production code paths.
"""
from __future__ import annotations
import logging
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Chunk(BaseModel):
    chunk_id: str
    document_title: str
    effective_date: str
    text: str
    score: Optional[float] = None       # cosine similarity score


class Retriever:
    """
    pgvector-backed retriever.
    Uses cosine similarity on the embed_text embeddings stored in knowledge_chunks.
    """

    async def _embed_query(self, query: str) -> Optional[List[float]]:
        """Embed a query string using the configured embedding provider."""
        try:
            from config.settings import settings

            if settings.openai_api_key and settings.embedding_provider == "openai":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                response = await client.embeddings.create(
                    input=[query],
                    model=settings.embedding_model,
                )
                return response.data[0].embedding

            # Local fallback
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(settings.local_embedding_model)
            vectors = model.encode([query])
            return vectors[0].tolist()

        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            return None

    async def search(self, query: str, top_k: int = 5) -> List[Chunk]:
        """
        Perform cosine-similarity search against the pgvector knowledge_chunks table.

        Returns up to top_k Chunk objects, sorted by relevance.
        Returns [] if the DB or embedding service is unavailable.
        """
        embedding = await self._embed_query(query)
        if embedding is None:
            logger.warning("Could not embed query — returning empty retrieval results.")
            return []

        try:
            from models.database import SessionLocal
            from models.orm_models import KnowledgeChunk, KnowledgeDocument

            db = SessionLocal()
            try:
                # pgvector cosine distance: <=> operator (lower = more similar)
                # We cast the embedding list to the vector type.
                from sqlalchemy import text as sql_text

                vector_str = "[" + ",".join(str(v) for v in embedding) + "]"

                rows = db.execute(
                    sql_text(
                        """
                        SELECT
                            kc.id::text          AS chunk_id,
                            kd.title             AS document_title,
                            kd.effective_date::text AS effective_date,
                            kc.content           AS text,
                            1 - (kc.embedding <=> CAST(:vec AS vector)) AS score
                        FROM knowledge_chunks kc
                        JOIN knowledge_documents kd ON kd.id = kc.document_id
                        WHERE kd.is_active = true
                          AND kc.embedding IS NOT NULL
                        ORDER BY kc.embedding <=> CAST(:vec AS vector)
                        LIMIT :top_k
                        """
                    ),
                    {"vec": vector_str, "top_k": top_k},
                ).fetchall()

                chunks = [
                    Chunk(
                        chunk_id=row.chunk_id,
                        document_title=row.document_title,
                        effective_date=str(row.effective_date or "unknown"),
                        text=row.text,
                        score=float(row.score),
                    )
                    for row in rows
                ]
                logger.info(f"Retrieved {len(chunks)} chunks for query: {query[:60]}")
                return chunks

            finally:
                db.close()

        except Exception as e:
            logger.error(f"pgvector search failed: {e}")
            return []
