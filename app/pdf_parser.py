"""PDF parsing and extraction. Clean text from PDFs, get we do."""

import logging
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.models import PDFMetadata

logger = logging.getLogger(__name__)

MAX_PDF_SIZE_MB = 20
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024


class PDFParser:
    """Parse PDF files. Content extract and validate, we accomplish."""

    @staticmethod
    def validate_file(
        filename: str, file_content: bytes
    ) -> tuple[bool, str | None]:
        """Validate PDF file. Size and format, check we do.
        
        Args:
            filename: Name of file, check we must.
            file_content: Binary data, validate we do.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        # File type check
        if not filename.lower().endswith(".pdf"):
            return False, "PDF only, accept we do. Other formats, reject we must."

        # Size check
        if len(file_content) > MAX_PDF_SIZE_BYTES:
            return False, f"Too large, file is. {MAX_PDF_SIZE_MB}MB max, accept we do."

        # Empty check
        if len(file_content) == 0:
            return False, "Empty file, received we have. Content, provide you must."

        return True, None

    @staticmethod
    def extract_text(file_content: bytes) -> tuple[str, int]:
        """Extract text from PDF bytes. Pages iterate, text gather we do.
        
        Args:
            file_content: PDF file as bytes.
            
        Returns:
            Tuple of (extracted_text, page_count).
            
        Raises:
            ValueError: If corrupt or invalid, the PDF is.
        """
        try:
            pdf_file = BytesIO(file_content)
            reader = PdfReader(pdf_file)
            page_count = len(reader.pages)

            if page_count == 0:
                raise ValueError("No pages, contain this PDF does.")

            text_parts: list[str] = []
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text.strip():  # Empty pages, skip we do.
                    text_parts.append(f"--- Page {page_num} ---\n{text}\n")

            full_text = "\n".join(text_parts)
            if not full_text.strip():
                raise ValueError("Text extract could not we. Scanned image, perhaps it is?")

            return full_text, page_count
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise ValueError(f"Parse PDF could not we: {str(e)}")

    @staticmethod
    def parse(filename: str, file_content: bytes) -> tuple[PDFMetadata, str]:
        """Parse PDF. Validate, extract, and metadata build we do.
        
        Args:
            filename: Name of file.
            file_content: Binary PDF data.
            
        Returns:
            Tuple of (metadata, extracted_text).
            
        Raises:
            ValueError: If invalid or unreadable, the file is.
        """
        # Validate file
        is_valid, error = PDFParser.validate_file(filename, file_content)
        if not is_valid:
            raise ValueError(error or "Validation failed, it did.")

        # Extract text
        text, page_count = PDFParser.extract_text(file_content)

        # Build metadata
        metadata = PDFMetadata(
            filename=filename,
            pages=page_count,
            size_bytes=len(file_content),
            text_length=len(text),
        )

        return metadata, text
