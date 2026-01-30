"""Integration tests for streaming and PDF flow. End-to-end, test we do."""

import asyncio
import os
import uuid
from pathlib import Path

import pytest
import pytest_check as check

# Note: These tests require a valid OPENAI_API_KEY in .env
# Run with: pytest tests/integration/ -v -s  ( -s shows progress; API calls can take 30-90s )

TESTS_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_PDF = TESTS_DATA_DIR / "linear-guest.pdf"

# Timeout for tests that call OpenAI (streaming / embeddings); avoid hanging
API_TIMEOUT_SECONDS = 90


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

    # Parse must succeed; do not hide failures with skip
    metadata, text = PDFParser.parse("test.pdf", pdf_content)
    check.equal(metadata.filename, "test.pdf")
    check.equal(metadata.pages, 1)
    check.equal(metadata.size_bytes, len(pdf_content))
    check.greater(metadata.text_length, 0)


@pytest.mark.integration
def test_agent_streaming(monkeypatch):
    """Agent streaming, verify chunks we get.

    Test that real streaming from agent works.
    Multiple chunks, expect we do.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or not api_key.startswith("sk-"):
        pytest.skip("Real OpenAI key required for integration test")

    print("\ntest_agent_streaming: calling OpenAI (may take 30-90s)...", flush=True)

    from app.agent import get_manager

    manager = get_manager()

    async def test_stream():
        chunks = []
        async for chunk in manager.stream_response(
            "What is 2+2?", session_id="test-session"
        ):
            if chunk:
                chunks.append(chunk)

        # Verify multiple streamed chunks (not a single blob)
        num_chunks = len(chunks)
        check.greater(
            num_chunks, 1,
            f"Expected multiple streamed chunks, not a single blob; got {num_chunks} chunk(s)",
        )
        full_response = "".join(chunks)
        check.greater(len(full_response), 0)

    try:
        asyncio.run(
            asyncio.wait_for(test_stream(), timeout=API_TIMEOUT_SECONDS)
        )
        print("test_agent_streaming: done.", flush=True)
    except asyncio.TimeoutError:
        pytest.fail(
            f"test_agent_streaming timed out after {API_TIMEOUT_SECONDS}s. "
            "Check network and OpenAI API."
        )
    # Do not catch other exceptions: let test fail loudly


@pytest.mark.integration
def test_upload_parse_query_answer_references_pdf():
    """Upload → parse → query → answer referencing the PDF. Full flow, verify we do.

    Real sample PDF from tests/data; add to knowledge; ask about document; assert
    answer references the PDF content (not a refusal or generic reply).
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or not api_key.startswith("sk-"):
        pytest.skip("Real OpenAI key required for integration test")

    check.is_true(SAMPLE_PDF.exists(), f"Sample PDF missing: {SAMPLE_PDF}")

    print(
        "\ntest_upload_parse_query_answer_references_pdf: parse + embed + query "
        "(may take 60-90s)...",
        flush=True,
    )

    from app.agent import get_manager
    from app.pdf_parser import PDFParser

    async def run_flow():
        # Parse real sample PDF
        content = SAMPLE_PDF.read_bytes()
        metadata, pdf_text = PDFParser.parse(SAMPLE_PDF.name, content)
        check.greater(len(pdf_text), 0)

        # Add PDF to agent knowledge (same flow as upload endpoint)
        session_id = f"integration-pdf-qa-{uuid.uuid4().hex[:8]}"
        manager = get_manager()
        await manager.add_pdf_to_knowledge(
            session_id=session_id,
            pdf_text=pdf_text,
            filename=metadata.filename,
        )

        # Query about the document (answer must reference PDF content)
        query = "What is this document about? Summarize the main topic or purpose in one or two sentences."
        chunks = []
        async for chunk in manager.stream_response(query, session_id=session_id):
            if chunk:
                chunks.append(chunk)
        full_response = "".join(chunks).strip()

        # Assert we got a substantive answer that references the document
        check.greater(len(full_response), 50, "Response too short; agent may not have used PDF.")
        refusal_phrases = (
            "don't have access",
            "cannot read",
            "cannot access",
            "no document",
            "no PDF",
            "not provided",
            "I don't have",
        )
        response_lower = full_response.lower()
        for phrase in refusal_phrases:
            check.is_false(
                phrase in response_lower,
                f"Answer should reference PDF; got refusal-like: {full_response[:200]}...",
            )

    try:
        asyncio.run(
            asyncio.wait_for(run_flow(), timeout=API_TIMEOUT_SECONDS)
        )
        print("test_upload_parse_query_answer_references_pdf: done.", flush=True)
    except asyncio.TimeoutError:
        pytest.fail(
            f"test_upload_parse_query_answer_references_pdf timed out after "
            f"{API_TIMEOUT_SECONDS}s. Check network and OpenAI API."
        )


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
