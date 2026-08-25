"""
MemoraGraph – Vector Store Abstraction

Provides an abstract VectorStore interface and a QdrantVectorStore implementation.
ChromaDB can be added later by implementing VectorStore.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

QDRANT_COLLECTION = "organizational_memory"


@dataclass
class VectorChunk:
    """A text chunk with its embedding and metadata for storage."""
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any]


@dataclass
class VectorSearchResult:
    """A search result from the vector store."""
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    metadata: dict[str, Any]


class VectorStore(ABC):
    """Abstract interface for vector storage backends."""

    @abstractmethod
    async def upsert_chunks(self, chunks: list[VectorChunk]) -> int:
        """Store or update chunks. Returns number of upserted chunks."""

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_document_id: Optional[str] = None,
    ) -> list[VectorSearchResult]:
        """Search for similar chunks. Returns scored results."""

    @abstractmethod
    async def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document. Returns deleted count."""

    @abstractmethod
    async def ping(self) -> bool:
        """Test connectivity."""


class QdrantVectorStore(VectorStore):
    """Qdrant vector database implementation."""

    def __init__(self, url: str, api_key: Optional[str] = None, collection: str = QDRANT_COLLECTION):
        from qdrant_client import QdrantClient
        self.collection = collection
        self._client = QdrantClient(url=url, api_key=api_key, timeout=30)
        logger.info("QdrantVectorStore initialized. Collection: %s", collection)

    async def ensure_collection(self, dimension: int) -> None:
        """Create the collection if it does not exist."""
        from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
        
        existing = self._client.get_collections().collections
        names = [c.name for c in existing]
        
        if self.collection not in names:
            self._client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection: %s (dim=%d)", self.collection, dimension)
        else:
            logger.debug("Qdrant collection already exists: %s", self.collection)
            
        # Ensure payload index for document_id exists (required by Qdrant Cloud for deletion/filtering)
        try:
            self._client.create_payload_index(
                collection_name=self.collection,
                field_name="document_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.info("Verified/Created Qdrant payload index for document_id.")
        except Exception as e:
            logger.debug("Skipped Qdrant payload index creation: %s", e)

    async def upsert_chunks(self, chunks: list[VectorChunk]) -> int:
        """Upsert a batch of chunks into Qdrant."""
        from qdrant_client.models import PointStruct
        
        if not chunks:
            return 0
        
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id)),
                vector=chunk.embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "text": chunk.text,
                    "user_id": chunk.metadata.get("user_id") or chunk.metadata.get("uploaded_by") or "",
                    "uploaded_by": chunk.metadata.get("uploaded_by") or chunk.metadata.get("user_id") or "",
                    "filename": chunk.metadata.get("filename") or chunk.document_name or "",
                    "title": chunk.metadata.get("title") or chunk.document_name or "",
                    "author": chunk.metadata.get("author") or "",
                    "department": chunk.metadata.get("department") or "",
                    "project": chunk.metadata.get("project") or "",
                    "document_date": chunk.metadata.get("document_date") or chunk.metadata.get("doc_date") or "",
                    "metadata": chunk.metadata,
                },
            )
            for chunk in chunks
        ]
        
        self._client.upsert(collection_name=self.collection, points=points)
        logger.debug("Upserted %d chunks into Qdrant", len(chunks))
        return len(chunks)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_document_id: Optional[str] = None,
        filter_user_id: Optional[str] = None,
    ) -> list[VectorSearchResult]:
        """Perform approximate nearest-neighbor search with user isolation."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        must_conditions = []
        if filter_document_id:
            must_conditions.append(FieldCondition(key="document_id", match=MatchValue(value=filter_document_id)))
        if filter_user_id:
            must_conditions.append(FieldCondition(key="user_id", match=MatchValue(value=filter_user_id)))
        
        search_filter = Filter(must=must_conditions) if must_conditions else None
        
        response = self._client.query_points(
            collection_name=self.collection,
            query=query_embedding,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True,
        )
        
        return [
            VectorSearchResult(
                chunk_id=r.payload.get("chunk_id", str(r.id)),
                document_id=r.payload.get("document_id", ""),
                document_name=r.payload.get("document_name", ""),
                text=r.payload.get("text", ""),
                score=r.score,
                metadata={k: v for k, v in r.payload.items() 
                          if k not in ("chunk_id", "document_id", "document_name", "text")},
            )
            for r in response.points
        ]

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all vectors for a given document."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        doc_filter = Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        )
        self._client.delete(
            collection_name=self.collection,
            points_selector=doc_filter,
        )
        logger.info("Deleted vectors for document: %s", document_id)
        return 1  # Qdrant delete doesn't return count easily

    async def ping(self) -> bool:
        """Check Qdrant connectivity."""
        try:
            self._client.get_collections()
            return True
        except Exception as e:
            logger.warning("Qdrant ping failed: %s", e)
            return False


# Module-level singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        raise RuntimeError("Vector store not initialized. Call init_vector_store() first.")
    return _vector_store


def init_vector_store(url: str, api_key: Optional[str], collection: str) -> QdrantVectorStore:
    global _vector_store
    store = QdrantVectorStore(url=url, api_key=api_key, collection=collection)
    _vector_store = store
    return store
