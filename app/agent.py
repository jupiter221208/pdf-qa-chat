"""Agno agent wiring. OpenAI model we use; from config, key we take."""

import logging
from typing import AsyncGenerator
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from app.config import get_settings

logger = logging.getLogger(__name__)


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
            self._agent = Agent(model=model)
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

        # Build full message with context. From the PDF alone answer we must, when context we have.
        full_message = message
        if context:
            full_message = (
                "Answer using only the following document context. "
                "If the answer is not in the context, say so. Do not invent details.\n\n"
                f"Document context:\n{context}\n\n"
                f"Question: {message}"
            )

        # Add to session history if session_id provided
        if session_id:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            self._sessions[session_id].append({"role": "user", "content": message})

        try:
            # Stream from agent using run_response with stream
            logger.info(f"Streaming response for message: {message[:50]}...")
            
            response_text = ""
            # Use agent.run() which returns a Response object with streaming capability
            response = await agent.arun(full_message)
            
            # If response has content, yield it
            if response and hasattr(response, 'content'):
                response_text = response.content
                # Yield character by character for true streaming effect
                for char in response_text:
                    yield char
            else:
                # Fallback: yield the whole response
                response_text = str(response) if response else ""
                for char in response_text:
                    yield char

            # Store in session
            if session_id:
                self._sessions[session_id].append(
                    {"role": "assistant", "content": response_text}
                )
        except Exception as e:
            logger.error(f"Stream error: {e}")
            raise

    def get_session(self, session_id: str) -> list[dict]:
        """Retrieve chat history for session. Messages, return we do.
        
        Args:
            session_id: Session identifier.
            
        Returns:
            List of message dicts with role and content.
        """
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
