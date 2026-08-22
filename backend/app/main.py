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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info(
        "Starting %s v%s", settings.app_name, settings.app_version
    )
    
    # 1. Initialize databases
    init_db(settings.database_url)
    await create_tables()

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

    # 3. Initialize sentence embeddings model
    init_encoder(model_name=settings.embedding_model)

    # 4. Initialize intent classifier prototypes (pre-computes embeddings)
    # Run in executor to avoid blocking startup event loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, get_intent_classifier)

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

