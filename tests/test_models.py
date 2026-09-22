"""Tests for Pydantic data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.resume import (
    ATSAnalysis,
    CandidateSummary,
    CategoryScore,
    ContactInfo,
    FullResumeAnalysis,
    JobMatchAnalysis,
    JobRequirement,
    ResumeAnalysis,
    ResumeLevel,
    ResumeWithJobMatch,
)


class TestResumeAnalysis:
    def test_valid_analysis_from_dict(self, mock_gemini_analysis_response):
        analysis = ResumeAnalysis.model_validate(mock_gemini_analysis_response)
        assert analysis.candidate_name == "John Doe"
        assert analysis.content_quality_score == 82
        assert analysis.level == ResumeLevel.STRONG
        assert len(analysis.strengths) >= 1

    def test_score_range_validation(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        data["content_quality_score"] = 150
        with pytest.raises(ValidationError):
            ResumeAnalysis.model_validate(data)

    def test_negative_score_validation(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        data["skills_relevance_score"] = -5
        with pytest.raises(ValidationError):
            ResumeAnalysis.model_validate(data)

    def test_missing_strengths_fails(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        data["strengths"] = []
        with pytest.raises(ValidationError):
            ResumeAnalysis.model_validate(data)

    def test_missing_weaknesses_fails(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        data["weaknesses"] = []
        with pytest.raises(ValidationError):
            ResumeAnalysis.model_validate(data)

    def test_contact_info_defaults(self):
        contact = ContactInfo()
        assert contact.name == "Unknown"
        assert contact.email is None

    def test_optional_fields_default(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        data.pop("certifications", None)
        analysis = ResumeAnalysis.model_validate(data)
        assert analysis.certifications == []


class TestCategoryScore:
    def test_valid_score(self):
        cs = CategoryScore(category="Content", score=85, evidence="Good content.")
        assert cs.score == 85

    def test_score_boundary_0(self):
        cs = CategoryScore(category="Test", score=0, evidence="Empty.")
        assert cs.score == 0

    def test_score_boundary_100(self):
        cs = CategoryScore(category="Test", score=100, evidence="Perfect.")
        assert cs.score == 100

    def test_score_over_100_fails(self):
        with pytest.raises(ValidationError):
            CategoryScore(category="Test", score=101, evidence="Invalid.")


class TestJobMatchAnalysis:
    def test_valid_job_match(self):
        jm = JobMatchAnalysis(
            job_match_score=85,
            match_summary="Good match.",
            matched_requirements=[
                JobRequirement(requirement="Python", category="Required", met=True, evidence="Listed in skills.")
            ],
        )
        assert jm.job_match_score == 85

    def test_job_match_score_range(self):
        with pytest.raises(ValidationError):
            JobMatchAnalysis(job_match_score=200, match_summary="Invalid.")


class TestCandidateSummary:
    def test_valid_candidate(self):
        c = CandidateSummary(
            rank=1, candidate_name="Jane", file_name="jane.pdf",
            overall_score=90, content_score=88, skills_score=92,
            experience_score=85, ats_score=90,
        )
        assert c.rank == 1
        assert c.job_match_score is None

    def test_rank_must_be_positive(self):
        with pytest.raises(ValidationError):
            CandidateSummary(
                rank=0, candidate_name="Test", file_name="test.pdf",
                overall_score=50, content_score=50, skills_score=50,
                experience_score=50, ats_score=50,
            )


class TestResumeWithJobMatch:
    def test_schema_includes_job_requirement_in_defs(self):
        schema = ResumeWithJobMatch.model_json_schema()
        assert "$defs" in schema
        assert "JobRequirement" in schema["$defs"]
        assert "JobMatchAnalysis" in schema["$defs"]
        assert "job_match" in schema["properties"]

    def test_valid_validation_with_job_match(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        data["job_match"] = {
            "job_match_score": 85,
            "match_summary": "Strong candidate match.",
            "matched_requirements": [
                {
                    "requirement": "Python experience",
                    "category": "Required",
                    "met": True,
                    "evidence": "5 years Python listed",
                }
            ],
            "missing_requirements": [],
            "relevant_skills": ["Python", "FastAPI"],
            "missing_skills": [],
            "relevant_experience": ["Software Engineer"],
            "experience_alignment": "Well aligned",
            "education_alignment": "BS Computer Science",
            "keyword_matches": ["Python"],
            "missing_keywords": [],
        }
        model = ResumeWithJobMatch.model_validate(data)
        assert model.candidate_name == "John Doe"
        assert model.job_match is not None
        assert model.job_match.job_match_score == 85


