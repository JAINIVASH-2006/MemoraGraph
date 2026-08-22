"""
MemoraGraph – Pydantic Schemas: Documents
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class DocumentOut(BaseModel):
    id: str
    name: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    status: str
    error_message: Optional[str] = None
    doc_metadata: Optional[Dict[str, Any]] = None
    author: Optional[str] = None
    doc_date: Optional[str] = None
    department: Optional[str] = None
    project: Optional[str] = None
    doc_type: Optional[str] = None
    chunk_count: int = 0
    entity_count: int = 0
    relationship_count: int = 0
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DocumentChunkOut(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    token_count: int
    chunk_metadata: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    document_id: str
    name: str
    status: str
    message: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]
    total: int
    page: int
    page_size: int
