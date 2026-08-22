"""
MemoraGraph – Health Check Endpoint Unit Tests
"""

import pytest
from httpx import AsyncClient, ASGITransport
import os
import sys

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify that the health check endpoint returns 200 and formatted keys."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "version" in data
    assert "services" in data
    assert "backend" in data["services"]
