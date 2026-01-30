"""Agno agent wiring. OpenAI model we use; from config, key we take."""

import asyncio
import inspect
import logging
from pathlib import Path
from typing import AsyncGenerator
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat

from app.config import get_settings

logger = logging.getLogger(__name__)

# Sqlite for Agno session/chat history; one file per app
_db_path = Path(__file__).resolve().parent.parent / "data" / "agent.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)
_agno_db = SqliteDb(db_file=str(_db_path))


class AgentManager:
    """Manage agent instances and sessions. Create and reuse agents, we do."""

    def __init__(self):
        """Initialize manager. Agent cache, maintain we shall."""
        self._agent: Agent | None = None
        self._sessions: dict[str, list[dict]] = {}

    def get_agent(self) -> Agent:
        """Get or create agent. Singleton pattern, use we do.
        
        Returns:
            Agent configured with OpenAI.
            
        Raises:
            ValueError: If API key missing, raise we do.
        """
        if self._agent is None:
            settings = get_settings()
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set. In .env put it, you must.")
            model = OpenAIChat(
                id=settings.openai_model_id,
                api_key=settings.openai_api_key,
            )
            self._agent = Agent(
                model=model,
                db=_agno_db,
                add_history_to_context=True,
            )
        return self._agent

    async def stream_response(
        self, message: str, session_id: str | None = None, context: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Stream response from agent. Token by token, yield we do.
        
        Args:
            message: User question.
            session_id: Optional session to track history.
            context: Optional knowledge context (PDF text, etc).
            
        Yields:
            Response chunks as they arrive.
        """
        agent = self.get_agent()

        # Build full message with context. From PDF prefer we do; when not in PDF, general knowledge use we may.
        full_message = message
        if context:
            full_message = (
                "Use the following document context when it contains the answer. "
                "When the answer is in the document, base your response on it. "
                "When the answer is not in the document, you may use your general knowledge to answer; "
                "if you do, briefly note that it is not from the document.\n\n"
                f"Document context:\n{context}\n\n"
                f"Question: {message}"
            )

        # Add to session history if session_id provided
        if session_id:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            self._sessions[session_id].append({"role": "user", "content": message})

        try:
            logger.info(f"Streaming response for message: {message[:50]}...")
            response_text = ""

            # Agno: arun(stream=True, session_id=...) so chat history is loaded and saved for this session.
            arun_result = agent.arun(full_message, stream=True, session_id=session_id or "default")
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
                        full_message, stream=False, session_id=session_id or "default"
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
