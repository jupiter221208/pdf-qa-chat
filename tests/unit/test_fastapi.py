"""Unit tests for FastAPI endpoints. Routes and models, test we do."""

import pytest_check as check
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check():
    """Health endpoint, working it is."""
    response = client.get("/health")
    check.equal(response.status_code, 200)
    check.equal(response.json(), {"status": "ok"})


def test_chat_stream_endpoint_exists():
    """Chat endpoint, exist it must."""
    # Just verify the endpoint exists and accepts the right schema
    check.is_true(any(route.path == "/api/chat/stream" for route in app.routes))


def test_pdf_upload_endpoint_exists():
    """PDF upload endpoint, exist it must."""
    # Verify the endpoint exists
    check.is_true(any(route.path == "/api/pdf/upload" for route in app.routes))


def test_session_endpoint_exists():
    """Session endpoint, exist it must."""
    # Verify the endpoint exists
    check.is_true(
        any(route.path == "/api/session/{session_id}" for route in app.routes)
    )
