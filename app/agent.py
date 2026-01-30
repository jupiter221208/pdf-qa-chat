"""Agno agent wiring. OpenAI model we use; from config, key we take."""

import asyncio
import inspect
import logging
import tempfile
from pathlib import Path
from typing import AsyncGenerator
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.models.openai import OpenAIChat
from agno.vectordb.chroma import ChromaDb, SearchType

from app.config import get_settings

logger = logging.getLogger(__name__)

# Sqlite for Agno session/chat history; one file per app
_db_path = Path(__file__).resolve().parent.parent / "data" / "agent.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)
_agno_db = SqliteDb(db_file=str(_db_path))

# ChromaDB for vector search; one knowledge base per session
_chroma_path = Path(__file__).resolve().parent.parent / "data" / "chromadb"
_chroma_path.mkdir(parents=True, exist_ok=True)


class AgentManager:
    """Manage agent instances and sessions. Create and reuse agents, we do."""

    def __init__(self):
        """Initialize manager. Agent cache, maintain we shall."""
        self._agent: Agent | None = None
        self._agents_by_session: dict[str, Agent] = {}
        self._sessions: dict[str, list[dict]] = {}
        self._knowledge_by_session: dict[str, Knowledge] = {}

    def get_knowledge(self, session_id: str) -> Knowledge:
        """Get or create Knowledge base for session. Vector search, enable we do.
        
        Args:
            session_id: Session identifier.
            
        Returns:
            Knowledge instance with ChromaDB for this session.
        """
        if session_id not in self._knowledge_by_session:
            settings = get_settings()
            knowledge = Knowledge(
                name=f"PDF Knowledge - {session_id}",
                vector_db=ChromaDb(
                    collection=f"pdf_{session_id}",
                    path=str(_chroma_path),
                    persistent_client=True,
                    search_type=SearchType.hybrid,
                    embedder=OpenAIEmbedder(
                        id="text-embedding-3-small",
                        api_key=settings.openai_api_key,
                    ),
                ),
            )
            self._knowledge_by_session[session_id] = knowledge
        return self._knowledge_by_session[session_id]

    def get_agent(self, session_id: str | None = None) -> Agent:
        """Get or create agent. With knowledge for session, configure we do.
        
        Args:
            session_id: Optional session ID to attach knowledge base.
            
        Returns:
            Agent configured with OpenAI and optional knowledge.
            
        Raises:
            ValueError: If API key missing, raise we do.
        """
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set. In .env put it, you must.")
        
        sid = session_id or "default"
        
        # Cache agent per session if knowledge exists
        if sid in self._agents_by_session:
            return self._agents_by_session[sid]
        
        model = OpenAIChat(
            id=settings.openai_model_id,
            api_key=settings.openai_api_key,
        )
        
        if sid in self._knowledge_by_session:
            # Session has knowledge: create agent with that knowledge
            knowledge = self._knowledge_by_session[sid]
            agent = Agent(
                model=model,
                db=_agno_db,
                knowledge=knowledge,
                add_history_to_context=True,
                add_knowledge_to_context=True,
                num_history_runs=settings.num_history_runs,
                num_history_messages=settings.num_history_messages,
            )
            self._agents_by_session[sid] = agent
            return agent
        else:
            # No knowledge: use singleton agent without knowledge
            if self._agent is None:
                self._agent = Agent(
                    model=model,
                    db=_agno_db,
                    add_history_to_context=True,
                    num_history_runs=settings.num_history_runs,
                    num_history_messages=settings.num_history_messages,
                )
            return self._agent

    async def add_pdf_to_knowledge(self, session_id: str, pdf_text: str, filename: str) -> None:
        """Add PDF content to Knowledge base. Vector search, enable we do.
        
        Args:
            session_id: Session identifier.
            pdf_text: Extracted PDF text content.
            filename: Original PDF filename.
        """
        knowledge = self.get_knowledge(session_id)
        # Write text to temp file, then insert; Agno will chunk and embed it
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write(pdf_text)
            tmp_path = Path(tmp.name)
        try:
            await knowledge.ainsert(
                path=tmp_path,
                name=filename,
                metadata={"source": "pdf_upload", "session_id": session_id},
            )
            logger.info(f"PDF added to knowledge base: {filename}, session: {session_id}")
            # Invalidate cached agent for this session so it picks up new knowledge
            if session_id in self._agents_by_session:
                del self._agents_by_session[session_id]
        finally:
            tmp_path.unlink(missing_ok=True)

    async def stream_response(
        self, message: str, session_id: str | None = None, context: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream response from agent. RAG via Knowledge, use we do; no manual context concatenation.
        
        Args:
            message: User question.
            session_id: Optional session to track history and knowledge.
            context: Deprecated; PDF content should be in Knowledge base via add_pdf_to_knowledge.
            
        Yields:
            Response chunks as they arrive.
        """
        # Get agent with knowledge for this session (if knowledge exists)
        sid = session_id or "default"
        agent = self.get_agent(session_id=sid)
        
        # Use message directly; Agno's add_knowledge_to_context retrieves relevant chunks automatically
        full_message = message

        # Add to session history if session_id provided
        if session_id:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            self._sessions[session_id].append({"role": "user", "content": message})

        try:
            logger.info(f"Streaming response for message: {message[:50]}...")
            response_text = ""

            # Agno: arun(stream=True, session_id=...) so chat history and knowledge are used for this session.
            arun_result = agent.arun(full_message, stream=True, session_id=sid)
            if hasattr(arun_result, "__aiter__"):
                stream = arun_result
            elif inspect.iscoroutine(arun_result):
                stream = await arun_result
            else:
                stream = arun_result
            if not hasattr(stream, "__aiter__"):
                # Not an iterator: treat as RunOutput and yield full content
                content = getattr(stream, "content", None) or ""
                response_text = content if isinstance(content, str) else str(content)
                if response_text:
                    yield response_text
            else:
                try:
                    async for event in stream:
                        chunk = getattr(event, "content", None)
                        if chunk is not None:
                            s = chunk if isinstance(chunk, str) else str(chunk)
                            if s:
                                response_text += s
                                yield s
                except Exception as stream_err:
                    logger.warning(f"Stream iteration failed: {stream_err}, falling back to non-streaming")
                # If stream gave no content, get full response so user always sees a reply
                if not response_text:
                    run_output = await agent.arun(
                        full_message, stream=False, session_id=sid
                    )
                    content = getattr(run_output, "content", None) or ""
                    response_text = content if isinstance(content, str) else str(content)
                    if response_text:
                        yield response_text
                    else:
                        yield "No response from the model. Check your API key and model settings."

            if session_id:
                self._sessions[session_id].append(
                    {"role": "assistant", "content": response_text}
                )
        except Exception as e:
            logger.error(f"Stream error: {e}")
            raise

    def get_session(self, session_id: str) -> list[dict]:
        """Retrieve chat history for session. From Agno db we read when possible.
        
        Args:
            session_id: Session identifier.
            
        Returns:
            List of message dicts with role and content.
        """
        agent = self.get_agent()
        try:
            history = agent.get_chat_history(session_id=session_id)
            if history:
                return [
                    {"role": getattr(m, "role", "user"), "content": getattr(m, "content", "") or ""}
                    for m in history
                ]
        except Exception as e:
            logger.debug(f"Agno get_chat_history failed: {e}, using in-memory")
        return self._sessions.get(session_id, [])

    def clear_session(self, session_id: str) -> None:
        """Clear chat history for session. Forget history, we do.
        
        Args:
            session_id: Session to clear.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session cleared: {session_id}")


# Global manager instance
_manager: AgentManager | None = None


def get_manager() -> AgentManager:
    """Get global agent manager. Singleton, one manager we need."""
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager
