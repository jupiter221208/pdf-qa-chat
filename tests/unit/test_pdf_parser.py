"""Unit tests for PDF parser. Parse we do, test we must."""

import pytest
import pytest_check as check

from app.models import PDFMetadata
from app.pdf_parser import PDFParser


def test_validate_pdf_format():
    """PDF format, verify we do."""
    # Valid PDF
    is_valid, error = PDFParser.validate_file("test.pdf", b"fake pdf content")
    check.is_true(is_valid)
    check.is_none(error)

    # Invalid format
    is_valid, error = PDFParser.validate_file("test.txt", b"content")
    check.is_false(is_valid)
    check.is_in("PDF only", error)


def test_validate_pdf_size():
    """PDF size, check we do."""
    # Too large
    large_content = b"x" * (21 * 1024 * 1024)  # 21MB
    is_valid, error = PDFParser.validate_file("test.pdf", large_content)
    check.is_false(is_valid)
    check.is_in("Too large", error)


def test_validate_pdf_empty():
    """Empty PDF, reject we do."""
    is_valid, error = PDFParser.validate_file("test.pdf", b"")
    check.is_false(is_valid)
    check.is_in("Empty", error)


def test_extract_text_invalid_pdf():
    """Corrupt PDF, handle gracefully we do."""
    invalid_pdf = b"This is not a PDF"
    with pytest.raises(ValueError) as exc_info:
        PDFParser.extract_text(invalid_pdf)
    check.is_in("Parse PDF could not we", str(exc_info.value))


def test_metadata_creation():
    """Metadata model, validate we do."""
    metadata = PDFMetadata(
        filename="test.pdf",
        pages=5,
        size_bytes=10000,
        text_length=5000,
    )
    check.equal(metadata.filename, "test.pdf")
    check.equal(metadata.pages, 5)
    check.equal(metadata.size_bytes, 10000)
    check.equal(metadata.text_length, 5000)
