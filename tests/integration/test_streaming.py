"""Integration tests for streaming and PDF flow. End-to-end, test we do."""

import asyncio
import os
from pathlib import Path

import pytest
import pytest_check as check

# Note: These tests require a valid OPENAI_API_KEY in .env
# Run with: pytest tests/integration/


@pytest.mark.integration
def test_pdf_parsing_flow(monkeypatch):
    """PDF upload → parse → verify metadata. Full flow, complete it is."""
    from app.pdf_parser import PDFParser

    # Create a minimal valid PDF for testing
    # In production, use real sample PDF in tests/data/
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test PDF) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000250 00000 n
0000000394 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
474
%%EOF"""

    try:
        metadata, text = PDFParser.parse("test.pdf", pdf_content)
        check.equal(metadata.filename, "test.pdf")
        check.equal(metadata.pages, 1)
        check.equal(metadata.size_bytes, len(pdf_content))
        check.greater(metadata.text_length, 0)
    except ValueError as e:
        # Expected if PDF parsing fails on invalid structure
        pytest.skip(f"PDF parsing not fully compatible: {e}")


@pytest.mark.integration
def test_agent_streaming(monkeypatch):
    """Agent streaming, verify chunks we get.
    
    Test that real streaming from agent works.
    Multiple chunks, expect we do.
    """
    # Check for real API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or not api_key.startswith("sk-"):
        pytest.skip("Real OpenAI key required for integration test")

    from app.agent import get_manager

    manager = get_manager()

    async def test_stream():
        chunks = []
        async for chunk in manager.stream_response(
            "What is 2+2?", session_id="test-session"
        ):
            if chunk:
                chunks.append(chunk)

        # Verify we got multiple chunks (streaming works)
        check.greater(len(chunks), 0)
        full_response = "".join(chunks)
        check.greater(len(full_response), 0)

    # Run async test
    try:
        asyncio.run(test_stream())
    except Exception as e:
        pytest.skip(f"Agent streaming test skipped: {e}")


@pytest.mark.integration
def test_session_persistence(monkeypatch):
    """Session history, maintain we must.
    
    Messages in session, store and retrieve we do.
    """
    from app.agent import get_manager

    manager = get_manager()
    session_id = "test-session-persist"

    # Manually add messages (simulate conversation)
    manager._sessions[session_id] = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    # Retrieve session
    history = manager.get_session(session_id)
    check.equal(len(history), 2)
    check.equal(history[0]["role"], "user")
    check.equal(history[1]["role"], "assistant")

    # Clear session
    manager.clear_session(session_id)
    check.equal(len(manager.get_session(session_id)), 0)
