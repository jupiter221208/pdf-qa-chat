"""Unit tests for PDF parser. Parse we do, test we must."""

from pathlib import Path

import pytest
import pytest_check as check

from app.models import PDFMetadata
from app.pdf_parser import PDFParser

# Real sample PDF in tests/data (assignment: unit tests with real sample files)
TESTS_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_PDF = TESTS_DATA_DIR / "linear-guest.pdf"


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


def test_validate_file_real_sample():
    """Real sample PDF from tests/data, validate we do."""
    check.is_true(SAMPLE_PDF.exists(), f"Sample PDF missing: {SAMPLE_PDF}")
    content = SAMPLE_PDF.read_bytes()
    is_valid, error = PDFParser.validate_file(SAMPLE_PDF.name, content)
    check.is_true(is_valid)
    check.is_none(error)


def test_extract_text_real_sample():
    """Real sample PDF from tests/data, extract text we do."""
    check.is_true(SAMPLE_PDF.exists(), f"Sample PDF missing: {SAMPLE_PDF}")
    content = SAMPLE_PDF.read_bytes()
    text, page_count = PDFParser.extract_text(content)
    check.greater(page_count, 0)
    check.greater(len(text), 0)
    check.is_instance(text, str)


def test_parse_real_sample():
    """Real sample PDF from tests/data, full parse we do."""
    check.is_true(SAMPLE_PDF.exists(), f"Sample PDF missing: {SAMPLE_PDF}")
    content = SAMPLE_PDF.read_bytes()
    metadata, text = PDFParser.parse(SAMPLE_PDF.name, content)
    check.equal(metadata.filename, SAMPLE_PDF.name)
    check.greater(metadata.pages, 0)
    check.equal(metadata.size_bytes, len(content))
    check.equal(metadata.text_length, len(text))
    check.greater(len(text), 0)
