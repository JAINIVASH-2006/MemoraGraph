"""
MemoraGraph – Document Ingestion Pipeline

Coordinates text extraction, semantic chunking, metadata extraction,
PostgreSQL metadata saving, embedding generation, Qdrant vector storage,
LLM-based entity/relationship extraction, and Neo4j graph storage.
Runs asynchronously as a background task.
"""

import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.extractor import extract_text
from app.ingestion.chunker import chunk_text
from app.ingestion.metadata_extractor import enrich_metadata
from app.config import settings
from app.embeddings.encoder import get_encoder
from app.embeddings.vector_store import get_vector_store, VectorChunk
from app.graph.extractor import extract_entities_and_relationships, GraphExtractionError
from app.graph.builder import GraphBuilder
from app.graph.neo4j_client import get_neo4j
from app.models.database import get_session
from app.models.document import Document, DocumentChunk, DocumentStatus

logger = logging.getLogger(__name__)


async def _extract_graph_chunk(text: str, document_name: str) -> dict:
    """Run one graph extraction with a bounded local-inference deadline."""
    timeout_seconds = max(0.1, getattr(settings, "graph_extraction_timeout_seconds", 45.0))
    try:
        return await asyncio.wait_for(
            extract_entities_and_relationships(
                text=text,
                document_name=document_name,
                max_tokens=getattr(settings, "graph_extraction_max_tokens", 1024),
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as e:
        raise GraphExtractionError(
            f"Graph extraction timed out after {timeout_seconds}s"
        ) from e


async def process_document_pipeline(
    document_id: str,
    db_session: AsyncSession | None = None,  # ignored – kept for API compatibility
) -> None:
    """
    Background worker task to process an uploaded document.
    Always opens a fresh DB session to avoid using a closed request-scoped session.
    """
    from app.models.database import _async_session_factory
    if _async_session_factory is None:
        logger.error("DB session factory not initialized. Cannot process document %s", document_id)
        return

    async with _async_session_factory() as db_session:
        await _run_pipeline(document_id, db_session)


async def _run_pipeline(
    document_id: str,
    db_session: AsyncSession,
) -> None:
    logger.info("Starting processing pipeline for document: %s", document_id)

    # 1. Fetch document and update status to PROCESSING
    result = await db_session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        logger.error("Document not found in database: %s", document_id)
        return

    doc.status = DocumentStatus.PROCESSING
    await db_session.commit()

    try:
        # 2. Extract raw text and basic metadata
        raw_text, basic_meta = extract_text(doc.file_path)
        if not raw_text.strip():
            raise ValueError("Extracted text is empty")

        # 3. Enrich metadata using content heuristics
        enriched_meta = enrich_metadata(doc.original_filename, basic_meta, raw_text)
        
        doc.author = enriched_meta.get("author") or doc.author
        doc.doc_date = enriched_meta.get("doc_date") or doc.doc_date
        doc.department = enriched_meta.get("department") or doc.department
        doc.project = enriched_meta.get("project") or doc.project
        doc.doc_type = enriched_meta.get("doc_type") or doc.doc_type
        doc.doc_metadata = enriched_meta

        # 4. Generate semantic chunks
        chunks = chunk_text(raw_text, doc_metadata=enriched_meta)
        if not chunks:
            raise ValueError("No text chunks generated")

        doc.chunk_count = len(chunks)
        await db_session.commit()

        # 5. Generate embeddings for all chunks
        encoder = get_encoder()
        chunk_texts = [c.text for c in chunks]
        embeddings = encoder.encode(chunk_texts)

        # 6. Save chunks to PostgreSQL & Vector Store (Qdrant)
        vector_store = get_vector_store()
        vector_chunks = []

        # Delete any existing chunks in PostgreSQL for this document to support idempotent reprocessing
        from sqlalchemy import delete
        await db_session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc.id}-c{i}"
            embedding = embeddings[i]
            
            chunk_meta = dict(chunk.metadata or {})
            if doc.uploaded_by:
                chunk_meta["user_id"] = doc.uploaded_by
                chunk_meta["uploaded_by"] = doc.uploaded_by

            # Save to PostgreSQL
            db_chunk = DocumentChunk(
                id=chunk_id,
                document_id=doc.id,
                chunk_index=i,
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                token_count=chunk.token_count,
                embedding_id=chunk_id,
                chunk_metadata=chunk_meta,
            )
            db_session.add(db_chunk)

            # Accumulate for Qdrant
            vector_chunks.append(
                VectorChunk(
                    chunk_id=chunk_id,
                    document_id=doc.id,
                    document_name=doc.name,
                    text=chunk.text,
                    embedding=embedding,
                    metadata=chunk_meta,
                )
            )

        await db_session.flush()
        
        # Ensure collection and upsert to Qdrant
        try:
            await vector_store.ensure_collection(encoder.dimension)
            await vector_store.upsert_chunks(vector_chunks)
        except Exception as q_err:
            logger.warning("Failed to store chunks in Qdrant vector store: %s", q_err)

        # 7. Extract entities and relationships using LLM and Ingest into Neo4j
        total_entities = 0
        total_rels = 0

        neo4j_connected = False
        try:
            neo4j_client = get_neo4j()
            if neo4j_client and neo4j_client.verify_connection():
                neo4j_connected = True
            else:
                logger.warning(
                    "Neo4j database connection verification failed. Document will be indexed for text/vector retrieval, but graph entity extraction will be skipped."
                )
        except Exception as neo_err:
            logger.warning("Neo4j client check encountered an error: %s", neo_err)

        graph_error: str | None = None
        if neo4j_connected:
            try:
                graph_builder = GraphBuilder(neo4j_client)
                neo4j_client.ensure_constraints()

                max_extract_chunks = min(getattr(settings, "max_extraction_chunks", 5), len(chunks))
                concurrency = max(1, getattr(settings, "extraction_concurrency", 1))

                successful_extractions: list[dict] = []
                successful_chunk_ids: list[str] = []
                failed_chunks: list[tuple[int, str]] = []

                if concurrency <= 1:
                    logger.info("Extracting graph data sequentially for %d chunks", max_extract_chunks)
                    for i in range(max_extract_chunks):
                        try:
                            extraction = await _extract_graph_chunk(chunks[i].text, doc.name)
                            successful_extractions.append(extraction)
                            successful_chunk_ids.append(f"{doc.id}-c{i}")
                        except Exception as e:
                            error = f"{type(e).__name__}: {e!r}"
                            logger.warning("Graph extraction failed for chunk %d: %s.", i, error)
                            failed_chunks.append((i, error))
                else:
                    logger.info(
                        "Extracting graph data concurrently for %d chunks (concurrency limit: %d)",
                        max_extract_chunks, concurrency,
                    )
                    semaphore = asyncio.Semaphore(concurrency)

                    async def _extract_chunk(idx: int):
                        async with semaphore:
                            try:
                                ext = await _extract_graph_chunk(chunks[idx].text, doc.name)
                                return (idx, ext, None)
                            except Exception as e:
                                error = f"{type(e).__name__}: {e!r}"
                                logger.warning("Graph extraction failed for chunk %d: %s.", idx, error)
                                return (idx, None, error)

                    tasks = [_extract_chunk(i) for i in range(max_extract_chunks)]
                    results = await asyncio.gather(*tasks)
                    for idx, ext, err in results:
                        if ext is not None:
                            successful_extractions.append(ext)
                            successful_chunk_ids.append(f"{doc.id}-c{idx}")
                        else:
                            failed_chunks.append((idx, err))

                if failed_chunks:
                    first_err = failed_chunks[0][1] or "Unknown extraction error"
                    graph_error = (
                        f"Graph extraction failed for {len(failed_chunks)} of {max_extract_chunks} chunks. "
                        f"First error: {first_err}"
                    )

                if successful_extractions:
                    total_entities, total_rels = graph_builder.ingest_document_graph(
                        extractions=successful_extractions,
                        document_id=doc.id,
                        document_name=doc.name,
                        chunk_ids=successful_chunk_ids,
                        user_id=doc.uploaded_by,
                    )

                logger.info(
                    "Graph extraction completed: %d entities, %d relationships",
                    total_entities, total_rels,
                )
            except Exception as graph_exc:
                graph_error = f"Graph extraction failed ({type(graph_exc).__name__}): {graph_exc!r}"
                logger.exception("Graph processing failed for document %s", document_id)
        else:
            graph_error = "Graph extraction unavailable: Neo4j connection could not be verified."

        # Update stats and complete
        doc.entity_count = total_entities
        doc.relationship_count = total_rels
        doc.status = DocumentStatus.FAILED if graph_error else DocumentStatus.PROCESSED
        doc.error_message = graph_error
        doc.processed_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        logger.info(
            "Document processing pipeline completed for document %s: status=%s, %d chunks, %d entities, %d relationships",
            doc.name, doc.status.value, doc.chunk_count, doc.entity_count, doc.relationship_count,
        )

    except Exception as e:
        logger.exception("Document processing failed for document_id: %s", document_id)
        # Attempt to clean up any partial vectors in Qdrant to prevent stale vector data
        try:
            vector_store = get_vector_store()
            await vector_store.delete_by_document(document_id)
        except Exception as cleanup_err:
            logger.debug("Failed to clean up vectors on pipeline failure: %s", cleanup_err)

        # Update status to FAILED and record error message
        await db_session.rollback()
        # Re-fetch document to avoid stale session state
        result = await db_session.execute(select(Document).where(Document.id == document_id))
        failed_doc = result.scalar_one_or_none()
        if failed_doc:
            failed_doc.status = DocumentStatus.FAILED
            failed_doc.error_message = f"{type(e).__name__}: {e!r}"
            await db_session.commit()
