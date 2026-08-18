"""
reindex_qdrant.py — Re-embed all knowledge base documents using fastembed (384-dim).

This script is needed when switching embedding providers (e.g. from OpenAI 1536-dim
to fastembed 384-dim). It:

  1. Deletes the old Qdrant collection (dimension mismatch means it must be recreated)
  2. Recreates the collection with the correct vector size from settings
  3. Re-reads every chunk stored in MongoDB (knowledge_chunks collection)
  4. Re-embeds them using the local fastembed model (BAAI/bge-small-en-v1.5)
  5. Upserts the new 384-dim vectors into the fresh Qdrant collection

Usage (run from backend/ with venv active):
    venv\\Scripts\\python.exe reindex_qdrant.py

Takes ~1-5 minutes depending on how many documents are in the knowledge base.
Safe to re-run — it always starts fresh.
"""

import asyncio
import logging
import sys
import os

# Ensure the backend package root is on the path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 32   # chunks per embedding batch


async def main():
    from config.settings import settings
    from models.mongodb import get_database
    from models.qdrant_client import get_async_qdrant
    from qdrant_client.http.models import VectorParams, Distance, HnswConfigDiff, PointStruct, PayloadSchemaType

    logger.info("=" * 60)
    logger.info("Qdrant Re-indexing Script")
    logger.info(f"  Embedding provider : {settings.embedding_provider}")
    logger.info(f"  Local model        : {settings.local_embedding_model}")
    logger.info(f"  Vector size        : {settings.qdrant_vector_size}")
    logger.info(f"  Qdrant collection  : {settings.qdrant_collection_name}")
    logger.info("=" * 60)

    qdrant = get_async_qdrant()
    db = get_database()
    collection_name = settings.qdrant_collection_name
    vector_size = settings.qdrant_vector_size

    # ── Step 1: Delete old collection ────────────────────────────────────────
    logger.info(f"Step 1/4 — Deleting old collection '{collection_name}' (if exists)...")
    try:
        await qdrant.delete_collection(collection_name)
        logger.info(f"  ✅ Deleted '{collection_name}'.")
    except Exception as e:
        logger.warning(f"  Collection may not exist yet (OK): {e}")

    # ── Step 2: Recreate collection ───────────────────────────────────────────
    logger.info(f"Step 2/4 — Creating new collection '{collection_name}' ({vector_size}-dim)...")
    await qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
        hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
    )
    await qdrant.create_payload_index(
        collection_name=collection_name,
        field_name="is_active",
        field_schema=PayloadSchemaType.BOOL,
    )
    logger.info(f"  ✅ Collection created with payload indices.")

    # ── Step 3: Load all chunks from MongoDB ──────────────────────────────────
    logger.info("Step 3/4 — Loading all knowledge chunks from MongoDB...")
    all_chunks = await db.knowledge_chunks.find({}).to_list(length=None)
    total = len(all_chunks)
    logger.info(f"  Found {total} chunks to re-embed.")

    if total == 0:
        logger.warning(
            "  ⚠️  No chunks found in MongoDB. "
            "Upload documents via the Admin Panel first, then run this script."
        )
        return

    # ── Step 4: Re-embed and upsert ───────────────────────────────────────────
    logger.info("Step 4/4 — Re-embedding and upserting into Qdrant...")

    # Load fastembed model (cached for the whole script run)
    from fastembed import TextEmbedding
    logger.info(f"  Loading fastembed model '{settings.local_embedding_model}'...")
    embed_model = TextEmbedding(settings.local_embedding_model)
    logger.info("  ✅ Model loaded.")

    upserted = 0
    failed = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = all_chunks[batch_start : batch_start + BATCH_SIZE]
        texts = [c.get("content", "") for c in batch]

        try:
            embeddings = list(embed_model.embed(texts))
        except Exception as e:
            logger.error(f"  ❌ Embedding failed for batch {batch_start}: {e}")
            failed += len(batch)
            continue

        points = []
        for chunk, embedding in zip(batch, embeddings):
            chunk_id = chunk.get("id") or str(chunk.get("_id", ""))
            payload = {
                "document_id":    chunk.get("document_id", ""),
                "chunk_index":    chunk.get("chunk_index", 0),
                "content":        chunk.get("content", ""),
                "doc_summary":    chunk.get("doc_summary", ""),
                "metadata":       chunk.get("metadata", {}),
                "document_title": chunk.get("metadata", {}).get("title", "Unknown"),
                "is_active":      True,
            }
            points.append(PointStruct(
                id=chunk_id,
                vector=embedding.tolist(),
                payload=payload,
            ))

        try:
            await qdrant.upsert(collection_name=collection_name, points=points)
            upserted += len(points)
            pct = (batch_start + len(batch)) / total * 100
            logger.info(f"  [{pct:5.1f}%] Upserted {upserted}/{total} chunks...")
        except Exception as e:
            logger.error(f"  ❌ Qdrant upsert failed for batch {batch_start}: {e}")
            failed += len(batch)

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"Re-indexing complete.")
    logger.info(f"  ✅ Upserted : {upserted} chunks")
    if failed:
        logger.warning(f"  ❌ Failed   : {failed} chunks")
    logger.info(f"  Collection  : '{collection_name}' ({vector_size}-dim, COSINE)")
    logger.info("=" * 60)
    logger.info("The RAG knowledge base is now using free local embeddings.")
    logger.info("Restart your backend server to pick up the new settings.")


if __name__ == "__main__":
    asyncio.run(main())
