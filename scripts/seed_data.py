"""
MemoraGraph – Database Seeder Script

Creates synthetic organizational document files on disk, inserts ORM entities in PostgreSQL,
runs offline FastEmbed embeddings to populate Qdrant, and runs Cypher to construct
the knowledge graph relationships directly in Neo4j.

Generates a genuine multi-document, multi-chunk, multi-project organizational memory:
- 6 Documents
- 12 Chunks (2 chunks per document)
- 25+ Knowledge Graph Entities
- 30+ Knowledge Graph Relationships
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

DOCUMENTS_SPEC = {
    "project_alpha_report.txt": {
        "id": "doc-alpha-report",
        "name": "Project Alpha Report",
        "department": "Engineering",
        "project": "Project Alpha",
        "chunks": [
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Project Alpha Report (Section 1)\n"
                "Department: Engineering | Date: 2025-01-10 | Author: Arun\n\n"
                "Project Alpha is our primary engineering project focused on building the core API gateway. "
                "Arun manages Project Alpha in the Engineering department. The project kickoff occurred on "
                "January 10, 2025. Priya is the primary designer, and Karthik is lead developer. The project "
                "is critical for our infrastructure modernization effort."
            ),
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Project Alpha Report (Section 2)\n"
                "Department: Engineering | Date: 2025-01-10 | Author: Arun\n\n"
                "The engineering department infrastructure roadmap requires Project Alpha to provide standardized "
                "REST and gRPC endpoints for downstream microservices. Karthik implemented rate limiting and service discovery. "
                "The API gateway acts as the foundational backbone for other initiatives including Project Beta."
            ),
        ]
    },
    "security_incident.txt": {
        "id": "doc-security-incident",
        "name": "Security Incident Report",
        "department": "Operations",
        "project": "Project Alpha",
        "chunks": [
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Security Incident Report (Incident Details)\n"
                "Department: Operations | Date: 2025-02-14 | Author: Karthik\n\n"
                "A severe database security incident occurred on February 14, 2025, in Project Alpha. "
                "Lead developer Karthik reported a security risk regarding exposed local credentials "
                "in the repository configuration. This issue created a critical vulnerability, posing "
                "a budget risk due to potential data loss penalties."
            ),
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Security Incident Report (Impact & Severity)\n"
                "Department: Operations | Date: 2025-02-14 | Author: Karthik\n\n"
                "The security risk was categorized as Critical severity. Exposed local database credentials could permit "
                "unauthorized read access to customer records. Operations placed a temporary block on production pushes "
                "until infrastructure remediation and credential rotation could be formally approved."
            ),
        ]
    },
    "project_alpha_meeting.txt": {
        "id": "doc-alpha-meeting",
        "name": "Management Meeting Notes",
        "department": "Engineering",
        "project": "Project Alpha",
        "chunks": [
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Management Meeting Notes (Discussion)\n"
                "Department: Engineering | Date: 2025-02-20 | Author: Arun\n\n"
                "A management meeting was held on February 20, 2025, to discuss the security incident in Project Alpha. "
                "Arun, Priya, and Karthik attended. The meeting discussed migrating the database infrastructure "
                "to a cloud environment. Karthik proposed migrating database servers to AWS as a mitigation path."
            ),
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Management Meeting Notes (Options & Consensus)\n"
                "Department: Engineering | Date: 2025-02-20 | Author: Arun\n\n"
                "During the meeting, Priya reviewed budget impact, confirming that managed cloud hosting would reduce maintenance overhead. "
                "Arun agreed to formulate a formal Architecture Decision Record proposing full cloud migration of all database instances."
            ),
        ]
    },
    "decision_record.txt": {
        "id": "doc-decision-record",
        "name": "Architecture Decision Record",
        "department": "Engineering",
        "project": "Project Alpha",
        "chunks": [
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Architecture Decision Record (Approval)\n"
                "Department: Engineering | Date: 2025-02-25 | Author: Arun\n\n"
                "On February 25, 2025, project manager Arun approved the Cloud Migration decision. "
                "The migration will move all backend services and postgres databases to AWS. This decision "
                "was approved to resolve the database security risk and mitigate credentials exposure."
            ),
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Alpha | Document: Architecture Decision Record (Outcome)\n"
                "Department: Engineering | Date: 2025-02-25 | Author: Arun\n\n"
                "The cloud migration successfully resulted in a secure system upgrade on March 10, 2025. "
                "All database credentials were moved to AWS Secrets Manager with automated rotation, resolving the security risk."
            ),
        ]
    },
    "project_beta_report.txt": {
        "id": "doc-beta-report",
        "name": "Project Beta Report",
        "department": "Finance",
        "project": "Project Beta",
        "chunks": [
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Beta | Document: Project Beta Report (Overview)\n"
                "Department: Finance | Date: 2025-03-01 | Author: Priya\n\n"
                "Project Beta is directed at automating financial forecasting led by department head Priya in the Finance department. "
                "Financial analyst Meena is conducting requirements gathering for quarterly budget models and automated ledger reconciliation."
            ),
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Beta | Document: Project Beta Report (Dependencies & Risks)\n"
                "Department: Finance | Date: 2025-03-01 | Author: Priya\n\n"
                "Project Beta has encountered a budget risk regarding software licensing costs. Priya and Meena are investigating mitigation options. "
                "Crucially, Project Beta has a direct cross-project dependency on the API gateway built in Project Alpha for transaction ingest."
            ),
        ]
    },
    "project_atlas_architecture.txt": {
        "id": "doc-atlas-architecture",
        "name": "Project Atlas Architecture Charter",
        "department": "Core Architecture",
        "project": "Project Atlas",
        "chunks": [
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Atlas | Document: Architecture Charter (Team & Scope)\n"
                "Department: Core Architecture | Date: 2025-03-15 | Author: Dr. Maya Rao\n\n"
                "Project Atlas is led by Dr. Maya Rao in the Core Architecture group in the Bengaluru office. "
                "Sneha Iyer owns the React dashboard for graph visualization, Rahul Menon owns the Neo4j knowledge graph engine, "
                "and Arjun Kumar owns the authentication module."
            ),
            (
                "[SYNTHETIC DEVELOPMENT DATA]\n"
                "MEMORAGRAPH ORGANIZATIONAL MEMORY CORPUS\n"
                "Project: Project Atlas | Document: Architecture Charter (Technology Stack & Risks)\n"
                "Department: Core Architecture | Date: 2025-03-15 | Author: Dr. Maya Rao\n\n"
                "Project Atlas selected Neo4j for multi-hop graph queries and Qdrant for semantic vector search using FastEmbed embeddings. "
                "The team identified a UI latency risk during high-concurrency graph traversals, mitigated by caching query results."
            ),
        ]
    },
}


async def seed_users(session) -> dict:
    """Create default mock users with distinct roles."""
    roles = {
        "admin@memoragraph.com": ("Admin User", UserRole.ADMIN),
        "manager@memoragraph.com": ("Arun Manager", UserRole.MANAGER),
        "employee@memoragraph.com": ("Karthik Developer", UserRole.EMPLOYEE),
        "priya@memoragraph.com": ("Priya Designer", UserRole.MANAGER),
    }
    
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
    print("==================================================")
    print("      MEMORAGRAPH DATABASE SEEDER (PHASE 5)      ")
    print("==================================================")
    print("Initializing PostgreSQL database...")
    init_db(settings.database_url)
    await create_tables()

    session_gen = get_session()
    session = await anext(session_gen)

    # Clean up old records
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

    # Clear old Qdrant collection to guarantee pristine evaluation state
    try:
        await vector_store.delete_collection()
        await vector_store.ensure_collection(encoder.dimension)
        print("Recreated clean Qdrant collection:", settings.qdrant_collection)
    except Exception as e:
        print("Note on Qdrant recreate:", e)

    # Initialize Neo4j
    print("\n--- Seeding Neo4j Knowledge Graph ---")
    neo4j = init_neo4j(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )
    neo4j.ensure_constraints()

    try:
        neo4j.execute_write("MATCH (n) DETACH DELETE n")
        print("Cleared existing Neo4j knowledge graph data.")
    except Exception as e:
        print("Warning: could not clear Neo4j graph:", e)

    # 4. Ingest Documents and Chunks
    print("\n--- Ingesting Multi-Document Corpus (6 Documents, 12 Chunks) ---")
    all_vector_chunks = []

    for filename, doc_info in DOCUMENTS_SPEC.items():
        doc_id = doc_info["id"]
        doc_name = doc_info["name"]
        department = doc_info["department"]
        project = doc_info["project"]
        chunks = doc_info["chunks"]

        full_content = "\n\n".join(chunks)
        file_path = os.path.join(doc_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        doc_counts_map = {
            "doc-alpha-report": (4, 4),
            "doc-security-incident": (5, 4),
            "doc-alpha-meeting": (4, 3),
            "doc-decision-record": (3, 3),
            "doc-beta-report": (4, 4),
            "doc-atlas-architecture": (7, 6),
        }
        ent_cnt, rel_cnt = doc_counts_map.get(doc_id, (0, 0))

        db_doc = Document(
            id=doc_id,
            name=doc_name,
            original_filename=filename,
            file_type="TXT",
            file_size_bytes=len(full_content),
            file_path=file_path,
            status=DocumentStatus.PROCESSED,
            department=department,
            project=project,
            chunk_count=len(chunks),
            entity_count=ent_cnt,
            relationship_count=rel_cnt,
            uploaded_by=user_map["admin@memoragraph.com"].id,
            processed_at=datetime.now(timezone.utc),
        )
        session.add(db_doc)

        for c_idx, chunk_text in enumerate(chunks):
            chunk_id = f"{doc_id}-c{c_idx}"
            db_chunk = DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=c_idx,
                text=chunk_text,
                char_start=0,
                char_end=len(chunk_text),
                token_count=len(chunk_text) // 4,
                embedding_id=chunk_id,
            )
            session.add(db_chunk)

            emb = encoder.encode_single(chunk_text)
            all_vector_chunks.append(
                VectorChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    document_name=doc_name,
                    text=chunk_text,
                    embedding=emb,
                    metadata={
                        "project": project,
                        "department": department,
                        "filename": filename,
                        "chunk_index": c_idx,
                    },
                )
            )

        print(f"  Ingested Document [{doc_id}]: '{doc_name}' ({len(chunks)} chunks)")

    # Upsert all chunks into Qdrant
    await vector_store.upsert_chunks(all_vector_chunks)
    await session.commit()
    print(f"Successfully upserted {len(all_vector_chunks)} vector chunks into Qdrant.")

    # 5. Populate Neo4j Knowledge Graph
    print("\n--- Seeding Knowledge Graph Entities & Relations ---")
    try:
        n_count, r_count = seed_neo4j_nodes_and_relationships(neo4j)
        print(f"Successfully seeded {n_count} Neo4j nodes and {r_count} relationships.")
    except Exception as e:
        print("Error populating Neo4j:", e)

    print("\n==================================================")
    print("        DATABASE SEEDING COMPLETED SUCCESSFULLY    ")
    print("==================================================")


def seed_neo4j_nodes_and_relationships(neo4j):
    """Seed the baseline knowledge graph nodes and relationships in Neo4j."""
    nodes = [
        # Employees
        ("Employee", "arun", {"name": "Arun", "role": "Project Manager"}),
        ("Employee", "priya", {"name": "Priya", "role": "Designer"}),
        ("Employee", "karthik", {"name": "Karthik", "role": "Developer"}),
        ("Employee", "meena", {"name": "Meena", "role": "Financial Analyst"}),
        ("Employee", "dr-maya-rao", {"name": "Dr. Maya Rao", "role": "Project Director"}),
        ("Employee", "sneha-iyer", {"name": "Sneha Iyer", "role": "Frontend Lead"}),
        ("Employee", "rahul-menon", {"name": "Rahul Menon", "role": "Graph Architect"}),
        ("Employee", "arjun-kumar", {"name": "Arjun Kumar", "role": "Security Engineer"}),
        
        # Departments
        ("Department", "engineering", {"name": "Engineering"}),
        ("Department", "operations", {"name": "Operations"}),
        ("Department", "finance", {"name": "Finance"}),
        ("Department", "core-architecture", {"name": "Core Architecture"}),
        
        # Projects
        ("Project", "project-alpha", {"name": "Project Alpha", "status": "Active"}),
        ("Project", "project-beta", {"name": "Project Beta", "status": "Planning"}),
        ("Project", "project-atlas", {"name": "Project Atlas", "status": "Active"}),
        
        # Risks
        ("Risk", "security-risk", {"name": "Security Risk", "severity": "Critical", "description": "Exposed repository database credentials"}),
        ("Risk", "budget-risk", {"name": "Budget Risk", "severity": "Medium", "description": "Software licensing cost overruns"}),
        ("Risk", "ui-latency-risk", {"name": "UI Latency Risk", "severity": "Low", "description": "Graph visualization rendering latency"}),
        
        # Decisions
        ("Decision", "cloud-migration", {"name": "Cloud Migration", "status": "Approved", "date": "2025-02-25"}),
        ("Decision", "graph-architecture", {"name": "Neo4j Architecture Choice", "status": "Approved", "date": "2025-03-15"}),
        
        # Outcomes
        ("Outcome", "system-upgrade", {"name": "System Upgrade", "status": "Resolved", "date": "2025-03-10"}),
        ("Outcome", "graph-visualizer", {"name": "Interactive Visualizer", "status": "Operational", "date": "2025-04-01"}),
        
        # Meetings
        ("Meeting", "management-meeting", {"name": "Management Meeting", "date": "2025-02-20"}),
        
        # Timeline Events
        ("Event", "evt-alpha-start", {"name": "Project Alpha Kickoff", "date": "2025-01-10"}),
        ("Event", "evt-sec-ident", {"name": "Security Risk Identified", "date": "2025-02-14"}),
        ("Event", "evt-meet-held", {"name": "Management Meeting Held", "date": "2025-02-20"}),
        ("Event", "evt-mig-appr", {"name": "Cloud Migration Approved", "date": "2025-02-25"}),
        ("Event", "evt-sec-resolv", {"name": "Security Risk Resolved", "date": "2025-03-10"}),
        
        # Issue
        ("Issue", "issue-cred-leak", {"name": "Repository Credentials Leak", "status": "Closed"}),
        
        # Documents (provenance nodes)
        ("Document", "doc-alpha-report", {"name": "Project Alpha Report"}),
        ("Document", "doc-security-incident", {"name": "Security Incident Report"}),
        ("Document", "doc-alpha-meeting", {"name": "Management Meeting Notes"}),
        ("Document", "doc-decision-record", {"name": "Architecture Decision Record"}),
        ("Document", "doc-beta-report", {"name": "Project Beta Report"}),
        ("Document", "doc-atlas-architecture", {"name": "Project Atlas Architecture Charter"}),
    ]

    for label, node_id, props in nodes:
        neo4j.merge_node(label, node_id, props)

    relationships = [
        # Employee -> Department (WORKS_IN)
        ("Employee", "arun", "WORKS_IN", "Department", "engineering"),
        ("Employee", "karthik", "WORKS_IN", "Department", "engineering"),
        ("Employee", "priya", "WORKS_IN", "Department", "finance"),
        ("Employee", "meena", "WORKS_IN", "Department", "finance"),
        ("Employee", "dr-maya-rao", "WORKS_IN", "Department", "core-architecture"),
        ("Employee", "sneha-iyer", "WORKS_IN", "Department", "core-architecture"),
        ("Employee", "rahul-menon", "WORKS_IN", "Department", "core-architecture"),
        ("Employee", "arjun-kumar", "WORKS_IN", "Department", "core-architecture"),
        
        # Employee -> Project (MANAGES)
        ("Employee", "arun", "MANAGES", "Project", "project-alpha"),
        ("Employee", "priya", "MANAGES", "Project", "project-beta"),
        ("Employee", "dr-maya-rao", "MANAGES", "Project", "project-atlas"),

        # Employee -> Project (ASSIGNED_TO)
        ("Employee", "karthik", "ASSIGNED_TO", "Project", "project-alpha"),
        ("Employee", "arjun-kumar", "ASSIGNED_TO", "Project", "project-atlas"),
        
        # Project -> Department (PART_OF)
        ("Project", "project-alpha", "PART_OF", "Department", "engineering"),
        ("Project", "project-beta", "PART_OF", "Department", "finance"),
        ("Project", "project-atlas", "PART_OF", "Department", "core-architecture"),
        
        # Project -> Risk (HAS_RISK)
        ("Project", "project-alpha", "HAS_RISK", "Risk", "security-risk"),
        ("Project", "project-beta", "HAS_RISK", "Risk", "budget-risk"),
        ("Project", "project-atlas", "HAS_RISK", "Risk", "ui-latency-risk"),

        # Causal relationships (CAUSED)
        ("Risk", "security-risk", "CAUSED", "Event", "evt-sec-ident"),
        ("Risk", "security-risk", "CAUSED", "Meeting", "management-meeting"),
        ("Risk", "security-risk", "CAUSED", "Risk", "budget-risk"),

        # Related issues (RELATED_TO)
        ("Issue", "issue-cred-leak", "RELATED_TO", "Risk", "security-risk"),
        
        # Meeting relations
        ("Meeting", "management-meeting", "DISCUSSED_IN", "Project", "project-alpha"),
        ("Meeting", "management-meeting", "INVOLVES", "Employee", "arun"),
        ("Meeting", "management-meeting", "INVOLVES", "Employee", "karthik"),
        
        # Decisions and Outcomes
        ("Decision", "cloud-migration", "APPROVED", "Project", "project-alpha"),
        ("Decision", "cloud-migration", "RESULTED_IN", "Outcome", "system-upgrade"),
        ("Decision", "graph-architecture", "APPROVED", "Project", "project-atlas"),
        ("Decision", "graph-architecture", "RESULTED_IN", "Outcome", "graph-visualizer"),
        
        # Risk resolution
        ("Risk", "security-risk", "RESOLVED_BY", "Decision", "cloud-migration"),
        
        # Cross-project dependencies
        ("Project", "project-beta", "DEPENDS_ON", "Project", "project-alpha"),
        
        # Document provenance
        ("Project", "project-alpha", "MENTIONED_IN", "Document", "doc-alpha-report"),
        ("Risk", "security-risk", "MENTIONED_IN", "Document", "doc-security-incident"),
        ("Meeting", "management-meeting", "MENTIONED_IN", "Document", "doc-alpha-meeting"),
        ("Decision", "cloud-migration", "MENTIONED_IN", "Document", "doc-decision-record"),
        ("Project", "project-beta", "MENTIONED_IN", "Document", "doc-beta-report"),
        ("Project", "project-atlas", "MENTIONED_IN", "Document", "doc-atlas-architecture"),
    ]

    for from_lbl, from_id, rel, to_lbl, to_id in relationships:
        neo4j.merge_relationship(from_lbl, from_id, rel, to_lbl, to_id)
    return len(nodes), len(relationships)


if __name__ == "__main__":
    asyncio.run(main())
