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

    def ingest_extraction(
        self,
        extraction: dict[str, Any],
        document_id: str,
        document_name: str,
        chunk_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> tuple[int, int]:
        """
        Write entities and relationships to Neo4j with user scoping.
        """
        entities = extraction.get("entities", [])
        relationships = extraction.get("relationships", [])

        # Ensure the Document node exists
        doc_props = {"name": document_name, "document_id": document_id}
        if user_id:
            doc_props["user_id"] = user_id
            doc_props["uploaded_by"] = user_id

        self._neo4j.merge_node("Document", document_id, doc_props)

        entities_created = 0
        for ent in entities:
            try:
                props = {
                    "name": ent["name"],
                    "source_document_id": document_id,
                    **{k: v for k, v in ent.get("properties", {}).items() if v is not None},
                }
                if chunk_id:
                    props["source_chunk_id"] = chunk_id
                if user_id:
                    props["user_id"] = user_id

                self._neo4j.merge_node(ent["type"], ent["id"], props)
                
                rel_props = {
                    "source_document_id": document_id,
                    "created_at": int(time.time() * 1000),
                }
                if chunk_id:
                    rel_props["source_chunk_id"] = chunk_id
                if user_id:
                    rel_props["user_id"] = user_id

                self._neo4j.merge_relationship(
                    ent["type"], ent["id"],
                    "MENTIONED_IN",
                    "Document", document_id,
                    rel_props,
                )
                entities_created += 1
            except Exception as e:
                logger.warning("Failed to insert entity %s: %s", ent.get("id"), e)

        relationships_created = 0
        for rel in relationships:
            try:
                from_ent = next((e for e in entities if e["id"] == rel["from_id"]), None)
                to_ent = next((e for e in entities if e["id"] == rel["to_id"]), None)
                
                if not from_ent or not to_ent:
                    continue
                
                rel_props = {
                    **rel.get("properties", {}),
                    "source_document_id": document_id,
                }
                if chunk_id:
                    rel_props["source_chunk_id"] = chunk_id
                if user_id:
                    rel_props["user_id"] = user_id

                self._neo4j.merge_relationship(
                    from_ent["type"], rel["from_id"],
                    rel["rel_type"],
                    to_ent["type"], rel["to_id"],
                    rel_props,
                )
                relationships_created += 1
            except Exception as e:
                logger.warning("Failed to insert relationship %s->%s: %s",
                               rel.get("from_id"), rel.get("to_id"), e)

        logger.info(
            "Graph build complete for doc '%s': %d entities, %d relationships",
            document_name, entities_created, relationships_created,
        )
        return entities_created, relationships_created

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
