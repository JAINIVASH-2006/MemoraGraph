import sys, os, asyncio
sys.path.insert(0, r'd:\Memoragraph\backend')
from app.config import settings
import app.models.database as db_mod
from app.embeddings.encoder import init_encoder
from app.embeddings.vector_store import init_vector_store
from app.graph.neo4j_client import init_neo4j, get_neo4j
from app.llm.provider import init_llm_provider
from app.ingestion.pipeline import _run_pipeline

async def main():
    db_mod.init_db(settings.database_url)
    init_encoder(settings.embedding_model)
    init_vector_store(settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection)
    neo4j = init_neo4j(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)
    init_llm_provider(settings.llm_provider, settings.llm_api_key, settings.llm_model)

    doc_id = 'a1c0c984-4ba6-4fe0-b175-751f2d4e44f9'
    print(f'Starting pipeline for document {doc_id}...')
    async with db_mod._async_session_factory() as session:
        await _run_pipeline(doc_id, session)

    print('\nPipeline completed! Checking Neo4j contents:')
    counts = neo4j.execute_query('MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as cnt ORDER BY cnt DESC')
    print('\n--- RELATIONSHIP TYPE COUNTS ---')
    for c in counts:
        print(f"  {c['rel_type']}: {c['cnt']}")

    semantic_rels = neo4j.execute_query(
        "MATCH (a)-[r]->(b) WHERE type(r) <> 'MENTIONED_IN' RETURN a.name as source_name, labels(a)[0] as source_type, type(r) as rel_type, b.name as target_name, labels(b)[0] as target_type LIMIT 50"
    )
    print(f"\n--- SEMANTIC RELATIONSHIPS (Found: {len(semantic_rels)}) ---")
    for r in semantic_rels:
        print(f"  ({r['source_type']}: {r['source_name']}) -[{r['rel_type']}]-> ({r['target_type']}: {r['target_name']})")

if __name__ == '__main__':
    asyncio.run(main())
