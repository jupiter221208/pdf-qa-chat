"""FastAPI backend and NiceGUI page. One app, both we serve."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from nicegui import ui

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup and shutdown, run we do."""
    yield
    # Teardown if needed later, here we add.


def setup_routes(app: FastAPI) -> None:
    """Register NiceGUI page and FastAPI routes. Obvious and minimal, we keep."""

    @app.get("/health")
    def health() -> dict[str, str]:
        """Health check. Ok we are."""
        return {"status": "ok"}

    @ui.page("/")
    def index() -> None:
        """Hello-world page. Greet the user, we do."""
        ui.label("Hello, World!").classes("text-2xl font-bold")
        ui.label("FastAPI + NiceGUI + Agno — hello-world.").classes("text-lg text-gray-600")

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

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
