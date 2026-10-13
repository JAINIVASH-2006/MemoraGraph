"""
MemoraGraph – Directed Edge-Routing Graph Retriever

Performs graph traversal in Neo4j starting from seed entities,
restricted to intent-allowed relationship types and directions.

Directional relationship specification format:
  "<REL"  = incoming  (traverse ()<-[:REL]-())
  "REL>"  = outgoing  (traverse ()-[:REL]->())
  "REL"   = undirected (traverse ()-[:REL]-())
"""

import logging
from typing import List, Dict, Any, Set, Optional, Tuple

from app.graph.neo4j_client import get_neo4j
from app.schemas.query import GraphPath, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


def parse_directional_rels(
    allowed_relationships: List[str],
    valid_rel_types: Set[str],
) -> Tuple[List[str], List[str], List[str]]:
    """
    Parse directional relationship specifications into three groups.

    Args:
        allowed_relationships: List of directional specs like ["<MANAGES", "MANAGES>", "RELATED_TO"]
        valid_rel_types: Set of valid relationship type names from the graph schema.

    Returns:
        (incoming_rels, outgoing_rels, undirected_rels) — each a list of bare relationship names.
    """
    incoming = []
    outgoing = []
    undirected = []

    for rel_spec in allowed_relationships:
        if rel_spec.startswith("<"):
            rel_name = rel_spec[1:]
            if rel_name in valid_rel_types and rel_name != "MENTIONED_IN":
                incoming.append(rel_name)
        elif rel_spec.endswith(">"):
            rel_name = rel_spec[:-1]
            if rel_name in valid_rel_types and rel_name != "MENTIONED_IN":
                outgoing.append(rel_name)
        else:
            rel_name = rel_spec
            if rel_name in valid_rel_types and rel_name != "MENTIONED_IN":
                undirected.append(rel_name)

    return incoming, outgoing, undirected


def normalize_rel_spec(rel_spec: str) -> str:
    """Strip directional markers from a relationship specification.

    Examples:
        "<MANAGES" -> "MANAGES"
        "MANAGES>" -> "MANAGES"
        "RELATED_TO" -> "RELATED_TO"
    """
    if rel_spec.startswith("<"):
        return rel_spec[1:]
    elif rel_spec.endswith(">"):
        return rel_spec[:-1]
    return rel_spec


class GraphRetriever:
    """Traverses Neo4j starting from seed entities, following directed edge routing rules."""

    def __init__(self):
        self._neo4j = get_neo4j()

    def retrieve_paths(
        self,
        seed_entity_names: List[str],
        allowed_relationships: List[str],
        max_hops: int = 2,
        user_id: Optional[str] = None,
    ) -> List[GraphPath]:
        """
        Search for paths starting from entities matching seed_entity_names.
        Constrained by allowed_relationships (with directional specs) and user isolation.

        Directional specs:
          "<REL"  = incoming only
          "REL>"  = outgoing only
          "REL"   = undirected/both
        """
        if not seed_entity_names:
            return []

        # Find matching starting nodes in Neo4j
        seed_nodes = []
        for name in seed_entity_names:
            matches = self._neo4j.search_entities(name, limit=2, user_id=user_id)
            seed_nodes.extend(matches)

        if not seed_nodes:
            logger.debug("No seed nodes matched in Neo4j for names: %s", seed_entity_names)
            return []

        seed_ids = [n["id"] for n in seed_nodes]

        # Build Cypher query with directional awareness
        from app.graph.schema import VALID_REL_TYPES
        semantic_rel_types = [r for r in VALID_REL_TYPES if r != "MENTIONED_IN"]

        user_filter = (
            "AND (startNode.user_id = $user_id OR startNode.user_id IS NULL) "
            "AND (endNode.user_id = $user_id OR endNode.user_id IS NULL) "
            if user_id else ""
        )
        params: Dict[str, Any] = {"seed_ids": seed_ids}
        if user_id:
            params["user_id"] = user_id

        if allowed_relationships:
            incoming, outgoing, undirected = parse_directional_rels(
                allowed_relationships, VALID_REL_TYPES
            )

            # Build UNION of up to 3 directional sub-queries
            sub_queries = []

            if incoming:
                rel_filter = "|".join(incoming)
                sub_queries.append(
                    f"MATCH path = (startNode)<-[:{rel_filter}*1..{max_hops}]-(endNode) "
                    f"WHERE startNode.id IN $seed_ids AND startNode <> endNode "
                    f"{user_filter}"
                    f"RETURN path, relationships(path) as rels, nodes(path) as ns "
                    f"LIMIT 15"
                )

            if outgoing:
                rel_filter = "|".join(outgoing)
                sub_queries.append(
                    f"MATCH path = (startNode)-[:{rel_filter}*1..{max_hops}]->(endNode) "
                    f"WHERE startNode.id IN $seed_ids AND startNode <> endNode "
                    f"{user_filter}"
                    f"RETURN path, relationships(path) as rels, nodes(path) as ns "
                    f"LIMIT 15"
                )

            if undirected:
                rel_filter = "|".join(undirected)
                sub_queries.append(
                    f"MATCH path = (startNode)-[:{rel_filter}*1..{max_hops}]-(endNode) "
                    f"WHERE startNode.id IN $seed_ids AND startNode <> endNode "
                    f"{user_filter}"
                    f"RETURN path, relationships(path) as rels, nodes(path) as ns "
                    f"LIMIT 15"
                )

            if not sub_queries:
                # All specs were invalid; fall back to undirected semantic traversal
                rel_filter = "|".join(semantic_rel_types)
                cypher = (
                    f"MATCH path = (startNode)-[:{rel_filter}*1..{max_hops}]-(endNode) "
                    f"WHERE startNode.id IN $seed_ids AND startNode <> endNode "
                    f"{user_filter}"
                    f"RETURN path, relationships(path) as rels, nodes(path) as ns "
                    f"LIMIT 15"
                )
            else:
                cypher = " UNION ".join(sub_queries)
        else:
            # GENERAL_INFORMATION fallback: traverse all semantic relationships undirected
            rel_filter = "|".join(semantic_rel_types)
            cypher = (
                f"MATCH path = (startNode)-[:{rel_filter}*1..{max_hops}]-(endNode) "
                f"WHERE startNode.id IN $seed_ids AND startNode <> endNode "
                f"{user_filter}"
                f"RETURN path, relationships(path) as rels, nodes(path) as ns "
                f"LIMIT 15"
            )

        logger.debug("Directional graph retrieval Cypher: %s", cypher)

        try:
            results = self._neo4j.execute_query(cypher, params)
            paths = []

            for record in results:
                nodes_in_path = record["ns"]
                rels_in_path = record["rels"]

                path_nodes = []
                for n in nodes_in_path:
                    # Convert to Pydantic node schema
                    labels = list(n.labels)
                    node_type = labels[0] if labels else "Entity"
                    props = dict(n)
                    path_nodes.append(
                        GraphNode(
                            id=props.get("id", ""),
                            label=props.get("name", props.get("id", "")),
                            type=node_type,
                            properties={k: v for k, v in props.items() if k not in ("id", "name")},
                        )
                    )

                path_edges = []
                for r in rels_in_path:
                    # Get start/end node ids
                    start_node = r.start_node
                    end_node = r.end_node
                    start_id = dict(start_node).get("id")
                    end_id = dict(end_node).get("id")
                    
                    props = dict(r)
                    path_edges.append(
                        GraphEdge(
                            id=str(r.element_id) if hasattr(r, "element_id") else f"{start_id}-{r.type}-{end_id}",
                            source=start_id,
                            target=end_id,
                            type=r.type,
                            properties=props,
                        )
                    )

                # Assemble textual description of the path
                path_desc = " -> ".join(
                    f"({n.type}: {n.label})" if i == 0 else f"-[{path_edges[i-1].type}]-> ({n.type}: {n.label})"
                    for i, n in enumerate(path_nodes)
                )

                paths.append(
                    GraphPath(
                        nodes=path_nodes,
                        edges=path_edges,
                        description=path_desc,
                    )
                )

            logger.info("Retrieved %d paths from Neo4j matching seed nodes", len(paths))
            return paths

        except Exception as e:
            logger.error("Failed to retrieve paths from Neo4j: %s", e)
            return []
