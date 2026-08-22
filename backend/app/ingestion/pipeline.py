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
from app.embeddings.encoder import get_encoder
from app.embeddings.vector_store import get_vector_store, VectorChunk
from app.graph.extractor import extract_entities_and_relationships
from app.graph.builder import GraphBuilder
from app.graph.neo4j_client import get_neo4j
from app.models.database import get_session
from app.models.document import Document, DocumentChunk, DocumentStatus

logger = logging.getLogger(__name__)


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

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc.id}-c{i}"
            embedding = embeddings[i]
            
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
                chunk_metadata=chunk.metadata,
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
                    metadata=chunk.metadata,
                )
            )

        await db_session.flush()
        
        # Ensure collection and upsert to Qdrant
        await vector_store.ensure_collection(encoder.dimension)
        await vector_store.upsert_chunks(vector_chunks)

        # 7. Extract entities and relationships using LLM
        # Perform extraction on the first few chunks or full text sample to capture graph structure
        # To avoid massive API usage, we limit graph extraction to the first 4 chunks
        # or combine key portions of the text. Let's do up to 4 chunks of extraction.
        # 7. Verify Neo4j and Ingest Graph Elements
        neo4j_client = get_neo4j()
        if not neo4j_client.verify_connection():
            raise RuntimeError("Neo4j database connection verification failed. Aborting document ingestion.")
            
        graph_builder = GraphBuilder(neo4j_client)
        
        total_entities = 0
        total_rels = 0
        
        # Ensure Neo4j uniqueness constraints exist
        neo4j_client.ensure_constraints()

        # Extract graph elements chunk-by-chunk for local context in parallel
        max_extract_chunks = min(5, len(chunks))
        
        logger.info("Extracting entities and relationships concurrently for %d chunks", max_extract_chunks)
        extraction_tasks = [
            extract_entities_and_relationships(
                text=chunks[i].text,
                document_name=doc.name,
            )
            for i in range(max_extract_chunks)
        ]
        
        extractions = await asyncio.gather(*extraction_tasks)
        
        for i, extraction in enumerate(extractions):
            chunk_id = f"{doc.id}-c{i}"
            ent_cnt, rel_cnt = graph_builder.ingest_extraction(
                extraction=extraction,
                document_id=doc.id,
                document_name=doc.name,
                chunk_id=chunk_id,
            )
            total_entities += ent_cnt
            total_rels += rel_cnt

        # Update stats and complete
        doc.entity_count = total_entities
        doc.relationship_count = total_rels
        doc.status = DocumentStatus.PROCESSED
        doc.processed_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        logger.info(
            "Document processing pipeline succeeded for document %s: %d chunks, %d entities, %d relationships",
            doc.name, doc.chunk_count, doc.entity_count, doc.relationship_count,
        )

    except Exception as e:
        logger.exception("Document processing failed for document: %s", doc.name)
        # Update status to FAILED and record error message
        db_session.rollback()
        # Re-fetch document to avoid stale session state
        result = await db_session.execute(select(Document).where(Document.id == document_id))
        failed_doc = result.scalar_one_or_none()
        if failed_doc:
            failed_doc.status = DocumentStatus.FAILED
            failed_doc.error_message = str(e)
            await db_session.commit()
