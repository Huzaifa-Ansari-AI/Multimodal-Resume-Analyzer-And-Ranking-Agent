"""Tests for document processing service."""

from __future__ import annotations

import pytest

from app.services.document_processor import (
    ProcessedDocument,
    ValidationResult,
    build_gemini_input,
    process_document,
    validate_file,
)


class TestValidateFile:
    """Test file validation logic."""

    def test_valid_txt_file(self, sample_resume_bytes):
        result = validate_file("resume.txt", len(sample_resume_bytes), sample_resume_bytes)
        assert result.is_valid
        assert result.extension == ".txt"
        assert result.processing_strategy == "text"

    def test_valid_pdf_extension(self, fake_pdf_bytes):
        result = validate_file("resume.pdf", len(fake_pdf_bytes), fake_pdf_bytes)
        assert result.is_valid
        assert result.extension == ".pdf"
        assert result.processing_strategy == "document"

    def test_valid_png_extension(self, fake_png_bytes):
        result = validate_file("resume.png", len(fake_png_bytes), fake_png_bytes)
        assert result.is_valid
        assert result.processing_strategy == "image"

    def test_valid_jpeg_extension(self, fake_jpeg_bytes):
        result = validate_file("photo.jpg", len(fake_jpeg_bytes), fake_jpeg_bytes)
        assert result.is_valid
        assert result.processing_strategy == "image"

    def test_unsupported_extension(self):
        result = validate_file("resume.exe", 100, b"MZ\x90\x00")
        assert not result.is_valid
        assert "Unsupported" in result.error

    def test_empty_file(self):
        result = validate_file("empty.txt", 0, b"")
        assert not result.is_valid
        assert "empty" in result.error.lower()

    def test_file_too_large(self, sample_resume_bytes):
        result = validate_file("huge.txt", 100 * 1024 * 1024, sample_resume_bytes)
        assert not result.is_valid
        assert "too large" in result.error.lower()

    def test_corrupt_pdf(self):
        result = validate_file("bad.pdf", 10, b"not a pdf!")
        assert not result.is_valid
        assert "valid PDF" in result.error

    def test_corrupt_png(self):
        result = validate_file("bad.png", 10, b"not a png!")
        assert not result.is_valid
        assert "valid PNG" in result.error

    def test_corrupt_jpeg(self):
        result = validate_file("bad.jpg", 10, b"not a jpg!")
        assert not result.is_valid
        assert "valid JPEG" in result.error

    def test_md_file_supported(self, sample_resume_bytes):
        result = validate_file("resume.md", len(sample_resume_bytes), sample_resume_bytes)
        assert result.is_valid
        assert result.processing_strategy == "text"

    def test_docx_extension(self):
        docx_header = b"PK\x03\x04" + b"\x00" * 100
        result = validate_file("resume.docx", len(docx_header), docx_header)
        assert result.is_valid
        assert result.processing_strategy == "docx"

    def test_case_insensitive_extension(self, fake_pdf_bytes):
        result = validate_file("resume.PDF", len(fake_pdf_bytes), fake_pdf_bytes)
        assert result.is_valid

    def test_webp_valid(self):
        webp_bytes = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 20
        result = validate_file("photo.webp", len(webp_bytes), webp_bytes)
        assert result.is_valid


class TestProcessDocument:
    """Test document processing logic."""

    def test_process_text_file(self, sample_resume_bytes):
        doc = process_document("resume.txt", sample_resume_bytes)
        assert doc.is_valid
        assert doc.content_type == "text"
        assert doc.text_content is not None
        assert "JOHN DOE" in doc.text_content

    def test_process_empty_file(self):
        doc = process_document("empty.txt", b"")
        assert not doc.is_valid
        assert doc.error is not None

    def test_process_unsupported_file(self):
        doc = process_document("resume.exe", b"MZ\x90\x00")
        assert not doc.is_valid
        assert "Unsupported" in doc.error

    def test_process_pdf_produces_document_type(self, fake_pdf_bytes):
        doc = process_document("resume.pdf", fake_pdf_bytes)
        assert doc.is_valid
        assert doc.content_type == "document"
        assert doc.data_base64 is not None

    def test_process_image_produces_image_type(self, fake_png_bytes):
        doc = process_document("resume.png", fake_png_bytes)
        assert doc.is_valid
        assert doc.content_type == "image"
        assert doc.data_base64 is not None

    def test_process_text_encoding_fallback(self):
        latin1_text = "R\xe9sum\xe9 caf\xe9".encode("latin-1")
        doc = process_document("resume.txt", latin1_text)
        assert doc.is_valid
        assert doc.text_content is not None
        assert len(doc.warnings) > 0

    def test_process_whitespace_only_text(self):
        doc = process_document("blank.txt", b"   \n\n   ")
        assert doc.is_valid
        assert len(doc.warnings) > 0


class TestBuildGeminiInput:
    """Test Gemini API input construction."""

    def test_text_document_input(self, sample_resume_bytes):
        doc = process_document("resume.txt", sample_resume_bytes)
        inputs = build_gemini_input(doc)
        assert len(inputs) == 1
        assert inputs[0]["type"] == "text"

    def test_pdf_document_input(self, fake_pdf_bytes):
        doc = process_document("resume.pdf", fake_pdf_bytes)
        inputs = build_gemini_input(doc)
        assert len(inputs) == 1
        assert inputs[0]["type"] == "document"
        assert inputs[0]["mime_type"] == "application/pdf"

    def test_image_input(self, fake_png_bytes):
        doc = process_document("resume.png", fake_png_bytes)
        inputs = build_gemini_input(doc)
        assert len(inputs) == 1
        assert inputs[0]["type"] == "image"

    def test_invalid_document_raises(self):
        doc = ProcessedDocument(
            file_name="bad.exe", file_size=0, content_type="unknown",
            mime_type="", is_valid=False, error="Unsupported",
        )
        with pytest.raises(ValueError):
            build_gemini_input(doc)
