"""Ranking and filtering service for recruiter mode.

Provides sorting, filtering, and export utilities for multi-resume comparison.
Ranking is based ONLY on job-relevant criteria — never on protected characteristics.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Optional

from app.models.resume import CandidateSummary, FullResumeAnalysis, RecruiterResults


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

SORT_OPTIONS = {
    "Overall Score": lambda c: c.overall_score,
    "Job Match": lambda c: c.job_match_score or 0,
    "Skills": lambda c: c.skills_score,
    "Experience": lambda c: c.experience_score,
    "ATS Score": lambda c: c.ats_score,
    "Content": lambda c: c.content_score,
}


def sort_candidates(
    candidates: list[CandidateSummary],
    sort_by: str = "Overall Score",
    ascending: bool = False,
) -> list[CandidateSummary]:
    """Sort candidates by a given criterion."""
    key_fn = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["Overall Score"])
    sorted_list = sorted(candidates, key=key_fn, reverse=not ascending)

    # Re-rank
    for i, candidate in enumerate(sorted_list, 1):
        candidate.rank = i

    return sorted_list


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_candidates(
    candidates: list[CandidateSummary],
    min_overall: int = 0,
    min_job_match: int = 0,
    min_ats: int = 0,
    required_skills: list[str] | None = None,
    detailed_analyses: list[FullResumeAnalysis] | None = None,
) -> list[CandidateSummary]:
    """Filter candidates by score thresholds and skills.

    Args:
        candidates: List to filter.
        min_overall: Minimum overall score.
        min_job_match: Minimum job match score.
        min_ats: Minimum ATS score.
        required_skills: Skills that must be present (checked in detailed analyses).
        detailed_analyses: Full analyses for skill checking.
    """
    filtered: list[CandidateSummary] = []

    # Build a lookup for detailed analyses by file name
    detail_lookup: dict[str, FullResumeAnalysis] = {}
    if detailed_analyses:
        for d in detailed_analyses:
            detail_lookup[d.file_name] = d

    for candidate in candidates:
        # Score filters
        if candidate.overall_score < min_overall:
            continue
        if min_job_match > 0 and (candidate.job_match_score or 0) < min_job_match:
            continue
        if candidate.ats_score < min_ats:
            continue

        # Skill filter
        if required_skills and detailed_analyses:
            detail = detail_lookup.get(candidate.file_name)
            if detail and detail.processing_status == "success":
                candidate_skills = {s.lower() for s in detail.resume_analysis.skills}
                required_lower = {s.lower() for s in required_skills}
                if not required_lower.issubset(candidate_skills):
                    continue

        filtered.append(candidate)

    # Re-rank
    for i, candidate in enumerate(filtered, 1):
        candidate.rank = i

    return filtered


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_to_csv(results: RecruiterResults) -> str:
    """Export comparison results to CSV string.

    Only includes job-relevant data — no sensitive/personal information.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    header = [
        "Rank", "Candidate", "File", "Overall Score",
        "Content", "Skills", "Experience", "ATS Score",
    ]
    if any(c.job_match_score is not None for c in results.candidates):
        header.insert(4, "Job Match")
    header.extend(["Top Strengths", "Top Weaknesses"])

    writer.writerow(header)

    for c in results.candidates:
        row = [
            c.rank, c.candidate_name, c.file_name, c.overall_score,
        ]
        if any(c2.job_match_score is not None for c2 in results.candidates):
            row.append(c.job_match_score or "N/A")
        row.extend([
            c.content_score, c.skills_score, c.experience_score, c.ats_score,
            "; ".join(c.top_strengths),
            "; ".join(c.top_weaknesses),
        ])
        writer.writerow(row)

    return output.getvalue()


def export_to_json(results: RecruiterResults) -> str:
    """Export comparison results to JSON string."""
    data = {
        "job_title": results.job_title,
        "total_processed": results.total_processed,
        "total_failed": results.total_failed,
        "candidates": [c.model_dump() for c in results.candidates],
    }
    return json.dumps(data, indent=2)
