"""
Qdrant Cloud client — replaces pgvector for all vector embedding storage/search.

Provides:
  - A single QdrantClient instance (app-lifetime singleton)
  - `get_qdrant()` helper to access the client
  - `ensure_collection()` called at startup to create the collection if it
    doesn't already exist, configured for cosine similarity (RAG use case)

Vector dimensions: 1536 — matches text-embedding-3-small (MVP default).
Fall back to 384 if using the local all-MiniLM-L6-v2 sentence-transformers model.
"""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    HnswConfigDiff,
    PayloadSchemaType,
)

from config.settings import settings

logger = logging.getLogger(__name__)

# ── Singleton instances ───────────────────────────────────────────────────────
_sync_client: QdrantClient | None = None
_async_client: AsyncQdrantClient | None = None


def get_qdrant() -> QdrantClient:
    """Return the synchronous Qdrant client singleton."""
    global _sync_client
    if _sync_client is None:
        _sync_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    return _sync_client


def get_async_qdrant() -> AsyncQdrantClient:
    """Return the async Qdrant client singleton."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    return _async_client


async def close_qdrant():
    """Call at application shutdown."""
    global _async_client, _sync_client
    if _async_client:
        await _async_client.close()
        _async_client = None
    _sync_client = None
    logger.info("Qdrant clients closed.")


async def ensure_collection():
    """
    Idempotently ensure the Qdrant collection exists with correct config.
    Called once at app startup.

    Uses HNSW approximate nearest-neighbour index with cosine similarity.
    Vector size matches the embedding model configured in settings.
    """
    client = get_async_qdrant()
    collection_name = settings.qdrant_collection_name
    vector_size = settings.qdrant_vector_size

    try:
        existing = await client.get_collection(collection_name)
        existing_size = existing.config.params.vectors.size
        if existing_size != vector_size:
            logger.warning(
                f"Qdrant collection '{collection_name}' exists with vector size "
                f"{existing_size}, but settings specify {vector_size}. "
                f"Using existing collection — update QDRANT_VECTOR_SIZE to match."
            )
        else:
            logger.info(
                f"Qdrant collection '{collection_name}' already exists "
                f"(size={existing_size}). Skipping creation."
            )
        return
    except Exception:
        # Collection does not exist — create it
        pass

    await client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
        hnsw_config=HnswConfigDiff(
            m=16,              # number of edges per node (higher = more accurate)
            ef_construct=100,  # size of dynamic candidate list during indexing
        ),
    )
    
    # Create payload index for the boolean 'is_active' filter
    await client.create_payload_index(
        collection_name=collection_name,
        field_name="is_active",
        field_schema=PayloadSchemaType.BOOL,
    )
    
    logger.info(
        f"Created Qdrant collection '{collection_name}' "
        f"(size={vector_size}, distance=COSINE) and payload indices."
    )
