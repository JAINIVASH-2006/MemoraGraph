import asyncio
from app.config import settings
from app.models.database import init_db, get_session
from app.models.document import Document, DocumentChunk
from app.embeddings.vector_store import init_vector_store
from app.graph.neo4j_client import init_neo4j
from sqlalchemy import select

async def inspect():
    init_db(settings.database_url)
    session_gen = get_session()
    session = await anext(session_gen)
    
    docs = (await session.execute(select(Document))).scalars().all()
    chunks = (await session.execute(select(DocumentChunk))).scalars().all()
    print(f"Postgres Documents: {len(docs)}")
    for d in docs:
        print(f"  Doc ID: {d.id} | Name: {d.name} | Chunks: {d.chunk_count}")
    print(f"Postgres Chunks: {len(chunks)}")
    for c in chunks:
        print(f"  Chunk ID: {c.id} | Doc: {c.document_id} | Chars: {len(c.text)}")

    vs = init_vector_store(settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection)
    info = vs._client.get_collection(settings.qdrant_collection)
    print(f"Qdrant Points Count: {info.points_count}")

    # Inspect points in Qdrant
    points, _ = vs._client.scroll(settings.qdrant_collection, limit=20, with_payload=True)
    print(f"Qdrant sample points (first {len(points)}):")
    for p in points:
        doc_id = p.payload.get("document_id") if p.payload else None
        chunk_id = p.payload.get("chunk_id") if p.payload else None
        name = p.payload.get("document_name") if p.payload else None
        print(f"  Point ID: {p.id} | Doc: {doc_id} | Chunk: {chunk_id} | Name: {name}")

    neo = init_neo4j(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    res_nodes = neo.execute_query("MATCH (n) RETURN count(n) as c")
    res_rels = neo.execute_query("MATCH ()-[r]->() RETURN count(r) as c")
    print(f"Neo4j Nodes: {res_nodes[0]['c']}")
    print(f"Neo4j Relationships: {res_rels[0]['c']}")
    
    # Check distinct relationship types in Neo4j
    rel_types = neo.execute_query("MATCH ()-[r]->() RETURN DISTINCT type(r) as t")
    print(f"Neo4j Relationship Types: {[r['t'] for r in rel_types]}")

    # Check distinct node labels in Neo4j
    labels = neo.execute_query("CALL db.labels() YIELD label RETURN label")
    print(f"Neo4j Labels: {[l['label'] for l in labels]}")

if __name__ == "__main__":
    asyncio.run(inspect())
