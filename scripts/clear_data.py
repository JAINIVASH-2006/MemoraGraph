"""
MemoraGraph – Database Purge Utility
"""

import asyncio
import os
import sys

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.models.database import init_db, get_session
from app.models.document import Document, DocumentChunk
from app.models.query import Query, QuerySource, Feedback, AuditLog
from app.embeddings.vector_store import init_vector_store
from app.graph.neo4j_client import init_neo4j
from sqlalchemy import delete


async def clear_all_data():
    print("--- MemoraGraph: Database Clean Slate ---")
    
    # 1. Clear PostgreSQL
    print("Clearing PostgreSQL records...")
    init_db(settings.database_url)
    session_gen = get_session()
    session = await anext(session_gen)
    
    await session.execute(delete(Feedback))
    await session.execute(delete(QuerySource))
    await session.execute(delete(Query))
    await session.execute(delete(AuditLog))
    await session.execute(delete(DocumentChunk))
    await session.execute(delete(Document))
    await session.commit()
    print("PostgreSQL records cleared successfully.")
    
    # 2. Clear Neo4j
    print("Clearing Neo4j knowledge graph...")
    try:
        neo4j = init_neo4j(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
        )
        neo4j.execute_write("MATCH (n) DETACH DELETE n")
        print("Neo4j database cleared successfully.")
    except Exception as e:
        print(f"Warning: Failed to clear Neo4j: {e}")
        
    # 3. Clear Qdrant
    print("Clearing Qdrant vector index...")
    try:
        vector_store = init_vector_store(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection=settings.qdrant_collection,
        )
        # Recreate collection to wipe all vectors cleanly
        from app.embeddings.encoder import init_encoder
        encoder = init_encoder(settings.embedding_model)
        vector_store._client.delete_collection(settings.qdrant_collection)
        await vector_store.ensure_collection(encoder.dimension)
        print("Qdrant vectors cleared successfully.")
    except Exception as e:
        print(f"Warning: Failed to clear Qdrant: {e}")
        
    # 4. Clean upload folders
    doc_dir = os.path.join(settings.upload_dir, "synthetic")
    if os.path.exists(doc_dir):
        import shutil
        try:
            shutil.rmtree(doc_dir)
            print("Physical synthetic files deleted from disk.")
        except Exception as e:
            print(f"Warning: Failed to delete folders: {e}")
            
    print("\nAll database collections successfully cleared! You now have a clean system.")


if __name__ == "__main__":
    asyncio.run(clear_all_data())
