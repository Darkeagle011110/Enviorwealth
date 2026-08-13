"""
RAG Retriever — Qdrant cosine-similarity search.

Replaces pgvector retriever. Performs vector similarity search against 
the Qdrant collection, filtering for `is_active=True`.
"""
from __future__ import annotations
import logging
from typing import List, Optional

from pydantic import BaseModel

from config.settings import settings
from models.qdrant_client import get_async_qdrant
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)


class Chunk(BaseModel):
    chunk_id: str
    document_title: str
    effective_date: str
    text: str
    score: Optional[float] = None       # cosine similarity score


class Retriever:
    """
    Qdrant-backed retriever.
    """

    async def _embed_query(self, query: str) -> Optional[List[float]]:
        """Embed a query string using the configured embedding provider."""
        try:
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
        Perform vector search against Qdrant.

        Returns up to top_k Chunk objects, sorted by relevance.
        Returns [] if embedding service or Qdrant is unavailable.
        """
        embedding = await self._embed_query(query)
        if embedding is None:
            logger.warning("Could not embed query — returning empty retrieval results.")
            return []

        try:
            qdrant = get_async_qdrant()
            
            # Search Qdrant, filtering for active documents
            results = await qdrant.search(
                collection_name=settings.qdrant_collection_name,
                query_vector=embedding,
                limit=top_k,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="is_active",
                            match=MatchValue(value=True)
                        )
                    ]
                )
            )
            
            chunks = []
            for hit in results:
                payload = hit.payload or {}
                chunks.append(
                    Chunk(
                        chunk_id=str(hit.id),
                        document_title=payload.get("document_title", "Unknown"),
                        effective_date=str(payload.get("effective_date", "unknown")),
                        text=payload.get("content", ""),
                        score=hit.score,
                    )
                )
                
            logger.info(f"Retrieved {len(chunks)} chunks for query: {query[:60]}")
            return chunks

        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []
