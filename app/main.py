"""FastAPI backend and NiceGUI page. One app, both we serve."""

import sys
import os
from pathlib import Path

# Add parent directory to path so app module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
import uuid
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from nicegui import ui

from app.config import get_settings
from app.models import ChatRequest, PDFMetadata, PDFUploadResponse, SessionHistoryResponse
from app.agent import get_manager
from app.pdf_parser import PDFParser

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Global state for current PDF context (deprecated; now using Knowledge/vector DB)
# Kept for backward compatibility but not used
current_pdf_context: dict[str, str] = {}

# UI branding: header and browser tab title
APP_TITLE = "PDF QA Chatbot"
APP_SUBTITLE = "Upload a PDF, then ask questions. Powered by Agno · FastAPI · NiceGUI"


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
        # No manual context; Agno Knowledge handles RAG automatically

        async def generate():
            """Yield response chunks. Token by token, stream we do."""
            try:
                # Status: Received → Searching → Generating → Done
                yield f"data: {json.dumps({'status': 'Received'})}\n\n"
                yield f"data: {json.dumps({'status': 'Searching...'})}\n\n"

                first_chunk = True
                async for chunk in manager.stream_response(
                    request.message, session_id=session_id
                ):
                    if chunk:
                        if first_chunk:
                            yield f"data: {json.dumps({'status': 'Generating...'})}\n\n"
                            first_chunk = False
                        # Valid JSON for SSE so client can parse reliably
                        payload = json.dumps({"chunk": chunk})
                        yield f"data: {payload}\n\n"

                # Status: done
                yield f"data: {json.dumps({'status': 'Done'})}\n\n"
            except Exception as e:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

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

            # Add PDF to Knowledge base (vector DB) instead of raw text context
            manager = get_manager()
            await manager.add_pdf_to_knowledge(
                session_id=sid,
                pdf_text=text,
                filename=metadata.filename,
            )
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

    @app.get("/api/session/{session_id}", response_model=SessionHistoryResponse)
    def get_session(session_id: str) -> SessionHistoryResponse:
        """Get chat history for session. Messages retrieve we do.

        Args:
            session_id: Session identifier.

        Returns:
            Session id and list of messages.
        """
        manager = get_manager()
        messages = manager.get_session(session_id)
        return SessionHistoryResponse(session_id=session_id, messages=messages)

    @ui.page("/")
    def index() -> None:
        """UI page. Chat and upload, facilitate we do."""
        # Tab title: override NiceGUI default so browser tab shows APP_TITLE
        ui.page_title(APP_TITLE)
        # Professional layout: centered container, subtle background
        ui.add_head_html(f'<title>{APP_TITLE}</title>')
        ui.add_head_html(
            """
            <style>
                .pdf-qa-page {
                    max-width: 720px; margin: 0 auto; padding: 0.75rem;
                    height: 100vh; max-height: calc(100vh - 2rem); overflow: hidden;
                    display: flex; flex-direction: column; box-sizing: border-box;
                }
                .pdf-qa-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.75rem; background: #fff; box-sizing: border-box; }
                .pdf-qa-chat-card { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
                .pdf-qa-scroll-hide {
                    scrollbar-width: none; -ms-overflow-style: none;
                }
                .pdf-qa-scroll-hide::-webkit-scrollbar { display: none; }
                .pdf-qa-chat-bubble-user { background: #2563eb; color: #fff; border-radius: 12px 12px 4px 12px; padding: 0.5rem 0.75rem; max-width: 85%; margin-left: auto; white-space: normal; word-break: break-word; }
                .pdf-qa-chat-bubble-assistant { background: #f1f5f9; color: #1e293b; border-radius: 12px 12px 12px 4px; padding: 0.5rem 0.75rem; max-width: 85%; border: 1px solid #e2e8f0; white-space: normal; word-break: break-word; }
                .pdf-qa-chat-bubble-assistant h1, .pdf-qa-chat-bubble-assistant h2, .pdf-qa-chat-bubble-assistant h3,
                .pdf-qa-chat-bubble-assistant h4, .pdf-qa-chat-bubble-assistant h5, .pdf-qa-chat-bubble-assistant h6 {
                    margin: 0.35em 0 0.2em 0; font-size: inherit; line-height: 1.3;
                }
                .pdf-qa-chat-bubble-assistant p, .pdf-qa-chat-bubble-assistant ul, .pdf-qa-chat-bubble-assistant ol {
                    margin: 0.2em 0; padding-left: 1.2em;
                }
                .pdf-qa-chat-bubble-assistant li { margin: 0.1em 0; }
                .pdf-qa-chat-bubble-assistant li > p { margin: 0.25em 0 0.1em 0; }
                .pdf-qa-chat-bubble-assistant li > ul, .pdf-qa-chat-bubble-assistant li > ol {
                    margin: 0.1em 0 0.25em 0; padding-left: 1.2em;
                }
                .pdf-qa-status { font-size: 0.75rem; color: #64748b; padding: 0.2rem 0.4rem; background: #f8fafc; border-radius: 4px; }
                .pdf-qa-status-done { color: #059669; }
                .pdf-qa-status-error { color: #dc2626; }
                .flex-shrink-0 { flex-shrink: 0; }
            </style>
            """
        )
        main_container = ui.column().classes("pdf-qa-page w-full").style(
            "background: #f8fafc;"
        )
        with main_container:
            # Header (fixed height)
            with ui.column().classes("w-full mb-2 flex-shrink-0"):
                ui.label("PDF QA Chatbot").classes(
                    "text-2xl font-semibold text-slate-800"
                )
                ui.label("Upload a PDF, then ask questions. Powered by Agno · FastAPI · NiceGUI").classes(
                    "text-sm text-slate-500"
                )

            # Session ID (hidden)
            session_id_input = ui.input(
                label="", value=str(uuid.uuid4())
            ).classes("hidden")

            # PDF Upload card (fixed height)
            with ui.column().classes("pdf-qa-card w-full mb-2 flex-shrink-0"):
                ui.label("Document").classes(
                    "text-sm font-medium text-slate-700 mb-1"
                )
                pdf_status = ui.label("").classes("text-sm text-slate-500")
                pdf_metadata = ui.label("").classes("text-xs text-slate-400")

                async def handle_upload(e):
                    """Handle PDF upload. To API send we do; under current session store we must."""
                    pdf_status.text = "Uploading…"
                    pdf_metadata.text = ""
                    try:
                        file_upload = getattr(e, "file", None)
                        if not file_upload:
                            pdf_status.text = "No file received."
                            return
                        name = getattr(file_upload, "name", None) or "document.pdf"
                        content = await file_upload.read()
                        if not content:
                            pdf_status.text = "File is empty."
                            return
                        sid = session_id_input.value or str(uuid.uuid4())
                        port = int(os.getenv("PORT", get_settings().api_port))
                        upload_url = f"http://127.0.0.1:{port}/api/pdf/upload"
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(
                                upload_url,
                                files={"file": (name, content, "application/pdf")},
                                data={"session_id": sid},
                                timeout=30.0,
                            )
                        result = resp.json()
                        if result.get("success"):
                            pdf_status.text = "Document loaded. You can ask questions below."
                            meta = result.get("metadata") or {}
                            pdf_metadata.text = (
                                f"{meta.get('filename', name)} · "
                                f"{meta.get('pages', 0)} pages · "
                                f"{meta.get('text_length', 0):,} characters"
                            )
                            if result.get("session_id") and not session_id_input.value:
                                session_id_input.value = result["session_id"]
                        else:
                            pdf_status.text = result.get("error", "Upload failed")
                    except Exception as err:
                        pdf_status.text = f"Error: {err}"
                        logger.exception("Upload failed")

                ui.upload(on_upload=handle_upload, auto_upload=True).props(
                    "accept=.pdf flat bordered"
                ).classes("w-full")

            # Chat card (takes remaining space, no page scrollbar)
            with ui.column().classes("pdf-qa-card pdf-qa-chat-card w-full"):
                ui.label("Chat").classes(
                    "text-sm font-medium text-slate-700 mb-1 flex-shrink-0"
                )
                status = ui.label("").classes("pdf-qa-status mb-1 flex-shrink-0")

                messages_container = ui.column().classes(
                    "w-full space-y-2 overflow-y-auto pdf-qa-scroll-hide"
                ).style("flex: 1; min-height: 0;")

                def scroll_to_bottom():
                    """Scroll chat container to bottom. Latest message, show we must."""
                    ui.run_javascript("""
                        setTimeout(() => {
                            const containers = document.querySelectorAll('.overflow-y-auto');
                            containers.forEach(container => {
                                if (container.scrollHeight > container.clientHeight) {
                                    container.scrollTop = container.scrollHeight;
                                }
                            });
                        }, 10);
                    """)

                async def display_message(role: str, content: str):
                    """Add message to display. UI update we do. Assistant: markdown we render."""
                    with messages_container:
                        bubble_class = (
                            "pdf-qa-chat-bubble-user" if role == "user" else "pdf-qa-chat-bubble-assistant"
                        )
                        if role == "user":
                            ui.label(content).classes(bubble_class)
                        else:
                            ui.markdown(content or "…").classes(bubble_class)

                # Input row
                with ui.row().classes("w-full items-end gap-2 mt-1"):
                    message_input = ui.input(
                        label="Message",
                        placeholder="Ask about your document…",
                        on_change=lambda: None,
                    ).classes("flex-grow")
                    message_input.props("outlined dense")

                    async def send_message():
                        """Send message and stream response. Agent we call directly, so no self-request deadlock."""
                        user_msg = message_input.value.strip()
                        if not user_msg:
                            return

                        await display_message("user", user_msg)
                        message_input.value = ""
                        scroll_to_bottom()

                        response_text = ""
                        with messages_container:
                            response_md = ui.markdown("…").classes(
                                "pdf-qa-chat-bubble-assistant"
                            )
                        scroll_to_bottom()

                        try:
                            status.classes(remove="pdf-qa-status-done pdf-qa-status-error")
                            status.text = "Received"
                            session_id = session_id_input.value or str(uuid.uuid4())
                            manager = get_manager()
                            status.text = "Searching…"
                            await asyncio.sleep(0)

                            first_chunk = True
                            async for chunk in manager.stream_response(
                                user_msg, session_id=session_id
                            ):
                                if chunk:
                                    if first_chunk:
                                        status.text = "Generating…"
                                        first_chunk = False
                                    response_text += chunk
                                    response_md.content = response_text if response_text else "…"
                                    scroll_to_bottom()
                                    await asyncio.sleep(0)

                            status.text = "Done"
                            status.classes(add="pdf-qa-status-done")
                            scroll_to_bottom()
                        except Exception as e:
                            status.text = f"Error: {e}"
                            status.classes(add="pdf-qa-status-error")
                            response_md.content = str(e) if not response_text else response_text
                            logger.exception("Chat error")

                    message_input.on("keydown.enter", send_message)
                    ui.button("Send", on_click=send_message).props(
                        "flat unelevated color=primary"
                    )

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

    port = int(os.getenv("PORT", get_settings().api_port))
    uvicorn.run(app, host="0.0.0.0", port=port)
