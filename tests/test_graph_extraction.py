"""
MemoraGraph – Graph Extraction, Multi-Strategy Validation & Cross-Chunk Consolidation Tests
"""

import pytest
import os
import sys

# Adjust path to import backend app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.graph.extractor import _slugify, _validate_and_clean, extract_entities_and_relationships
from app.graph.builder import GraphBuilder
from app.graph.neo4j_client import get_neo4j, init_neo4j, _client
from app.graph.schema import VALID_NODE_TYPES, VALID_REL_TYPES
from app.llm.provider import MockLLMProvider
from app.config import settings


@pytest.fixture(autouse=True)
def setup_neo4j_fixture():
    """Ensure Neo4j client is initialized."""
    global _client
    if _client is None:
        init_neo4j(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
        )
    return _client


def test_slugify_consistency():
    """Verify _slugify produces stable, clean IDs."""
    assert _slugify("Dr. Maya Rao") == "dr-maya-rao"
    assert _slugify("Project Atlas") == "project-atlas"
    assert _slugify("Engineering Department") == "engineering-department"
    assert _slugify("  PostgreSQL / Database  ") == "postgresql-database"
    assert _slugify("already-slugified-id") == "already-slugified-id"


def test_valid_same_chunk_relationship():
    """1. Test valid same-chunk entity and relationship extraction and validation."""
    raw_data = {
        "entities": [
            {"id": "dr-maya-rao", "type": "Employee", "name": "Dr. Maya Rao"},
            {"id": "project-atlas", "type": "Project", "name": "Project Atlas"},
            {"id": "aurora-labs", "type": "Department", "name": "Aurora Labs"},
        ],
        "relationships": [
            {
                "from_id": "dr-maya-rao",
                "rel_type": "MANAGES",
                "to_id": "project-atlas",
            },
            {
                "from_id": "project-atlas",
                "rel_type": "PART_OF",
                "to_id": "aurora-labs",
            }
        ]
    }

    validated = _validate_and_clean(raw_data)
    assert len(validated["entities"]) == 3
    assert len(validated["relationships"]) == 2
    
    rels = validated["relationships"]
    assert rels[0]["from_id"] == "dr-maya-rao"
    assert rels[0]["rel_type"] == "MANAGES"
    assert rels[0]["to_id"] == "project-atlas"
    assert rels[0]["from_type"] == "Employee"
    assert rels[0]["to_type"] == "Project"

    assert rels[1]["from_id"] == "project-atlas"
    assert rels[1]["rel_type"] == "PART_OF"
    assert rels[1]["to_id"] == "aurora-labs"
    assert rels[1]["from_type"] == "Project"
    assert rels[1]["to_type"] == "Department"


def test_relationship_endpoints_represented_differently():
    """2. Test that endpoints represented as entity names, titles, or unnormalized slugs resolve accurately."""
    raw_data = {
        "entities": [
            {"id": "dr-maya-rao", "type": "Employee", "name": "Dr. Maya Rao"},
            {"id": "project-atlas", "type": "Project", "name": "Project Atlas"},
            {"id": "fastapi", "type": "Technology", "name": "FastAPI"},
        ],
        "relationships": [
            # Source using full name string, target using slug
            {
                "source": "Dr. Maya Rao",
                "relationship": "MANAGES",
                "target": "project-atlas",
            },
            # Source using short name ("Atlas"), target using technology name ("FastAPI")
            {
                "from_id": "Atlas",
                "rel_type": "DEPENDS_ON",
                "to_id": "FastAPI",
            },
            # Source with underscores and casing
            {
                "from_id": "DR_MAYA_RAO",
                "rel_type": "MANAGES",
                "to_id": "Project Atlas",
            }
        ]
    }

    validated = _validate_and_clean(raw_data)
    assert len(validated["entities"]) == 3
    assert len(validated["relationships"]) == 3
    
    # Check resolution
    r1 = validated["relationships"][0]
    assert r1["from_id"] == "dr-maya-rao"
    assert r1["to_id"] == "project-atlas"

    r2 = validated["relationships"][1]
    assert r2["from_id"] == "project-atlas"
    assert r2["to_id"] == "fastapi"

    r3 = validated["relationships"][2]
    assert r3["from_id"] == "dr-maya-rao"
    assert r3["to_id"] == "project-atlas"


def test_cross_chunk_entity_relationship():
    """3. Test resolving relationships where endpoints were extracted in different chunks."""
    # Chunk 0 entities
    chunk_0_raw = {
        "entities": [
            {"id": "project-atlas", "type": "Project", "name": "Project Atlas"},
            {"id": "dr-maya-rao", "type": "Employee", "name": "Dr. Maya Rao"},
        ],
        "relationships": [
            {"from_id": "dr-maya-rao", "rel_type": "MANAGES", "to_id": "project-atlas"}
        ]
    }
    chunk_0_val = _validate_and_clean(chunk_0_raw)

    # Chunk 1 has a new entity and a relationship referencing an entity from Chunk 0
    chunk_1_raw = {
        "entities": [
            {"id": "rahul-menon", "type": "Employee", "name": "Rahul Menon"},
            {"id": "kg-extraction-task", "type": "Task", "name": "KG Extraction Task"},
        ],
        "relationships": [
            # Cross-chunk rel: Rahul (Chunk 1) -> Project Atlas (Chunk 0)
            {"from_id": "Rahul Menon", "rel_type": "WORKS_IN", "to_id": "Project Atlas"},
            # Local rel in chunk 1
            {"from_id": "rahul-menon", "rel_type": "ASSIGNED_TO", "to_id": "kg-extraction-task"},
        ]
    }
    # Pass chunk 0 entities into chunk 1 validation
    chunk_1_val = _validate_and_clean(chunk_1_raw, known_entities=chunk_0_val["entities"])
    
    assert len(chunk_1_val["relationships"]) == 2
    cross_rel = next(r for r in chunk_1_val["relationships"] if r["to_id"] == "project-atlas")
    assert cross_rel["from_id"] == "rahul-menon"
    assert cross_rel["rel_type"] == "WORKS_IN"
    assert cross_rel["to_type"] == "Project"


def test_invalid_relationship_type_rejection():
    """4. Test that invalid or hallucinated relationship types are rejected."""
    raw_data = {
        "entities": [
            {"id": "arun", "type": "Employee", "name": "Arun"},
            {"id": "project-alpha", "type": "Project", "name": "Project Alpha"},
        ],
        "relationships": [
            {"from_id": "arun", "rel_type": "LOVES_WORKING_ON", "to_id": "project-alpha"},
            {"from_id": "arun", "rel_type": "MANAGES", "to_id": "project-alpha"},
            {"from_id": "arun", "rel_type": "UNKNOWN_CUSTOM_REL", "to_id": "project-alpha"},
        ]
    }

    validated = _validate_and_clean(raw_data)
    assert len(validated["relationships"]) == 1
    assert validated["relationships"][0]["rel_type"] == "MANAGES"


def test_hallucinated_missing_endpoint_rejection():
    """5. Test that relationships referencing nonexistent entities are rejected."""
    raw_data = {
        "entities": [
            {"id": "arun", "type": "Employee", "name": "Arun"},
        ],
        "relationships": [
            # Target does not exist anywhere
            {"from_id": "arun", "rel_type": "MANAGES", "to_id": "nonexistent-project-xyz"},
            # Source does not exist
            {"from_id": "ghost-employee", "rel_type": "WORKS_IN", "to_id": "arun"},
        ]
    }

    validated = _validate_and_clean(raw_data)
    assert len(validated["relationships"]) == 0


@pytest.mark.asyncio
async def test_document_graph_consolidation_and_idempotency():
    """6. Test multi-chunk document graph builder consolidation, deduplication, and Neo4j idempotency."""
    neo4j = get_neo4j()
    builder = GraphBuilder(neo4j)
    doc_id = "test-doc-cross-chunk-001"
    doc_name = "Cross Chunk Test Document.txt"

    # Reset test document graph
    builder.delete_document_graph(doc_id)

    chunk_0 = {
        "entities": [
            {"id": "dr-maya-rao", "type": "Employee", "name": "Dr. Maya Rao"},
            {"id": "project-atlas", "type": "Project", "name": "Project Atlas"},
            {"id": "aurora-labs", "type": "Department", "name": "Aurora Labs"},
        ],
        "relationships": [
            {"from_id": "dr-maya-rao", "rel_type": "MANAGES", "to_id": "project-atlas"},
            {"from_id": "project-atlas", "rel_type": "PART_OF", "to_id": "aurora-labs"},
        ]
    }

    chunk_1 = {
        "entities": [
            {"id": "rahul-menon", "type": "Employee", "name": "Rahul Menon"},
            {"id": "project-atlas", "type": "Project", "name": "Project Atlas"},  # shared entity
        ],
        "relationships": [
            # Duplicate relationship from chunk 0
            {"from_id": "Dr. Maya Rao", "rel_type": "MANAGES", "to_id": "Project Atlas"},
            # Cross-chunk relationship
            {"from_id": "dr-maya-rao", "rel_type": "MANAGES", "to_id": "rahul-menon"},
        ]
    }

    # Ingest consolidated document graph
    ent_cnt, rel_cnt = builder.ingest_document_graph(
        extractions=[chunk_0, chunk_1],
        document_id=doc_id,
        document_name=doc_name,
        chunk_ids=["chunk-0", "chunk-1"],
    )

    # 4 unique entities (Dr. Maya Rao, Project Atlas, Aurora Labs, Rahul Menon)
    assert ent_cnt == 4
    # 3 unique semantic relationships:
    # 1. dr-maya-rao -> project-atlas
    # 2. project-atlas -> aurora-labs
    # 3. dr-maya-rao -> rahul-menon
    assert rel_cnt == 3

    # Query Neo4j to verify relationships were created
    cypher = (
        "MATCH (a)-[r]->(b) "
        "WHERE r.source_document_id = $doc_id AND type(r) <> 'MENTIONED_IN' "
        "RETURN a.id as from_id, type(r) as rel_type, b.id as to_id"
    )
    results = neo4j.execute_query(cypher, {"doc_id": doc_id})
    assert len(results) == 3

    rel_tuples = {(r["from_id"], r["rel_type"], r["to_id"]) for r in results}
    assert ("dr-maya-rao", "MANAGES", "project-atlas") in rel_tuples
    assert ("project-atlas", "PART_OF", "aurora-labs") in rel_tuples
    assert ("dr-maya-rao", "MANAGES", "rahul-menon") in rel_tuples

    # Re-ingest exact same document: verify idempotency
    ent_cnt_2, rel_cnt_2 = builder.ingest_document_graph(
        extractions=[chunk_0, chunk_1],
        document_id=doc_id,
        document_name=doc_name,
        chunk_ids=["chunk-0", "chunk-1"],
    )
    assert ent_cnt_2 == 4
    assert rel_cnt_2 == 3

    results_after = neo4j.execute_query(cypher, {"doc_id": doc_id})
    assert len(results_after) == 3

    # Cleanup test document
    builder.delete_document_graph(doc_id)
