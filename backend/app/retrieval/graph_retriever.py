"""
MemoraGraph – Directed Edge-Routing Graph Retriever

Performs graph traversal in Neo4j starting from seed entities,
restricted to intent-allowed relationship types.
"""

import logging
from typing import List, Dict, Any, Set

from app.graph.neo4j_client import get_neo4j
from app.schemas.query import GraphPath, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class GraphRetriever:
    """Traverses Neo4j starting from seed entities, following directed edge routing rules."""

    def __init__(self):
        self._neo4j = get_neo4j()

    def retrieve_paths(
        self,
        seed_entity_names: List[str],
        allowed_relationships: List[str],
        max_hops: int = 2,
    ) -> List[GraphPath]:
        """
        Search for paths starting from entities matching seed_entity_names.
        Constrained by allowed_relationships.
        """
        if not seed_entity_names:
            return []

        # Find matching starting nodes in Neo4j
        # We search matching seed names (case-insensitive)
        seed_nodes = []
        for name in seed_entity_names:
            matches = self._neo4j.search_entities(name, limit=2)
            seed_nodes.extend(matches)

        if not seed_nodes:
            logger.debug("No seed nodes matched in Neo4j for names: %s", seed_entity_names)
            return []

        seed_ids = [n["id"] for n in seed_nodes]
        
        # Build Cypher path matching query
        # If allowed_relationships is empty, allow all relationship types
        if allowed_relationships:
            rel_filter = "|".join(allowed_relationships)
            rel_pattern = f"-[r:{rel_filter}*1..{max_hops}]-"
        else:
            rel_pattern = f"-[r*1..{max_hops}]-"

        cypher = (
            f"MATCH path = (startNode){rel_pattern}(endNode) "
            f"WHERE startNode.id IN $seed_ids AND startNode <> endNode "
            f"RETURN path, relationships(path) as rels, nodes(path) as ns "
            f"LIMIT 15"
        )

        try:
            results = self._neo4j.execute_query(cypher, {"seed_ids": seed_ids})
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
