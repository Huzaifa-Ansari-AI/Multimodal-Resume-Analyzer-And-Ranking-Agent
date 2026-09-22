"""Shared test fixtures and mocks."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_resume_bytes() -> bytes:
    """Load the strong sample resume as bytes."""
    return (FIXTURES_DIR / "sample_resume.txt").read_bytes()


@pytest.fixture
def poor_resume_bytes() -> bytes:
    """Load the poor sample resume as bytes."""
    return (FIXTURES_DIR / "sample_resume_poor.txt").read_bytes()


@pytest.fixture
def sample_job_description() -> str:
    """Load the sample job description."""
    return (FIXTURES_DIR / "sample_job_description.txt").read_text()


@pytest.fixture
def empty_file_bytes() -> bytes:
    """Empty file."""
    return b""


@pytest.fixture
def fake_pdf_bytes() -> bytes:
    """Minimal valid PDF header (not a real PDF but passes magic byte check)."""
    return b"%PDF-1.4 fake content for testing"


@pytest.fixture
def fake_png_bytes() -> bytes:
    """Minimal PNG header."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def fake_jpeg_bytes() -> bytes:
    """Minimal JPEG header."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


@pytest.fixture
def mock_gemini_analysis_response() -> dict:
    """A valid structured analysis response matching ResumeAnalysis schema."""
    return {
        "candidate_name": "John Doe",
        "contact": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "(555) 123-4567",
            "location": "San Francisco, CA",
            "linkedin": "linkedin.com/in/johndoe",
            "portfolio": "johndoe.dev",
        },
        "summary": "Experienced software engineer with 4 years of experience.",
        "verdict": "Strong technical resume with good quantified achievements.",
        "level": "Strong",
        "education": [
            {
                "degree": "BS Computer Science",
                "institution": "UC Berkeley",
                "year": "2020",
                "details": "GPA: 3.7/4.0",
            }
        ],
        "experience": [
            {
                "title": "Senior Software Engineer",
                "company": "TechCorp Inc.",
                "duration": "Jan 2022 – Present",
                "highlights": [
                    "Led development serving 500K DAU",
                    "Reduced API response time by 40%",
                ],
            }
        ],
        "projects": [
            {
                "name": "CLI Tool",
                "description": "Python CLI for dev workflows",
                "technologies": ["Python", "Click", "Docker"],
                "outcome": "200+ GitHub stars",
            }
        ],
        "skills": ["Python", "JavaScript", "React", "FastAPI", "AWS", "Docker"],
        "certifications": ["AWS Solutions Architect"],
        "achievements": ["Led team of 3", "92% code coverage"],
        "languages": ["English", "Spanish"],
        "content_quality_score": 82,
        "experience_achievements_score": 78,
        "skills_relevance_score": 85,
        "ats_compatibility_score": 88,
        "structure_readability_score": 80,
        "impact_quantification_score": 75,
        "language_communication_score": 84,
        "visual_document_quality_score": 70,
        "category_scores": [
            {"category": "Content Quality", "score": 82, "evidence": "Well-structured with all key sections."},
            {"category": "Experience", "score": 78, "evidence": "Good quantified achievements."},
        ],
        "strengths": [
            {"title": "Quantified Achievements", "detail": "Multiple metrics like 40% improvement, 500K users."},
            {"title": "Technical Breadth", "detail": "Strong full-stack skills with cloud experience."},
            {"title": "Clear Structure", "detail": "Well-organized sections with consistent formatting."},
        ],
        "weaknesses": [
            {"title": "Limited Leadership Detail", "detail": "Mentoring mentioned but leadership not emphasized."},
            {"title": "No Summary Section", "detail": "Missing professional summary section at top."},
        ],
        "recommendations": [
            {
                "title": "Add Professional Summary",
                "detail": "Add a 2-3 sentence summary highlighting key strengths.",
                "priority": "High",
            },
            {
                "title": "Expand Leadership",
                "detail": "Describe leadership responsibilities with measurable outcomes.",
                "priority": "Medium",
            },
        ],
        "ats_analysis": {
            "score": 88,
            "has_standard_sections": True,
            "has_contact_info": True,
            "text_extractable": True,
            "issues": ["Consider adding a professional summary section"],
            "suggestions": ["Ensure skills section matches common ATS keywords"],
        },
        "visual_analysis": {
            "score": 70,
            "has_photo": False,
            "layout_type": "Single Column",
            "observations": ["Clean text-based layout", "Good use of whitespace"],
        },
        "keywords": {
            "extracted_keywords": ["Python", "FastAPI", "React", "AWS", "Docker"],
            "missing_keywords": ["Agile", "Scrum"],
        },
        "extraction_confidence": "High",
        "warnings": [],
    }


@pytest.fixture
def mock_gemini_client(mock_gemini_analysis_response):
    """Mock Gemini client that returns a valid analysis."""
    client = MagicMock()

    mock_text_output = MagicMock()
    mock_text_output.text = json.dumps(mock_gemini_analysis_response)

    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(mock_gemini_analysis_response)
    mock_interaction.steps = []

    client.interactions.create.return_value = mock_interaction
    client.files.upload.return_value = MagicMock(uri="gs://fake/file", mime_type="application/pdf")

    return client
