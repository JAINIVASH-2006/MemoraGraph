"""
MemoraGraph API – Document Management Endpoints

POST   /api/documents/upload – Upload and start ingestion
GET    /api/documents        – List documents
GET    /api/documents/{id}   – View document details
DELETE /api/documents/{id}   – Delete a document
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_session
from app.models.document import Document, DocumentStatus, DocumentChunk
from app.models.user import User, UserRole
from app.security.auth import get_current_user
from app.security.rbac import require_manager_or_admin, require_admin
from app.schemas.document import DocumentOut, UploadResponse, DocumentListResponse
from app.ingestion.pipeline import process_document_pipeline
from app.embeddings.vector_store import get_vector_store
from app.graph.builder import GraphBuilder
from app.graph.neo4j_client import get_neo4j

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".json", ".pptx", ".md"}
MAX_FILE_SIZE_MB = 20


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    department: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    current_user: User = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    """
    Upload an organizational document.
    Validates extension and size, saves file to disk, and triggers processing.
    """
    # 1. Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 2. Check file size (approximate stream check)
    os.makedirs(settings.upload_dir, exist_ok=True)
    document_id = str(uuid.uuid4())
    save_name = f"{document_id}{ext}"
    file_path = os.path.join(settings.upload_dir, save_name)

    size = 0
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):
                size += len(chunk)
                if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File size exceeds limit of {MAX_FILE_SIZE_MB}MB.",
                    )
                buffer.write(chunk)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        if isinstance(e, HTTPException):
            raise e
        logger.error("Failed to save uploaded file: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        )

    # 3. Create document record in database
    doc = Document(
        id=document_id,
        name=Path(file.filename).stem.replace("_", " ").replace("-", " ").title(),
        original_filename=file.filename,
        file_type=ext[1:].upper(),
        file_size_bytes=size,
        file_path=file_path,
        status=DocumentStatus.UPLOADED,
        department=department,
        project=project,
        uploaded_by=current_user.id,
    )
    session.add(doc)
    await session.commit()

    logger.info(
        "Document uploaded successfully: %s (id=%s, size=%d bytes)",
        doc.original_filename, doc.id, size,
    )

    # 4. Dispatch processing background task
    background_tasks.add_task(
        process_document_pipeline,
        document_id=doc.id,
        db_session=session,
    )

    return UploadResponse(
        document_id=doc.id,
        name=doc.name,
        status=doc.status.value,
        message="Document uploaded successfully. Processing started in the background.",
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    query: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    """List documents with pagination, search, and status filters."""
    offset = (page - 1) * page_size
    stmt = select(Document)

    # Apply search filter
    if query:
        stmt = stmt.where(Document.name.ilike(f"%{query}%") | Document.original_filename.ilike(f"%{query}%"))

    # Apply status filter
    if status_filter:
        try:
            status_enum = DocumentStatus(status_filter.upper())
            stmt = stmt.where(Document.status == status_enum)
        except ValueError:
            pass

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    # Order and paginate
    stmt = stmt.order_by(Document.uploaded_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    docs = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentOut.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=DocumentOut)
async def get_document(
    id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentOut:
    """Retrieve metadata of a single document."""
    result = await session.execute(select(Document).where(Document.id == id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentOut.model_validate(doc)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    id: str,
    current_user: User = Depends(require_manager_or_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete document, its chunks, vectors, and graph annotations."""
    result = await session.execute(select(Document).where(Document.id == id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    logger.info("Deleting document: %s (id=%s)", doc.name, id)

    # 1. Delete original file from disk
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning("Failed to delete file from disk: %s", e)

    # 2. Delete vectors from Qdrant
    try:
        vector_store = get_vector_store()
        await vector_store.delete_by_document(doc.id)
    except Exception as e:
        logger.warning("Failed to delete vectors from Qdrant: %s", e)

    # 3. Delete annotations from Neo4j
    try:
        neo4j_client = get_neo4j()
        graph_builder = GraphBuilder(neo4j_client)
        graph_builder.delete_document_graph(doc.id)
    except Exception as e:
        logger.warning("Failed to delete graph data from Neo4j: %s", e)

    # 4. Delete document record (cascade deletes PostgreSQL document_chunks)
    await session.delete(doc)
    await session.commit()
    logger.info("Document deleted successfully: %s", id)
