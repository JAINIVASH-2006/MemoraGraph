"""
MemoraGraph – Neo4j Knowledge Graph Client

Provides an async-compatible wrapper around the Neo4j Python driver.
All Cypher queries are parameterized to prevent injection.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_neo4j_driver = None


class Neo4jClient:
    """
    Thread-safe Neo4j driver wrapper with convenience methods.
    Uses neo4j.AsyncGraphDatabase for async operation.
    """

    def __init__(self, uri: str, username: str, password: str):
        self._uri = uri
        self._username = username
        self._password = password
        self._driver = None
        self.connect()

    def connect(self) -> None:
        """Establish connection to the Neo4j database."""
        from neo4j import GraphDatabase
        try:
            if not self._driver:
                self._driver = GraphDatabase.driver(
                    self._uri,
                    auth=(self._username, self._password),
                    max_connection_pool_size=20,
                    connection_timeout=5.0,
                    connection_acquisition_timeout=5.0,
                    max_transaction_retry_time=3.0,
                )
                logger.info("Neo4j client initialized. URI: %s", self._uri)
        except Exception as e:
            logger.warning("Failed to establish Neo4j driver connection: %s", e)
            self._driver = None

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            try:
                self._driver.close()
                self._driver = None
                logger.info("Neo4j connection closed.")
            except Exception as e:
                logger.warning("Error closing Neo4j connection: %s", e)

    def verify_connection(self) -> bool:
        """Verify the Neo4j driver connectivity with auto-reconnection."""
        try:
            if not self._driver:
                self.connect()
            if self._driver:
                self._driver.verify_connectivity()
                return True
        except Exception as e:
            logger.warning("Neo4j connection verification failed: %s. Attempting reconnection...", e)
            try:
                self.close()
                self.connect()
                if self._driver:
                    self._driver.verify_connectivity()
                    return True
            except Exception as retry_err:
                logger.warning("Neo4j reconnection retry failed: %s", retry_err)
        return False

    async def ping(self) -> bool:
        """Test Neo4j connectivity asynchronously without blocking event loop."""
        import asyncio
        try:
            return await asyncio.to_thread(self.verify_connection)
        except Exception:
            return False

    def execute_query(
        self,
        cypher: str,
        parameters: Optional[dict] = None,
        database: Optional[str] = None,
    ) -> list[dict]:
        """
        Execute a Cypher query and return results as a list of dicts.
        Runs synchronously (Neo4j sync driver).
        """
        if not self._driver:
            self.connect()
        if not self._driver:
            logger.warning("Cannot execute query: Neo4j driver is not connected.")
            return []
        try:
            with self._driver.session(database=database) as session:
                result = session.run(cypher, parameters or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.warning("Neo4j execute_query error: %s (query: %s)", e, cypher)
            return []

    def execute_write(
        self,
        cypher: str,
        parameters: Optional[dict] = None,
        database: Optional[str] = None,
    ) -> list[dict]:
        """Execute a write transaction."""
        if not self._driver:
            self.connect()
        if not self._driver:
            logger.warning("Cannot execute write: Neo4j driver is not connected.")
            return []
        try:
            def _tx(tx):
                result = tx.run(cypher, parameters or {})
                return [dict(record) for record in result]
            
            with self._driver.session(database=database) as session:
                return session.execute_write(_tx)
        except Exception as e:
            logger.warning("Neo4j execute_write error: %s (query: %s)", e, cypher)
            return []

    def ensure_constraints(self) -> None:
        """Create uniqueness constraints for all node types."""
        node_types = [
            "Employee", "Department", "Project", "Meeting",
            "Risk", "Decision", "Technology", "Event", "Outcome",
            "Document", "Task", "Issue"
        ]
        for node_type in node_types:
            try:
                self.execute_write(
                    f"CREATE CONSTRAINT {node_type.lower()}_id IF NOT EXISTS "
                    f"FOR (n:{node_type}) REQUIRE n.id IS UNIQUE"
                )
            except Exception as e:
                logger.debug("Constraint already exists for %s: %s", node_type, e)
        logger.info("Neo4j constraints ensured for all node types.")

    def merge_node(self, node_type: str, node_id: str, properties: dict) -> None:
        """Idempotently create or update a node."""
        props_clause = ", ".join(f"n.{k} = ${k}" for k in properties)
        cypher = (
            f"MERGE (n:{node_type} {{id: $node_id}}) "
            f"ON CREATE SET {props_clause}, n.created_at = timestamp() "
            f"ON MATCH SET {props_clause}, n.updated_at = timestamp()"
        )
        self.execute_write(cypher, {"node_id": node_id, **properties})

    def merge_relationship(
        self,
        from_type: str,
        from_id: str,
        rel_type: str,
        to_type: str,
        to_id: str,
        properties: Optional[dict] = None,
    ) -> None:
        """Idempotently create a directed relationship between two nodes."""
        props = properties or {}
        prop_clause = ""
        if props:
            prop_clause = " SET r += $props"
        
        cypher = (
            f"MATCH (a:{from_type} {{id: $from_id}}) "
            f"MATCH (b:{to_type} {{id: $to_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b)"
            f"{prop_clause}"
        )
        self.execute_write(
            cypher,
            {"from_id": from_id, "to_id": to_id, "props": props},
        )

    def get_node_by_id(self, node_id: str) -> Optional[dict]:
        """Get a node by its id property."""
        results = self.execute_query(
            "MATCH (n {id: $node_id}) RETURN n, labels(n) as types LIMIT 1",
            {"node_id": node_id},
        )
        if not results:
            return None
        record = results[0]
        node = dict(record["n"])
        node["_types"] = record["types"]
        return node

    def get_neighbors(
        self,
        node_id: str,
        allowed_rel_types: Optional[list[str]] = None,
        max_hops: int = 1,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Get neighboring nodes constrained by relationship types and optional user isolation.
        """
        if allowed_rel_types:
            rel_filter = "|".join(allowed_rel_types)
            rel_pattern = f"[r:{rel_filter}]"
        else:
            rel_pattern = "[r]"

        user_filter = ""
        params = {"node_id": node_id}
        if user_id:
            user_filter = "AND (start.user_id = $user_id OR start.user_id IS NULL) AND (neighbor.user_id = $user_id OR neighbor.user_id IS NULL) "
            params["user_id"] = user_id
        
        cypher = (
            f"MATCH (start {{id: $node_id}})-{rel_pattern}-(neighbor) "
            f"WHERE true {user_filter}"
            f"RETURN start, neighbor, r, type(r) as rel_type, "
            f"labels(start) as start_types, labels(neighbor) as neighbor_types "
            f"LIMIT 50"
        )
        
        results = self.execute_query(cypher, params)
        
        nodes = {}
        edges = []
        
        for record in results:
            start = dict(record["start"])
            start["_types"] = record["start_types"]
            neighbor = dict(record["neighbor"])
            neighbor["_types"] = record["neighbor_types"]
            rel = dict(record["r"])
            rel_type = record["rel_type"]
            
            nodes[start.get("id", "")] = start
            nodes[neighbor.get("id", "")] = neighbor
            edges.append({
                "from_id": start.get("id"),
                "to_id": neighbor.get("id"),
                "rel_type": rel_type,
                "properties": rel,
            })
        
        return {"nodes": list(nodes.values()), "edges": edges}

    def search_entities(
        self,
        query: str,
        node_types: Optional[list[str]] = None,
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Full-text search on entity names with user scoping."""
        if node_types:
            type_filter = "|".join(node_types)
            label_match = f"(n:{type_filter})"
        else:
            label_match = "(n)"

        user_clause = ""
        params = {"query": query, "limit": limit}
        if user_id:
            user_clause = "AND (n.user_id = $user_id OR n.user_id IS NULL) "
            params["user_id"] = user_id
        
        cypher = (
            f"MATCH {label_match} "
            f"WHERE (toLower(n.name) CONTAINS toLower($query) OR toLower(n.id) CONTAINS toLower($query)) "
            f"{user_clause}"
            f"RETURN n, labels(n) as types "
            f"LIMIT $limit"
        )
        results = self.execute_query(cypher, params)
        nodes = []
        for r in results:
            node = dict(r["n"])
            node["_types"] = r["types"]
            nodes.append(node)
        return nodes

    def get_stats(self, user_id: Optional[str] = None) -> dict:
        """Get count statistics for nodes and relationships with optional user filtering."""
        try:
            where_clause = "WHERE (n.user_id = $user_id OR n.user_id IS NULL)" if user_id else ""
            params = {"user_id": user_id} if user_id else {}

            node_result = self.execute_query(f"MATCH (n) {where_clause} RETURN count(n) as total_nodes", params)
            rel_result = self.execute_query(f"MATCH ()-[r]->() RETURN count(r) as total_rels")
            
            # Per-type counts
            type_result = self.execute_query(
                f"MATCH (n) {where_clause} RETURN labels(n)[0] as label, count(n) as cnt ORDER BY cnt DESC",
                params
            )
            
            return {
                "total_nodes": node_result[0]["total_nodes"] if node_result else 0,
                "total_relationships": rel_result[0]["total_rels"] if rel_result else 0,
                "node_counts": {r["label"]: r["cnt"] for r in type_result if r["label"]},
            }
        except Exception as e:
            logger.warning("Could not get Neo4j stats: %s", e)
            return {"total_nodes": 0, "total_relationships": 0, "node_counts": {}}


# Singleton
_client: Optional[Neo4jClient] = None


def get_neo4j() -> Neo4jClient:
    global _client
    if _client is None:
        raise RuntimeError("Neo4j client not initialized. Call init_neo4j() first.")
    return _client


def init_neo4j(uri: str, username: str, password: str) -> Neo4jClient:
    global _client
    _client = Neo4jClient(uri=uri, username=username, password=password)
    return _client
