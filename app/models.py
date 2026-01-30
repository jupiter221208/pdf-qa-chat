"""Data models for the chatbot. Structured data, use Pydantic we do."""

from pydantic import BaseModel, Field
from typing import Optional


class Message(BaseModel):
    """Single message. Role and content, hold it."""

    role: str = Field(..., description="User or assistant, the sender is.")
    content: str = Field(..., description="Message text, contained here.")


class ChatRequest(BaseModel):
    """Client request for chat. Question and context, provide user does."""

    message: str = Field(..., description="User's question or message.")
    session_id: Optional[str] = Field(None, description="Session ID, track history we do.")


class ChatResponse(BaseModel):
    """Streamed response chunk. Content flowing to client, this is."""

    chunk: str = Field(..., description="Text chunk from agent, received we have.")
    status: Optional[str] = Field(None, description="Status message, optional it is.")


class PDFMetadata(BaseModel):
    """PDF file information. Content and metadata, parsed from file."""

    filename: str = Field(..., description="Original filename, stored it is.")
    pages: int = Field(..., description="Page count, extracted we did.")
    size_bytes: int = Field(..., description="File size in bytes, tracked we have.")
    text_length: int = Field(..., description="Extracted text length, measured it is.")


class PDFUploadResponse(BaseModel):
    """Result of PDF upload and parsing. Success or error, communicated here."""

    success: bool = Field(..., description="Parse succeeded, or failed it did.")
    metadata: Optional[PDFMetadata] = Field(None, description="File info, if successful.")
    error: Optional[str] = Field(None, description="Error message, if failed it was.")
    session_id: Optional[str] = Field(None, description="Session under which PDF context is stored.")
