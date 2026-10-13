"""
MemoraGraph – Phase 3 Graph & Extraction Unit Tests
"""

import pytest
import os
import sys

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.graph.neo4j_client import get_neo4j, init_neo4j, _client
from app.graph.extractor import extract_entities_and_relationships, _validate_and_clean
from app.graph.builder import GraphBuilder
from app.llm.provider import MockLLMProvider
from app.config import settings

# Test dataset configurations
TEST_DOC_ID = "doc-test-provenance-123"
TEST_DOC_NAME = "test_document_phase_3.txt"
TEST_TEXT = "Arun manages Project Alpha in the Engineering Department. Karthik reported a database vulnerability risk."


@pytest.fixture(autouse=True)
def setup_neo4j():
    """Fixture to ensure Neo4j client is initialized prior to running unit tests."""
    global _client
    if _client is None:
        init_neo4j(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password
        )
    return _client


@pytest.mark.asyncio
async def test_neo4j_connection_and_constraints():
    """1. Test Neo4j connection verification and constraints creation."""
    neo4j = get_neo4j()
    
    # Verify connection works
    connected = neo4j.verify_connection()
    assert connected is True
    
    # Verify constraints creation executes without raising errors
    neo4j.ensure_constraints()


@pytest.mark.asyncio
async def test_entity_and_relationship_extraction_fallback():
    """2. Test rule-based mock entity and relationship extraction."""
    mock_llm = MockLLMProvider()
    
    # Run extractor in offline mock mode
    extraction = await extract_entities_and_relationships(
        text=TEST_TEXT,
        document_name=TEST_DOC_NAME,
        llm_client=mock_llm
    )
    
    assert "entities" in extraction
    assert "relationships" in extraction
    
    # Check that deterministic rules parsed our test text
    entities = extraction["entities"]
    entity_names = {e["name"] for e in entities}
    assert "Arun" in entity_names
    assert "Project Alpha" in entity_names
    assert "Engineering Department" in entity_names
    
    # Check that a Risk entity was extracted dynamically
    risk_entities = [e for e in entities if e["type"] == "Risk"]
    assert len(risk_entities) > 0
    
    # Check that relationships were mapped
    relationships = extraction["relationships"]
    assert len(relationships) > 0
    rel_types = {r["rel_type"] for r in relationships}
    assert "WORKS_IN" in rel_types or "MANAGES" in rel_types or "HAS_RISK" in rel_types


def test_schema_validation_and_rejections():
    """3. Test strict schema validation and invalid element rejections."""
    # Test valid entities & relationships
    raw_data = {
        "entities": [
            {"name": "Arun", "type": "Employee"},
            {"name": "Project Alpha", "type": "Project"},
            {"name": "Invalid Node", "type": "AlienType"}  # Invalid type
        ],
        "relationships": [
            {
                "source": "Arun",
                "target": "Project Alpha",
                "relationship": "MANAGES"
            },
            {
                "source": "Arun",
                "target": "Project Alpha",
                "relationship": "ALIEN_RELATION"  # Invalid relationship
            }
        ]
    }
    
    validated = _validate_and_clean(raw_data)
    
    # AlienType should be rejected
    entities = validated["entities"]
    assert len(entities) == 2
    types = {e["type"] for e in entities}
    assert "AlienType" not in types
    
    # ALIEN_RELATION should be rejected
    relationships = validated["relationships"]
    assert len(relationships) == 1
    assert relationships[0]["rel_type"] == "MANAGES"


@pytest.mark.asyncio
async def test_idempotent_graph_merge_and_provenance():
    """4. Test idempotency of node/edge MERGE, provenance, and duplicate checks."""
    neo4j = get_neo4j()
    builder = GraphBuilder(neo4j)
    
    # Clear test nodes
    neo4j.execute_write("MATCH (n) WHERE n.id IN ['test-arun-phase3', 'test-project-alpha-phase3', $doc_id] DETACH DELETE n", {"doc_id": TEST_DOC_ID})
    stats_initial = neo4j.get_stats()

    # Extract mock elements
    extraction = {
        "entities": [
            {"id": "test-arun-phase3", "type": "Employee", "name": "Arun", "properties": {"role": "Manager"}},
            {"id": "test-project-alpha-phase3", "type": "Project", "name": "Project Alpha", "properties": {"status": "Active"}}
        ],
        "relationships": [
            {
                "from_id": "test-arun-phase3",
                "from_type": "Employee",
                "rel_type": "MANAGES",
                "to_id": "test-project-alpha-phase3",
                "to_type": "Project"
            }
        ]
    }
    
    # First Ingest: Verify creation and provenance properties
    ent_cnt, rel_cnt = builder.ingest_extraction(
        extraction=extraction,
        document_id=TEST_DOC_ID,
        document_name=TEST_DOC_NAME,
        chunk_id="chunk-0"
    )
    assert ent_cnt == 2
    assert rel_cnt == 1
    
    # Verify node has source reference properties
    node = neo4j.get_node_by_id("test-arun-phase3")
    assert node is not None
    assert node["source_document_id"] == TEST_DOC_ID
    assert node["source_chunk_id"] == "chunk-0"
    
    # Verify relationship has provenance
    stats_before = neo4j.get_stats()
    assert stats_before["total_nodes"] == stats_initial["total_nodes"] + 3
    assert stats_before["total_relationships"] == stats_initial["total_relationships"] + 3
    
    # Second Ingest (Duplicate): Verify MERGE prevents duplication
    ent_cnt_dup, rel_cnt_dup = builder.ingest_extraction(
        extraction=extraction,
        document_id=TEST_DOC_ID,
        document_name=TEST_DOC_NAME,
        chunk_id="chunk-0"
    )
    # Check stats did not increase
    stats_after = neo4j.get_stats()
    assert stats_after["total_nodes"] == stats_before["total_nodes"]
    assert stats_after["total_relationships"] == stats_before["total_relationships"]

    # Clean up test nodes
    neo4j.execute_write("MATCH (n) WHERE n.id IN ['test-arun-phase3', 'test-project-alpha-phase3', $doc_id] DETACH DELETE n", {"doc_id": TEST_DOC_ID})


@pytest.mark.asyncio
async def test_graph_search_and_neighbors():
    """5. Test entity name/type search and neighbor expansion."""
    neo4j = get_neo4j()
    
    # Search Project Alpha
    nodes = neo4j.search_entities(query="Alpha", node_types=["Project"])
    assert len(nodes) > 0
    assert nodes[0]["name"] == "Project Alpha"
    
    # Neighbors expansion
    graph_data = neo4j.get_neighbors(node_id="arun")
    assert "nodes" in graph_data
    assert "edges" in graph_data
    
    # Validate adjacent project was returned
    neighbor_ids = {n["id"] for n in graph_data["nodes"]}
    assert "project-alpha" in neighbor_ids


@pytest.mark.asyncio
async def test_cascading_document_deletion_cleanup():
    """6. Test cascading delete of exclusive orphan nodes on document delete."""
    neo4j = get_neo4j()
    builder = GraphBuilder(neo4j)

    doc1_id = "doc-test-cascade-1"
    doc2_id = "doc-test-cascade-2"
    sarah_id = "sarah-test-cascade"
    john_id = "john-test-cascade"
    project_id = "project-test-cascade"

    # Clean only test entities if they exist
    neo4j.execute_write(
        "MATCH (n) WHERE n.id IN [$doc1, $doc2, $sarah, $john, $project] DETACH DELETE n",
        {"doc1": doc1_id, "doc2": doc2_id, "sarah": sarah_id, "john": john_id, "project": project_id}
    )

    doc1_extraction = {
        "entities": [
            {"id": sarah_id, "type": "Employee", "name": "Sarah", "properties": {}},
            {"id": project_id, "type": "Project", "name": "Project Cascade", "properties": {}}
        ],
        "relationships": [
            {"from_id": sarah_id, "from_type": "Employee", "rel_type": "WORKS_IN", "to_id": project_id, "to_type": "Project"}
        ]
    }

    doc2_extraction = {
        "entities": [
            {"id": john_id, "type": "Employee", "name": "John", "properties": {}},
            {"id": project_id, "type": "Project", "name": "Project Cascade", "properties": {}}
        ],
        "relationships": [
            {"from_id": john_id, "from_type": "Employee", "rel_type": "WORKS_IN", "to_id": project_id, "to_type": "Project"}
        ]
    }

    builder.ingest_extraction(doc1_extraction, doc1_id, "doc1.txt")
    builder.ingest_extraction(doc2_extraction, doc2_id, "doc2.txt")

    # Verify both documents ingested
    assert neo4j.get_node_by_id(sarah_id) is not None
    assert neo4j.get_node_by_id(john_id) is not None
    assert neo4j.get_node_by_id(project_id) is not None

    # Delete Document 1
    builder.delete_document_graph(doc1_id)

    # Verify cascading outcomes:
    # - doc1_id node is deleted.
    # - sarah_id node (exclusive to doc1) is deleted.
    # - john_id node (exclusive to doc2) is preserved.
    # - project_id (shared with doc2) is preserved!
    assert neo4j.get_node_by_id(doc1_id) is None
    assert neo4j.get_node_by_id(sarah_id) is None
    assert neo4j.get_node_by_id(john_id) is not None
    assert neo4j.get_node_by_id(project_id) is not None

    # Clean up test nodes
    neo4j.execute_write(
        "MATCH (n) WHERE n.id IN [$doc1, $doc2, $sarah, $john, $project] DETACH DELETE n",
        {"doc1": doc1_id, "doc2": doc2_id, "sarah": sarah_id, "john": john_id, "project": project_id}
    )
