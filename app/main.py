"""FastAPI backend and NiceGUI page. One app, both we serve."""

import sys
import os
from pathlib import Path

# Add parent directory to path so app module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import uuid
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from nicegui import ui

from app.config import get_settings
from app.models import ChatRequest, PDFUploadResponse, PDFMetadata
from app.agent import get_manager
from app.pdf_parser import PDFParser

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Global state for current PDF context
current_pdf_context: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup and shutdown, run we do."""
    logger.info("App starting, initialize we do.")
    yield
    logger.info("App shutting down, cleanup we do.")


def setup_routes(app: FastAPI) -> None:
    """Register NiceGUI page and FastAPI routes. Obvious and minimal, we keep."""

    @app.get("/health")
    def health() -> dict[str, str]:
        """Health check. Ok we are."""
        return {"status": "ok"}

    @app.post("/api/chat/stream")
    async def stream_chat(request: ChatRequest):
        """Stream agent response token by token. Real-time we deliver.
        
        Args:
            request: ChatRequest with message and optional session_id.
            
        Returns:
            StreamingResponse with chunks.
        """
        session_id = request.session_id or str(uuid.uuid4())
        manager = get_manager()
        context = current_pdf_context.get(session_id, "")

        async def generate():
            """Yield response chunks. Token by token, stream we do."""
            try:
                # Status: thinking
                yield "data: {'status': 'Thinking...'}\n\n"

                # Stream response
                async for chunk in manager.stream_response(
                    request.message, session_id=session_id, context=context
                ):
                    if chunk:
                        # Escape for SSE
                        chunk_sse = chunk.replace("\n", "\\n")
                        yield f"data: {{'chunk': '{chunk_sse}'}}\n\n"

                # Status: done
                yield "data: {'status': 'Done'}\n\n"
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {{'error': '{str(e)}'}}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/api/pdf/upload")
    async def upload_pdf(
        file: UploadFile,
        session_id: str | None = Form(None),
    ) -> PDFUploadResponse:
        """Upload and parse PDF. Under given session store we do, so chat may use it.
        
        Args:
            file: PDF file upload.
            session_id: Optional. If provided, PDF context stored under this session; else new one we create.
            
        Returns:
            Metadata and session_id if successful, error if failed.
        """
        try:
            content = await file.read()
            sid = session_id or str(uuid.uuid4())

            metadata, text = PDFParser.parse(file.filename or "unknown.pdf", content)

            current_pdf_context[sid] = text
            logger.info(f"PDF parsed: {metadata.filename}, pages: {metadata.pages}, session_id: {sid}")

            return PDFUploadResponse(
                success=True,
                metadata=metadata,
                session_id=sid,
            )
        except ValueError as e:
            logger.error(f"PDF upload error: {e}")
            return PDFUploadResponse(
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/session/{session_id}")
    def get_session(session_id: str) -> dict:
        """Get chat history for session. Messages retrieve we do.
        
        Args:
            session_id: Session identifier.
            
        Returns:
            Dictionary with messages.
        """
        manager = get_manager()
        messages = manager.get_session(session_id)
        return {"session_id": session_id, "messages": messages}

    @ui.page("/")
    def index() -> None:
        """UI page. Chat and upload, facilitate we do."""
        ui.label("📄 PDF QA Chatbot").classes("text-3xl font-bold mb-4")
        ui.label("Powered by Agno + FastAPI + NiceGUI").classes(
            "text-gray-600 mb-6"
        )

        # Session ID (hidden)
        session_id_input = ui.input(
            label="", value=str(uuid.uuid4())
        ).classes("hidden")

        # PDF Upload section
        ui.label("📋 Upload PDF").classes("text-xl font-semibold mt-4 mb-2")
        pdf_status = ui.label("").classes("text-sm text-gray-500")
        pdf_metadata = ui.label("").classes("text-sm text-gray-700")

        async def handle_upload(e):
            """Handle PDF upload. To API send we do; under current session store we must."""
            pdf_status.text = "Uploading..."
            pdf_metadata.text = ""
            try:
                # NiceGUI 3.x: UploadEventArguments has .file (FileUpload), not .content
                file_upload = getattr(e, "file", None)
                if not file_upload:
                    pdf_status.text = "❌ No file in event"
                    return
                name = getattr(file_upload, "name", None) or "document.pdf"
                content = await file_upload.read()
                if not content:
                    pdf_status.text = "❌ No file content"
                    return
                sid = session_id_input.value or str(uuid.uuid4())
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "http://localhost:8000/api/pdf/upload",
                        files={"file": (name, content, "application/pdf")},
                        data={"session_id": sid},
                        timeout=30.0,
                    )
                result = resp.json()
                if result.get("success"):
                    pdf_status.text = "✓ PDF loaded — ask questions about it below."
                    meta = result.get("metadata") or {}
                    pdf_metadata.text = f"{meta.get('filename', name)} — {meta.get('pages', 0)} pages, {meta.get('text_length', 0)} chars"
                    if result.get("session_id") and not session_id_input.value:
                        session_id_input.value = result["session_id"]
                else:
                    pdf_status.text = f"❌ {result.get('error', 'Upload failed')}"
            except Exception as err:
                pdf_status.text = f"❌ Error: {err}"
                logger.exception("Upload failed")

        ui.upload(on_upload=handle_upload, auto_upload=True).props("accept=.pdf")

        # Chat section
        ui.separator()
        ui.label("💬 Chat").classes("text-xl font-semibold mt-4 mb-2")

        # Status line
        status = ui.label("").classes("text-xs text-amber-600")

        # Chat messages display
        messages_container = ui.column().classes("w-full space-y-3 max-h-96 overflow-y-auto")

        async def display_message(role: str, content: str):
            """Add message to display. UI update we do."""
            with messages_container:
                if role == "user":
                    ui.label(content).classes(
                        "bg-blue-100 p-3 rounded text-sm max-w-full ml-auto mr-0"
                    )
                else:
                    ui.label(content).classes(
                        "bg-green-100 p-3 rounded text-sm max-w-full"
                    )

        # Input and send
        async def send_message():
            """Send message and stream response. Real-time chat, we conduct."""
            user_msg = message_input.value.strip()
            if not user_msg:
                return

            # Show user message
            await display_message("user", user_msg)
            message_input.value = ""

            # Create a container for the response that updates as we stream
            response_text = ""
            response_label = None
            
            # Stream response
            try:
                status.text = "Thinking..."
                
                # Call the streaming endpoint
                async with httpx.AsyncClient() as client:
                    # Get the session ID from the hidden input
                    session_id = session_id_input.value
                    
                    # POST to /api/chat/stream
                    async with client.stream(
                        "POST",
                        "http://localhost:8000/api/chat/stream",
                        json={"message": user_msg, "session_id": session_id},
                        timeout=60.0,
                    ) as response:
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    # Parse SSE format - use json instead of eval for safety
                                    import json as json_module
                                    data_str = line[6:]  # Remove "data: " prefix
                                    
                                    # Try to parse as JSON dict
                                    # Handle both {'key': 'value'} and {"key": "value"}
                                    try:
                                        data = json_module.loads(data_str)
                                    except:
                                        # Try eval as fallback for single-quoted dicts
                                        data = eval(data_str)
                                    
                                    if "chunk" in data:
                                        chunk = data["chunk"]
                                        response_text += chunk
                                        
                                        # Create response label on first chunk
                                        if response_label is None:
                                            with messages_container:
                                                response_label = ui.label(response_text).classes(
                                                    "bg-green-100 p-3 rounded text-sm max-w-full mr-8"
                                                )
                                        else:
                                            # Update existing label
                                            response_label.text = response_text
                                    elif "status" in data:
                                        status.text = data["status"]
                                    elif "error" in data:
                                        status.text = f"❌ Error: {data['error']}"
                                        logger.error(f"Stream error: {data['error']}")
                                except Exception as e:
                                    logger.debug(f"Parse error: {e}")
                                    continue
                
                status.text = "✓ Done"
            except Exception as e:
                status.text = f"❌ Error: {e}"
                logger.error(f"Chat error: {e}")

        message_input = ui.input(
            label="Ask something...", 
            on_change=lambda: None
        ).classes("w-full")
        
        # Handle Enter key to send message
        message_input.on("keydown.enter", send_message)

        ui.button("Send", on_click=send_message).classes("mt-2")

    ui.run_with(
        app,
        mount_path="/",
        storage_secret=get_settings().openai_api_key or "dev-secret-change-in-production",
    )


def create_app() -> FastAPI:
    """Build the FastAPI app. Lifespan and routes, we attach."""
    app = FastAPI(title="pdf-qa-chat", lifespan=lifespan)
    setup_routes(app)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
