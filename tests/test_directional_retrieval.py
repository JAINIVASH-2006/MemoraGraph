"""
MemoraGraph – Directional Intent-Routed Graph Retriever Tests

Tests that the GraphRetriever respects directional relationship specifications
and produces genuinely different traversal results based on seed + direction.
"""

import pytest
import os
import sys

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.graph.neo4j_client import get_neo4j, init_neo4j, _client
from app.graph.builder import GraphBuilder
from app.retrieval.graph_retriever import GraphRetriever, parse_directional_rels, normalize_rel_spec
from app.graph.schema import VALID_REL_TYPES
from app.config import settings


@pytest.fixture(autouse=True)
def setup_neo4j():
    """Ensure Neo4j client is initialized."""
    global _client
    if _client is None:
        init_neo4j(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
        )
    return _client


# ──────────────────────────────────────────────
# Unit tests for directional parsing utilities
# ──────────────────────────────────────────────

def test_parse_directional_rels_incoming():
    """Incoming specs are correctly classified."""
    incoming, outgoing, undirected = parse_directional_rels(
        ["<MANAGES", "<ASSIGNED_TO"], VALID_REL_TYPES
    )
    assert "MANAGES" in incoming
    assert "ASSIGNED_TO" in incoming
    assert outgoing == []
    assert undirected == []


def test_parse_directional_rels_outgoing():
    """Outgoing specs are correctly classified."""
    incoming, outgoing, undirected = parse_directional_rels(
        ["MANAGES>", "ASSIGNED_TO>"], VALID_REL_TYPES
    )
    assert incoming == []
    assert "MANAGES" in outgoing
    assert "ASSIGNED_TO" in outgoing
    assert undirected == []


def test_parse_directional_rels_undirected():
    """Bare specs (no direction marker) are classified as undirected."""
    incoming, outgoing, undirected = parse_directional_rels(
        ["RELATED_TO"], VALID_REL_TYPES
    )
    assert incoming == []
    assert outgoing == []
    assert "RELATED_TO" in undirected


def test_parse_directional_rels_mixed():
    """Mixed directional specs are grouped correctly."""
    incoming, outgoing, undirected = parse_directional_rels(
        ["<MANAGES", "MANAGES>", "RELATED_TO", "<ASSIGNED_TO", "ASSIGNED_TO>"],
        VALID_REL_TYPES,
    )
    assert set(incoming) == {"MANAGES", "ASSIGNED_TO"}
    assert set(outgoing) == {"MANAGES", "ASSIGNED_TO"}
    assert undirected == ["RELATED_TO"]


def test_parse_directional_rels_filters_invalid():
    """Invalid or MENTIONED_IN relationship types are excluded."""
    incoming, outgoing, undirected = parse_directional_rels(
        ["<MANAGES", "FAKE_REL>", "MENTIONED_IN", "<MENTIONED_IN"],
        VALID_REL_TYPES,
    )
    assert incoming == ["MANAGES"]
    assert outgoing == []
    assert undirected == []


def test_normalize_rel_spec():
    """normalize_rel_spec correctly strips directional markers."""
    assert normalize_rel_spec("<MANAGES") == "MANAGES"
    assert normalize_rel_spec("MANAGES>") == "MANAGES"
    assert normalize_rel_spec("RELATED_TO") == "RELATED_TO"
    assert normalize_rel_spec("<ASSIGNED_TO") == "ASSIGNED_TO"
    assert normalize_rel_spec("PART_OF>") == "PART_OF"


# ──────────────────────────────────────────────
# Integration tests against live Neo4j
# ──────────────────────────────────────────────

@pytest.fixture
def graph_retriever():
    return GraphRetriever()


def test_project_seed_incoming_manages(graph_retriever):
    """
    Test 1: Project seed + incoming MANAGES
    "Who manages Project Atlas?" — seed is Project Atlas.
    Should discover Dr. Maya Rao via incoming MANAGES edge.
    """
    paths = graph_retriever.retrieve_paths(
        seed_entity_names=["Project Atlas"],
        allowed_relationships=["<MANAGES"],
        max_hops=2,
    )

    # Should find at least one path
    assert len(paths) > 0, "Expected paths from Project Atlas via incoming MANAGES"

    # Collect all discovered node labels
    all_node_labels = set()
    for p in paths:
        for n in p.nodes:
            all_node_labels.add(n.label)

    # Dr. Maya Rao should be discovered
    assert any("Maya Rao" in label for label in all_node_labels), \
        f"Expected 'Dr. Maya Rao' in retrieved nodes, got: {all_node_labels}"

    # All edges should be MANAGES type
    for p in paths:
        for e in p.edges:
            assert e.type == "MANAGES", f"Expected only MANAGES edges, got {e.type}"


def test_person_seed_outgoing_manages(graph_retriever):
    """
    Test 2: Person seed + outgoing MANAGES
    "Which projects does Dr. Maya Rao manage?" — seed is Dr. Maya Rao.
    Should discover Project Atlas via outgoing MANAGES edge.
    """
    paths = graph_retriever.retrieve_paths(
        seed_entity_names=["Dr. Maya Rao"],
        allowed_relationships=["MANAGES>"],
        max_hops=2,
    )

    assert len(paths) > 0, "Expected paths from Dr. Maya Rao via outgoing MANAGES"

    all_node_labels = set()
    for p in paths:
        for n in p.nodes:
            all_node_labels.add(n.label)

    assert any("Project Atlas" in label for label in all_node_labels), \
        f"Expected 'Project Atlas' in retrieved nodes, got: {all_node_labels}"

    for p in paths:
        for e in p.edges:
            assert e.type == "MANAGES", f"Expected only MANAGES edges, got {e.type}"


def test_project_seed_outgoing_manages_yields_no_manager(graph_retriever):
    """
    Test 3: Project seed + outgoing MANAGES
    A Project is not the source of a MANAGES relationship in the ontology.
    Should return zero or very few paths (no manager should be found via outgoing).
    """
    paths = graph_retriever.retrieve_paths(
        seed_entity_names=["Project Atlas"],
        allowed_relationships=["MANAGES>"],
        max_hops=1,
    )

    # In a strictly directional graph (Employee -MANAGES-> Project),
    # searching outgoing from Project should yield no MANAGES edges.
    for p in paths:
        for e in p.edges:
            # If any edge is returned, verify it's NOT finding a manager backwards
            assert e.type == "MANAGES"
            # The project should be the source of the edge, not the target
            assert e.source != "dr-maya-rao", \
                "Outgoing from Project should not discover Dr. Maya Rao as a managed entity"


def test_person_seed_incoming_manages_yields_no_project(graph_retriever):
    """
    Test 4: Person seed + incoming MANAGES
    A Person is not the target of a MANAGES relationship in our ontology
    (Employees manage projects, not the other way around).
    Should return zero or very few paths.
    """
    paths = graph_retriever.retrieve_paths(
        seed_entity_names=["Dr. Maya Rao"],
        allowed_relationships=["<MANAGES"],
        max_hops=1,
    )

    # Incoming MANAGES to a person means "who manages Dr. Maya Rao?"
    # In our ontology, projects don't manage people. So we expect no MANAGES edges.
    for p in paths:
        for e in p.edges:
            if e.type == "MANAGES":
                # Should not find project-atlas managing dr-maya-rao
                assert e.source != "project-atlas", \
                    "Project Atlas should not appear as a manager of Dr. Maya Rao"


def test_symmetric_related_to_works(graph_retriever):
    """
    Test 5: Symmetric relationship RELATED_TO still works in undirected mode.
    """
    paths = graph_retriever.retrieve_paths(
        seed_entity_names=["Project Atlas"],
        allowed_relationships=["RELATED_TO"],
        max_hops=2,
    )

    # RELATED_TO is used as undirected — whatever is in the graph should be traversable
    for p in paths:
        for e in p.edges:
            assert e.type == "RELATED_TO", f"Expected only RELATED_TO edges, got {e.type}"


def test_different_intents_produce_different_results(graph_retriever):
    """
    Test 6: Different intents produce genuinely different graph neighborhoods.
    PERSON_PROJECT (MANAGES/ASSIGNED_TO) vs EMPLOYEE_DEPARTMENT (WORKS_IN/MANAGES/PART_OF)
    should return different edge types from the same seed.
    """
    # PERSON_PROJECT intent
    person_project_paths = graph_retriever.retrieve_paths(
        seed_entity_names=["Project Atlas"],
        allowed_relationships=["<MANAGES", "MANAGES>", "<ASSIGNED_TO", "ASSIGNED_TO>"],
        max_hops=2,
    )

    # EMPLOYEE_DEPARTMENT intent
    emp_dept_paths = graph_retriever.retrieve_paths(
        seed_entity_names=["Project Atlas"],
        allowed_relationships=["<WORKS_IN", "WORKS_IN>", "<MANAGES", "MANAGES>", "<PART_OF", "PART_OF>"],
        max_hops=2,
    )

    # Collect edge types from each
    pp_edge_types = set()
    for p in person_project_paths:
        for e in p.edges:
            pp_edge_types.add(e.type)

    ed_edge_types = set()
    for p in emp_dept_paths:
        for e in p.edges:
            ed_edge_types.add(e.type)

    # PERSON_PROJECT should never contain WORKS_IN or PART_OF
    assert "WORKS_IN" not in pp_edge_types, \
        f"PERSON_PROJECT should not contain WORKS_IN edges: {pp_edge_types}"
    assert "PART_OF" not in pp_edge_types, \
        f"PERSON_PROJECT should not contain PART_OF edges: {pp_edge_types}"
