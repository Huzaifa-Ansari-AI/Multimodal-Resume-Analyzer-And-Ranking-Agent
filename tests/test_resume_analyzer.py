"""Tests for resume analysis, scoring, and ranking logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import SCORING_WEIGHTS
from app.models.resume import CandidateSummary, RecruiterResults, ResumeAnalysis, ResumeLevel
from app.services.resume_analyzer import (
    _empty_analysis,
    analyze_single_resume,
    calculate_overall_score,
    validate_analysis,
)
from app.services.ranking import export_to_csv, export_to_json, filter_candidates, sort_candidates


class TestCalculateOverallScore:
    def test_perfect_scores(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        for key in list(data.keys()):
            if key.endswith("_score") and isinstance(data[key], int):
                data[key] = 100
        data["ats_analysis"]["score"] = 100
        data["visual_analysis"]["score"] = 100
        analysis = ResumeAnalysis.model_validate(data)
        assert calculate_overall_score(analysis) == 100

    def test_zero_scores(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        for key in list(data.keys()):
            if key.endswith("_score") and isinstance(data[key], int):
                data[key] = 0
        data["ats_analysis"]["score"] = 0
        data["visual_analysis"]["score"] = 0
        analysis = ResumeAnalysis.model_validate(data)
        assert calculate_overall_score(analysis) == 0

    def test_weighted_calculation(self, mock_gemini_analysis_response):
        analysis = ResumeAnalysis.model_validate(mock_gemini_analysis_response)
        score = calculate_overall_score(analysis)
        expected = round(
            analysis.content_quality_score * 0.20
            + analysis.experience_achievements_score * 0.20
            + analysis.skills_relevance_score * 0.15
            + analysis.ats_compatibility_score * 0.15
            + analysis.structure_readability_score * 0.10
            + analysis.impact_quantification_score * 0.10
            + analysis.language_communication_score * 0.05
            + analysis.visual_document_quality_score * 0.05
        )
        assert score == expected

    def test_weights_sum_to_100(self):
        assert sum(SCORING_WEIGHTS.values()) == 100


class TestValidateAnalysis:
    def test_normal_analysis_no_crash(self, mock_gemini_analysis_response):
        analysis = ResumeAnalysis.model_validate(mock_gemini_analysis_response)
        warnings = validate_analysis(analysis)
        assert isinstance(warnings, list)

    def test_extreme_variance_warns(self, mock_gemini_analysis_response):
        data = mock_gemini_analysis_response.copy()
        data["content_quality_score"] = 95
        data["impact_quantification_score"] = 20
        analysis = ResumeAnalysis.model_validate(data)
        warnings = validate_analysis(analysis)
        assert any("variance" in w.lower() for w in warnings)


class TestEmptyAnalysis:
    def test_empty_analysis_is_valid(self):
        analysis = _empty_analysis("Test error")
        assert analysis.candidate_name == "Unknown"
        assert analysis.level == ResumeLevel.POOR

    def test_empty_analysis_has_warnings(self):
        analysis = _empty_analysis("API timeout")
        assert any("API timeout" in w for w in analysis.warnings)


class TestAnalyzeSingleResume:
    @patch("app.services.resume_analyzer.get_client")
    @patch("app.services.resume_analyzer.analyze_resume")
    def test_successful_analysis(self, mock_analyze, mock_get_client, sample_resume_bytes, mock_gemini_analysis_response):
        mock_get_client.return_value = MagicMock()
        mock_analyze.return_value = mock_gemini_analysis_response
        result = analyze_single_resume("resume.txt", sample_resume_bytes)
        assert result.processing_status == "success"
        assert result.overall_score > 0
        assert result.resume_analysis.candidate_name == "John Doe"

    @patch("app.services.resume_analyzer.get_client")
    @patch("app.services.resume_analyzer.analyze_resume")
    def test_gemini_failure_handled(self, mock_analyze, mock_get_client, sample_resume_bytes):
        from app.services.gemini_service import GeminiServiceError
        mock_get_client.return_value = MagicMock()
        mock_analyze.side_effect = GeminiServiceError("API quota exceeded")
        result = analyze_single_resume("resume.txt", sample_resume_bytes)
        assert result.processing_status == "failed"
        assert "quota" in result.error_message.lower()

    @patch("app.services.resume_analyzer.get_client")
    def test_invalid_file_handled(self, mock_get_client):
        mock_get_client.return_value = MagicMock()
        result = analyze_single_resume("malware.exe", b"MZ\x90\x00bad")
        assert result.processing_status == "failed"
        assert "Unsupported" in result.error_message

    @patch("app.services.resume_analyzer.get_client")
    def test_missing_api_key(self, mock_get_client, sample_resume_bytes):
        mock_get_client.side_effect = ValueError("GEMINI_API_KEY is not set")
        result = analyze_single_resume("resume.txt", sample_resume_bytes)
        assert result.processing_status == "failed"
        assert "API_KEY" in result.error_message


class TestRanking:
    @pytest.fixture
    def sample_candidates(self):
        return [
            CandidateSummary(rank=1, candidate_name="Alice", file_name="alice.pdf",
                             overall_score=90, job_match_score=88, content_score=85,
                             skills_score=92, experience_score=88, ats_score=90),
            CandidateSummary(rank=2, candidate_name="Bob", file_name="bob.pdf",
                             overall_score=75, job_match_score=70, content_score=72,
                             skills_score=78, experience_score=70, ats_score=80),
            CandidateSummary(rank=3, candidate_name="Charlie", file_name="charlie.pdf",
                             overall_score=60, job_match_score=55, content_score=58,
                             skills_score=65, experience_score=55, ats_score=62),
        ]

    def test_sort_by_overall(self, sample_candidates):
        sorted_c = sort_candidates(sample_candidates, "Overall Score")
        assert sorted_c[0].candidate_name == "Alice"
        assert sorted_c[-1].candidate_name == "Charlie"

    def test_sort_ascending(self, sample_candidates):
        sorted_c = sort_candidates(sample_candidates, "Overall Score", ascending=True)
        assert sorted_c[0].candidate_name == "Charlie"

    def test_filter_by_min_overall(self, sample_candidates):
        filtered = filter_candidates(sample_candidates, min_overall=70)
        assert len(filtered) == 2
        assert all(c.overall_score >= 70 for c in filtered)

    def test_filter_by_min_ats(self, sample_candidates):
        filtered = filter_candidates(sample_candidates, min_ats=80)
        assert len(filtered) == 2

    def test_filter_updates_ranks(self, sample_candidates):
        filtered = filter_candidates(sample_candidates, min_overall=70)
        assert filtered[0].rank == 1
        assert filtered[1].rank == 2

    def test_export_csv(self, sample_candidates):
        results = RecruiterResults(candidates=sample_candidates, total_processed=3)
        csv_data = export_to_csv(results)
        assert "Alice" in csv_data
        assert "Rank" in csv_data

    def test_export_json(self, sample_candidates):
        results = RecruiterResults(candidates=sample_candidates, total_processed=3)
        json_data = export_to_json(results)
        parsed = json.loads(json_data)
        assert parsed["total_processed"] == 3
        assert len(parsed["candidates"]) == 3
