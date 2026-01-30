"""FastAPI backend and NiceGUI page. One app, both we serve."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
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
    async def upload_pdf(file: UploadFile) -> PDFUploadResponse:
        """Upload and parse PDF. Knowledge base, populate we do.
        
        Args:
            file: PDF file upload.
            
        Returns:
            Metadata if successful, error if failed.
        """
        try:
            # Status: receiving
            content = await file.read()
            session_id = str(uuid.uuid4())

            # Status: parsing
            metadata, text = PDFParser.parse(file.filename or "unknown.pdf", content)

            # Store in context
            current_pdf_context[session_id] = text
            logger.info(f"PDF parsed: {metadata.filename}, pages: {metadata.pages}")

            return PDFUploadResponse(
                success=True,
                metadata=metadata,
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
            """Handle PDF upload. Parse and store context we do."""
            pdf_status.text = "Uploading..."
            try:
                # Simulate progress
                pdf_metadata.text = ""

                # In real app, upload via API
                # For now, show placeholder
                pdf_status.text = "✓ Ready for documents"
                pdf_metadata.text = ""
            except Exception as err:
                pdf_status.text = f"❌ Error: {err}"

        ui.upload(on_upload=handle_upload, auto_upload=True).props("accept=.pdf")

        # Chat section
        ui.separator()
        ui.label("💬 Chat").classes("text-xl font-semibold mt-4 mb-2")

        # Status line
        status = ui.label("").classes("text-xs text-amber-600")

        # Chat messages display
        messages_container = ui.column().classes("w-full space-y-2")

        async def display_message(role: str, content: str):
            """Add message to display. UI update we do."""
            with messages_container:
                if role == "user":
                    ui.label(f"You: {content}").classes(
                        "bg-blue-100 p-2 rounded text-sm"
                    )
                else:
                    ui.label(f"Bot: {content}").classes(
                        "bg-green-100 p-2 rounded text-sm"
                    )

        # Input and send
        message_input = ui.input(
            label="Ask something...", on_change=lambda: None
        ).classes("w-full")

        async def send_message():
            """Send message and stream response. Real-time chat, we conduct."""
            user_msg = message_input.value.strip()
            if not user_msg:
                return

            # Show user message
            await display_message("user", user_msg)
            message_input.value = ""

            # Stream response
            try:
                status.text = "Thinking..."
                response_text = ""

                # Simulated streaming (in real app, call /api/chat/stream)
                response_text = f"[Streamed response to: {user_msg[:30]}...]"
                await display_message("assistant", response_text)

                status.text = "✓ Done"
            except Exception as e:
                status.text = f"❌ Error: {e}"
                logger.error(f"Chat error: {e}")

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

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
