"""
MemoraGraph – FastAPI Application Entry Point

Intent-Routed Organizational Memory Retrieval System.
"""

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# Import routers
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.graph import router as graph_router
from app.api.query import router as query_router
from app.api.analytics import router as analytics_router
from app.api.retrieval import router as retrieval_router

# Import initializers
from app.models.database import init_db, create_tables, close_db
from app.embeddings.encoder import init_encoder
from app.embeddings.vector_store import init_vector_store
from app.graph.neo4j_client import init_neo4j
from app.llm.provider import init_llm_provider
from app.retrieval.intent_classifier import get_intent_classifier

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("memoragraph")


async def auto_seed_default_users():
    """Auto seed default users if database is empty."""
    import uuid
    from app.models.database import get_session
    from app.models.user import User, UserRole
    from app.security.auth import hash_password
    from sqlalchemy import select, func
    
    try:
        session_gen = get_session()
        async for session in session_gen:
            result = await session.execute(select(func.count(User.id)))
            count = result.scalar()
            if count == 0:
                logger.info("Database empty. Auto-seeding default system users...")
                default_users = [
                    User(id=str(uuid.uuid4()), email="admin@memoragraph.com", hashed_password=hash_password("memoragraph"), name="Admin User", role=UserRole.ADMIN, is_active=True),
                    User(id=str(uuid.uuid4()), email="manager@memoragraph.com", hashed_password=hash_password("memoragraph"), name="Arun Manager", role=UserRole.MANAGER, is_active=True),
                    User(id=str(uuid.uuid4()), email="employee@memoragraph.com", hashed_password=hash_password("memoragraph"), name="Karthik Developer", role=UserRole.EMPLOYEE, is_active=True),
                ]
                session.add_all(default_users)
                await session.commit()
                logger.info("Auto-seeded default users successfully.")
            break
    except Exception as e:
        logger.warning("Could not auto-seed default users: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info(
        "Starting %s v%s", settings.app_name, settings.app_version
    )
    
    # 1. Initialize databases
    init_db(settings.database_url)
    await create_tables()
    await auto_seed_default_users()

    init_vector_store(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        collection=settings.qdrant_collection,
    )

    init_neo4j(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )

    # 2. Initialize LLM provider
    init_llm_provider(
        provider=settings.llm_provider,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )

    # 3. Register sentence embeddings model (lazy loads on first request)
    init_encoder(model_name=settings.embedding_model)

    yield
    
    # Shutdown / Cleanup
    logger.info("Shutting down %s", settings.app_name)
    await close_db()


app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Organizational Memory Retrieval using Intent-Routed Graph RAG",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS – allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5000",
        "https://memoragraph.vercel.app",
        "*",  # support broad dev environments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(graph_router)
app.include_router(query_router)
app.include_router(analytics_router)
app.include_router(retrieval_router)


# Serve frontend static assets in production
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

frontend_dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(frontend_dist_path):
    logger.info("Mounting frontend static files from: %s", frontend_dist_path)
    
    # Catch-all exception handler to redirect client-side route requests (like /login) to index.html
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        if request.url.path.startswith("/api"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        index_file = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    app.mount("/", StaticFiles(directory=frontend_dist_path, html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": settings.app_name,
            "description": "Intent-Routed Organizational Memory",
            "docs": "/api/docs",
        }

