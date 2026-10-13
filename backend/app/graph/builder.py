"""
MemoraGraph – Knowledge Graph Builder

Ingests extracted entities and relationships into Neo4j using MERGE
for idempotent, conflict-safe graph construction.
"""

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds the knowledge graph from extracted entities and relationships."""

    def __init__(self, neo4j_client):
        self._neo4j = neo4j_client

    def ingest_document_graph(
        self,
        extractions: list[dict[str, Any]],
        document_id: str,
        document_name: str,
        chunk_ids: Optional[list[str]] = None,
        user_id: Optional[str] = None,
    ) -> tuple[int, int]:
        """
        Consolidate entities and relationships across multiple chunk extractions for a document,
        resolve cross-chunk relationship endpoints, and write the unified graph to Neo4j.
        """
        from app.graph.extractor import _slugify, _resolve_endpoint
        from app.graph.schema import VALID_NODE_TYPES, VALID_REL_TYPES

        # 1. Ensure the Document node exists
        doc_props = {"name": document_name, "document_id": document_id}
        if user_id:
            doc_props["user_id"] = user_id
            doc_props["uploaded_by"] = user_id

        self._neo4j.merge_node("Document", document_id, doc_props)

        # 2. Canonicalize entities across all chunks
        doc_entities: dict[str, dict[str, Any]] = {}
        entity_id_map: dict[str, str] = {}  # id -> type
        name_to_id_map: dict[str, str] = {}  # name/slug -> id

        for i, extraction in enumerate(extractions):
            chunk_id = chunk_ids[i] if chunk_ids and i < len(chunk_ids) else None
            for ent in extraction.get("entities", []):
                ent_type = ent.get("type")
                ent_name = ent.get("name")
                if not ent_type or ent_type not in VALID_NODE_TYPES or not ent_name:
                    continue

                raw_id = ent.get("id")
                ent_id = _slugify(raw_id) if raw_id else _slugify(ent_name)
                
                if ent_id not in doc_entities:
                    doc_entities[ent_id] = {
                        "id": ent_id,
                        "type": ent_type,
                        "name": str(ent_name).strip(),
                        "properties": dict(ent.get("properties", {}) or {}),
                        "source_chunk_id": chunk_id,
                    }
                else:
                    # Merge properties and preserve earlier non-null properties
                    existing_props = doc_entities[ent_id]["properties"]
                    for k, v in (ent.get("properties") or {}).items():
                        if v is not None and k not in existing_props:
                            existing_props[k] = v
                            
                entity_id_map[ent_id] = ent_type
                name_to_id_map[str(ent_name).strip().lower()] = ent_id
                name_to_id_map[_slugify(ent_name)] = ent_id

        # 3. Ingest canonical entities and MENTIONED_IN links
        entities_created = 0
        now_ms = int(time.time() * 1000)

        for ent_id, ent in doc_entities.items():
            try:
                node_props = {
                    "name": ent["name"],
                    "source_document_id": document_id,
                    **{k: v for k, v in ent.get("properties", {}).items() if v is not None},
                }
                if ent.get("source_chunk_id"):
                    node_props["source_chunk_id"] = ent["source_chunk_id"]
                if user_id:
                    node_props["user_id"] = user_id

                self._neo4j.merge_node(ent["type"], ent_id, node_props)

                rel_props = {
                    "source_document_id": document_id,
                    "created_at": now_ms,
                }
                if ent.get("source_chunk_id"):
                    rel_props["source_chunk_id"] = ent["source_chunk_id"]
                if user_id:
                    rel_props["user_id"] = user_id

                self._neo4j.merge_relationship(
                    ent["type"], ent_id,
                    "MENTIONED_IN",
                    "Document", document_id,
                    rel_props,
                )
                entities_created += 1
            except Exception as e:
                logger.warning("Failed to insert entity node %s: %s", ent_id, e)

        # 4. Consolidate and resolve relationships across all chunks
        seen_relationships = set()
        relationships_created = 0

        for i, extraction in enumerate(extractions):
            chunk_id = chunk_ids[i] if chunk_ids and i < len(chunk_ids) else None
            for rel in extraction.get("relationships", []):
                raw_from = rel.get("from_id") or rel.get("source") or rel.get("from") or rel.get("source_id") or rel.get("head")
                raw_to = rel.get("to_id") or rel.get("target") or rel.get("to") or rel.get("target_id") or rel.get("tail")
                rel_type = (rel.get("rel_type") or rel.get("relationship") or rel.get("type") or "").strip().upper()

                if rel_type not in VALID_REL_TYPES:
                    continue

                from_id = _resolve_endpoint(raw_from, entity_id_map, name_to_id_map)
                to_id = _resolve_endpoint(raw_to, entity_id_map, name_to_id_map)

                if not from_id or not to_id or from_id == to_id:
                    continue

                rel_key = (from_id, rel_type, to_id)
                if rel_key in seen_relationships:
                    continue
                seen_relationships.add(rel_key)

                from_type = entity_id_map[from_id]
                to_type = entity_id_map[to_id]

                rel_props = {
                    **{k: v for k, v in rel.get("properties", {}).items() if v is not None},
                    "source_document_id": document_id,
                    "created_at": now_ms,
                }
                if chunk_id:
                    rel_props["source_chunk_id"] = chunk_id
                if user_id:
                    rel_props["user_id"] = user_id

                try:
                    self._neo4j.merge_relationship(
                        from_type, from_id,
                        rel_type,
                        to_type, to_id,
                        rel_props,
                    )
                    relationships_created += 1
                except Exception as e:
                    logger.warning("Failed to insert relationship %s-[%s]->%s: %s",
                                   from_id, rel_type, to_id, e)

        logger.info(
            "Consolidated graph build complete for doc '%s': %d entities, %d semantic relationships",
            document_name, entities_created, relationships_created,
        )
        return entities_created, relationships_created

    def ingest_extraction(
        self,
        extraction: dict[str, Any],
        document_id: str,
        document_name: str,
        chunk_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> tuple[int, int]:
        """
        Write entities and relationships from a single extraction to Neo4j with user scoping.
        Maintains backward compatibility by delegating to consolidated document graph ingestion.
        """
        return self.ingest_document_graph(
            extractions=[extraction],
            document_id=document_id,
            document_name=document_name,
            chunk_ids=[chunk_id] if chunk_id else None,
            user_id=user_id,
        )

    def delete_document_graph(self, document_id: str) -> None:
        """Remove all entity-document links for a deleted document and delete exclusive orphan nodes."""
        # 1. Delete MENTIONED_IN relations pointing to this Document
        self._neo4j.execute_write(
            "MATCH (n)-[r:MENTIONED_IN]->(d:Document {id: $doc_id}) DELETE r",
            {"doc_id": document_id},
        )
        # 2. Delete the Document node
        self._neo4j.execute_write(
            "MATCH (d:Document {id: $doc_id}) DETACH DELETE d",
            {"doc_id": document_id},
        )
        # 3. Cascading delete: Remove orphan nodes that have no remaining MENTIONED_IN relationships
        # pointing to any Document (excluding the Document nodes themselves)
        self._neo4j.execute_write(
            "MATCH (n) WHERE NOT n:Document AND NOT (n)-[:MENTIONED_IN]->(:Document) DETACH DELETE n"
        )
        logger.info("Deleted graph data and clean up exclusive orphan nodes for document: %s", document_id)
