"""
MemoraGraph API – Knowledge Graph Explorer Endpoints

GET  /api/graph/entity/{id}   – View detailed entity properties
GET  /api/graph/neighbors/{id}– Retrieve adjacent nodes/relationships
POST /api/graph/search         – Search for entities
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.graph.neo4j_client import get_neo4j
from app.models.user import User, UserRole
from app.security.auth import get_current_user
from app.schemas.query import GraphNode, GraphEdge

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


class GraphSearchResponse(BaseModel):
    entities: List[GraphNode]


class NeighborResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


@router.get("/entity/{id}", response_model=GraphNode)
async def get_entity(
    id: str,
    current_user: User = Depends(get_current_user),
) -> GraphNode:
    """Retrieve detailed properties and labels of a single Neo4j node."""
    neo4j = get_neo4j()
    node = neo4j.get_node_by_id(id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity with ID '{id}' not found in the knowledge graph.",
        )
    
    types = node.pop("_types", ["Entity"])
    node_type = types[0] if types else "Entity"
    name = node.pop("name", id)

    return GraphNode(
        id=id,
        label=name,
        type=node_type,
        properties=node,
    )


@router.get("/neighbors/{id}", response_model=NeighborResponse)
async def get_neighbors(
    id: str,
    allowed_relations: Optional[str] = Query(None, description="Comma-separated relationship types"),
    current_user: User = Depends(get_current_user),
) -> NeighborResponse:
    """
    Expand adjacent nodes and relationships.
    Enables interactive exploration in the Knowledge Graph visualizer.
    """
    neo4j = get_neo4j()
    
    rel_list = None
    if allowed_relations:
        rel_list = [r.strip() for r in allowed_relations.split(",") if r.strip()]

    # Retrieve from Neo4j client with user scoping
    user_id = current_user.id if current_user.role != UserRole.ADMIN else None
    graph_data = neo4j.get_neighbors(node_id=id, allowed_rel_types=rel_list, user_id=user_id)

    nodes = []
    for n in graph_data["nodes"]:
        types = n.get("_types", ["Entity"])
        node_type = types[0] if types else "Entity"
        name = n.get("name", n.get("id", ""))
        nodes.append(
            GraphNode(
                id=n.get("id", ""),
                label=name,
                type=node_type,
                properties={k: v for k, v in n.items() if k not in ("id", "name", "_types")},
            )
        )

    edges = []
    for e in graph_data["edges"]:
        edges.append(
            GraphEdge(
                id=e.get("properties", {}).get("id", f"{e['from_id']}-{e['rel_type']}-{e['to_id']}"),
                source=e["from_id"],
                target=e["to_id"],
                type=e["rel_type"],
                properties={k: v for k, v in e["properties"].items() if k != "id"},
            )
        )

    return NeighborResponse(nodes=nodes, edges=edges)


class GraphStatsResponse(BaseModel):
    total_nodes: int
    total_relationships: int
    projects: int
    employees: int
    departments: int
    risks: int
    decisions: int
    meetings: int
    technologies: int


class GraphSearchRequest(BaseModel):
    query: str
    node_types: Optional[List[str]] = None


@router.post("/search", response_model=GraphSearchResponse)
async def search_graph_entities(
    req: GraphSearchRequest,
    current_user: User = Depends(get_current_user),
) -> GraphSearchResponse:
    """Search for matching nodes in the Neo4j knowledge graph with user isolation."""
    neo4j = get_neo4j()
    user_id = current_user.id if current_user.role != UserRole.ADMIN else None
    nodes = neo4j.search_entities(query=req.query, node_types=req.node_types, user_id=user_id)
    
    # Exclude document nodes if they are present or filter properly
    response_nodes = []
    for n in nodes:
        types = n.get("_types", ["Entity"])
        node_type = types[0] if types else "Entity"
        name = n.get("name", n.get("id", ""))
        response_nodes.append(
            GraphNode(
                id=n.get("id", ""),
                label=name,
                type=node_type,
                properties={k: v for k, v in n.items() if k not in ("id", "name", "_types")},
            )
        )

    return GraphSearchResponse(entities=response_nodes)


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats(
    current_user: User = Depends(get_current_user),
) -> GraphStatsResponse:
    """Retrieve count statistics from the Neo4j knowledge graph with user isolation."""
    neo4j = get_neo4j()
    user_id = current_user.id if current_user.role != UserRole.ADMIN else None
    stats = neo4j.get_stats(user_id=user_id)
    node_counts = stats.get("node_counts", {})
    
    return GraphStatsResponse(
        total_nodes=stats.get("total_nodes", 0),
        total_relationships=stats.get("total_relationships", 0),
        projects=node_counts.get("Project", 0),
        employees=node_counts.get("Employee", 0),
        departments=node_counts.get("Department", 0),
        risks=node_counts.get("Risk", 0),
        decisions=node_counts.get("Decision", 0),
        meetings=node_counts.get("Meeting", 0),
        technologies=node_counts.get("Technology", 0),
    )
