"""
MemoraGraph – Database Seeder Script

Creates synthetic organizational document files on disk, inserts ORM entities in PostgreSQL,
runs offline SentenceTransformer embeddings to populate Qdrant, and runs Cypher to construct
the knowledge graph relationships directly in Neo4j.

This guarantees a fully operational system immediately, even if no LLM API key is present.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.models.database import init_db, get_session, create_tables
from app.models.user import User, UserRole
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.security.auth import hash_password
from app.embeddings.encoder import init_encoder, get_encoder
from app.embeddings.vector_store import init_vector_store, VectorChunk
from app.graph.neo4j_client import init_neo4j, get_neo4j

# Synthetic Document Templates
DOCUMENTS_CONTENT = {
    "project_alpha_report.txt": (
        "[SYNTHETIC DEVELOPMENT DATA]\n"
        "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
        "Project: Project Alpha\n"
        "Department: Engineering\n"
        "Date: 2025-01-10\n"
        "Author: Arun\n"
        "\n"
        "Project Alpha is our primary engineering project focused on building the core API gateway. "
        "Arun manages Project Alpha in the Engineering department. The project kickoff occurred on "
        "January 10, 2025. Priya is the primary designer, and Karthik is lead developer. The project "
        "is critical for our infrastructure modernization effort."
    ),
    "security_incident.txt": (
        "[SYNTHETIC DEVELOPMENT DATA]\n"
        "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
        "Project: Project Alpha\n"
        "Department: Operations\n"
        "Date: 2025-02-14\n"
        "Author: Karthik\n"
        "\n"
        "A severe database security incident occurred on February 14, 2025, in Project Alpha. "
        "Lead developer Karthik reported a security risk regarding exposed local credentials "
        "in the repository configuration. This issue created a critical vulnerability, posing "
        "a budget risk due to potential data loss penalties."
    ),
    "project_alpha_meeting.txt": (
        "[SYNTHETIC DEVELOPMENT DATA]\n"
        "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
        "Project: Project Alpha\n"
        "Department: Engineering\n"
        "Date: 2025-02-20\n"
        "Author: Arun\n"
        "\n"
        "A management meeting was held on February 20, 2025, to discuss the security incident in Project Alpha. "
        "Arun, Priya, and Karthik attended. The meeting discussed migrating the database infrastructure "
        "to a cloud environment. Karthik proposed migrating database servers to AWS as a mitigation path."
    ),
    "decision_record.txt": (
        "[SYNTHETIC DEVELOPMENT DATA]\n"
        "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
        "Project: Project Alpha\n"
        "Department: Engineering\n"
        "Date: 2025-02-25\n"
        "Author: Arun\n"
        "\n"
        "On February 25, 2025, project manager Arun approved the Cloud Migration decision. "
        "The migration will move all backend services and postgres databases to AWS. This decision "
        "was approved to resolve the database security risk and mitigate credentials exposure. "
        "The cloud migration successfully resulted in a secure system upgrade on March 10, 2025."
    ),
    "project_beta_report.txt": (
        "[SYNTHETIC DEVELOPMENT DATA]\n"
        "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
        "Project: Project Beta\n"
        "Department: Finance\n"
        "Date: 2025-03-01\n"
        "Author: Priya\n"
        "\n"
        "Project Beta is directed at automating financial forecasting led by department head Priya. "
        "The project has encountered a budget risk. Priya and Meena are investigating mitigation options, "
        "including budget reductions. The project has a direct dependency on the API gateway built in Project Alpha."
    )
}


async def seed_users(session) -> dict:
    """Create default mock users with distinct roles."""
    roles = {
        "admin@memoragraph.com": ("Admin User", UserRole.ADMIN),
        "manager@memoragraph.com": ("Arun Manager", UserRole.MANAGER),
        "employee@memoragraph.com": ("Karthik Developer", UserRole.EMPLOYEE),
        "priya@memoragraph.com": ("Priya Designer", UserRole.MANAGER),
    }
    
    # Delete existing default users to prevent unique constraint failures
    from sqlalchemy import delete
    await session.execute(delete(User).where(User.email.in_(list(roles.keys()))))
    await session.flush()
    
    user_map = {}
    for email, (name, role) in roles.items():
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hash_password("memoragraph"),
            name=name,
            role=role,
            is_active=True,
        )
        session.add(user)
        user_map[email] = user
        print(f"Seeded User: {email} (role: {role.value})")
    
    await session.flush()
    return user_map


async def main():
    print("Initializing databases for seeding...")
    init_db(settings.database_url)
    await create_tables()

    # Create session
    session_gen = get_session()
    session = await anext(session_gen)

    # Clean up old documents/chunks/query history to avoid UniqueViolationError
    from sqlalchemy import delete
    from app.models.query import Query, QuerySource, Feedback, AuditLog
    await session.execute(delete(Feedback))
    await session.execute(delete(QuerySource))
    await session.execute(delete(Query))
    await session.execute(delete(AuditLog))
    await session.execute(delete(DocumentChunk))
    await session.execute(delete(Document))
    await session.flush()

    # 1. Seed Users
    print("\n--- Seeding Users ---")
    user_map = await seed_users(session)

    # 2. Setup folders
    doc_dir = os.path.join(settings.upload_dir, "synthetic")
    os.makedirs(doc_dir, exist_ok=True)

    # 3. Initialize Embedding Encoder and Qdrant
    print("\n--- Seeding Embeddings & Qdrant ---")
    encoder = init_encoder(settings.embedding_model)
    vector_store = init_vector_store(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection=settings.qdrant_collection,
    )
    await vector_store.ensure_collection(encoder.dimension)

    # Initialize Neo4j
    print("\n--- Seeding Neo4j Knowledge Graph ---")
    neo4j = init_neo4j(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )
    neo4j.ensure_constraints()

    # Clear old graph data for seeder idempotency
    try:
        neo4j.execute_write("MATCH (n) DETACH DELETE n")
        print("Cleared existing Neo4j knowledge graph data.")
    except Exception as e:
        print("Warning: could not clear Neo4j graph:", e)

    doc_ids = {
        "project_alpha_report.txt": "doc-alpha-report",
        "security_incident.txt": "doc-security-incident",
        "project_alpha_meeting.txt": "doc-alpha-meeting",
        "decision_record.txt": "doc-decision-record",
        "project_beta_report.txt": "doc-beta-report",
    }

    # 4. Ingest Documents
    print("\n--- Seeding Documents ---")
    for filename, content in DOCUMENTS_CONTENT.items():
        doc_id = doc_ids[filename]
        file_path = os.path.join(doc_dir, filename)
        
        # Write to disk
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Basic metadata parser
        department = "Engineering"
        project = "Project Alpha"
        if "Beta" in content:
            department = "Finance"
            project = "Project Beta"
        elif "security_incident" in filename:
            department = "Operations"

        # Save document record
        db_doc = Document(
            id=doc_id,
            name=filename.replace(".txt", "").replace("_", " ").title(),
            original_filename=filename,
            file_type="TXT",
            file_size_bytes=len(content),
            file_path=file_path,
            status=DocumentStatus.PROCESSED,
            department=department,
            project=project,
            chunk_count=1,
            uploaded_by=user_map["admin@memoragraph.com"].id,
            processed_at=datetime.now(timezone.utc),
        )
        session.add(db_doc)

        # Save document chunk
        chunk_id = f"{doc_id}-c0"
        db_chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            chunk_index=0,
            text=content,
            char_start=0,
            char_end=len(content),
            token_count=len(content) // 4,
            embedding_id=chunk_id,
        )
        session.add(db_chunk)

        # Create Qdrant embedding
        emb = encoder.encode_single(content)
        await vector_store.upsert_chunks([
            VectorChunk(
                chunk_id=chunk_id,
                document_id=doc_id,
                document_name=db_doc.name,
                text=content,
                embedding=emb,
                metadata={"project": project, "department": department, "filename": filename},
            )
        ])
        print(f"Ingested document into PostgreSQL and Qdrant: {filename}")

    await session.commit()

    # 5. Populate Neo4j Knowledge Graph relationships
    # Directly seeding using Cypher, avoiding LLM calls
    print("\n--- Seeding Graph Relations ---")
    try:
        # Create Nodes
        nodes = [
            # Employees
            ("Employee", "arun", {"name": "Arun", "role": "Project Manager"}),
            ("Employee", "priya", {"name": "Priya", "role": "Designer"}),
            ("Employee", "karthik", {"name": "Karthik", "role": "Developer"}),
            ("Employee", "meena", {"name": "Meena", "role": "Financial Analyst"}),
            # Departments
            ("Department", "engineering", {"name": "Engineering"}),
            ("Department", "operations", {"name": "Operations"}),
            ("Department", "finance", {"name": "Finance"}),
            # Projects
            ("Project", "project-alpha", {"name": "Project Alpha", "status": "Active"}),
            ("Project", "project-beta", {"name": "Project Beta", "status": "Planning"}),
            # Risks
            ("Risk", "security-risk", {"name": "Security Risk", "severity": "Critical", "description": "Exposed repository database credentials"}),
            ("Risk", "budget-risk", {"name": "Budget Risk", "severity": "Medium", "description": "Risk of project overruns"}),
            # Meetings
            ("Meeting", "management-meeting", {"name": "Management Meeting", "date": "2025-02-20"}),
            # Decisions
            ("Decision", "cloud-migration", {"name": "Cloud Migration", "status": "Approved", "date": "2025-02-25"}),
            # Outcomes
            ("Outcome", "security-resolution", {"name": "System Upgrade", "status": "Resolved", "date": "2025-03-10"}),
            # Events (Timeline)
            ("Event", "evt-1", {"name": "Project Alpha Kickoff", "date": "2025-01-10", "description": "Project Alpha officially started."}),
            ("Event", "evt-2", {"name": "Security Risk Identified", "date": "2025-02-14", "description": "Security Risk detected concerning local database credentials."}),
            ("Event", "evt-3", {"name": "Management Meeting Held", "date": "2025-02-20", "description": "Team aligned on cloud migration strategy."}),
            ("Event", "evt-4", {"name": "Cloud Migration Approved", "date": "2025-02-25", "description": "Decision approved to migrate database infrastructure."}),
            ("Event", "evt-5", {"name": "Security Risk Resolved", "date": "2025-03-10", "description": "Security Risk resolved via cloud upgrade."}),
        ]

        for label, node_id, props in nodes:
            neo4j.merge_node(label, node_id, props)
            # Link to generic Document node if relevant
            if "alpha" in node_id or "security" in node_id:
                neo4j.merge_node("Document", "doc-alpha-report", {"name": "Project Alpha Report"})
                neo4j.merge_relationship(label, node_id, "MENTIONED_IN", "Document", "doc-alpha-report")

        # Create Relationships
        relationships = [
            ("Employee", "arun", "WORKS_IN", "Department", "engineering"),
            ("Employee", "karthik", "WORKS_IN", "Department", "engineering"),
            ("Employee", "priya", "WORKS_IN", "Department", "finance"),
            ("Employee", "meena", "WORKS_IN", "Department", "finance"),
            
            ("Employee", "arun", "MANAGES", "Project", "project-alpha"),
            ("Employee", "priya", "MANAGES", "Project", "project-beta"),
            
            ("Project", "project-alpha", "PART_OF", "Department", "engineering"),
            ("Project", "project-beta", "PART_OF", "Department", "finance"),
            
            ("Project", "project-alpha", "HAS_RISK", "Risk", "security-risk"),
            ("Project", "project-beta", "HAS_RISK", "Risk", "budget-risk"),
            
            ("Meeting", "management-meeting", "DISCUSSED_IN", "Project", "project-alpha"),
            ("Meeting", "management-meeting", "INVOLVES", "Employee", "arun"),
            ("Meeting", "management-meeting", "INVOLVES", "Employee", "karthik"),
            
            ("Decision", "cloud-migration", "APPROVED", "Project", "project-alpha"),
            ("Decision", "cloud-migration", "RESULTED_IN", "Outcome", "security-resolution"),
            ("Risk", "security-risk", "RESOLVED_BY", "Decision", "cloud-migration"),
            
            ("Project", "project-beta", "DEPENDS_ON", "Project", "project-alpha"),
        ]

        for from_lbl, from_id, rel, to_lbl, to_id in relationships:
            neo4j.merge_relationship(from_lbl, from_id, rel, to_lbl, to_id)

        print("Neo4j knowledge graph seeded successfully.")
    except Exception as e:
        print("Error populating Neo4j:", e)

    print("\nAll database seeding operations completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
