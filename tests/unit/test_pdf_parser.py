"""Unit tests for PDF parser. Parse we do, test we must."""

import pytest
from app.pdf_parser import PDFParser
from app.models import PDFMetadata


def test_validate_pdf_format():
    """PDF format, verify we do."""
    # Valid PDF
    is_valid, error = PDFParser.validate_file("test.pdf", b"fake pdf content")
    assert is_valid is True
    assert error is None

    # Invalid format
    is_valid, error = PDFParser.validate_file("test.txt", b"content")
    assert is_valid is False
    assert "PDF only" in error


def test_validate_pdf_size():
    """PDF size, check we do."""
    # Too large
    large_content = b"x" * (21 * 1024 * 1024)  # 21MB
    is_valid, error = PDFParser.validate_file("test.pdf", large_content)
    assert is_valid is False
    assert "Too large" in error


def test_validate_pdf_empty():
    """Empty PDF, reject we do."""
    is_valid, error = PDFParser.validate_file("test.pdf", b"")
    assert is_valid is False
    assert "Empty" in error


def test_extract_text_invalid_pdf():
    """Corrupt PDF, handle gracefully we do."""
    invalid_pdf = b"This is not a PDF"
    with pytest.raises(ValueError) as exc_info:
        PDFParser.extract_text(invalid_pdf)
    assert "Parse PDF could not we" in str(exc_info.value)


def test_metadata_creation():
    """Metadata model, validate we do."""
    metadata = PDFMetadata(
        filename="test.pdf",
        pages=5,
        size_bytes=10000,
        text_length=5000,
    )
    assert metadata.filename == "test.pdf"
    assert metadata.pages == 5
    assert metadata.size_bytes == 10000
    assert metadata.text_length == 5000
