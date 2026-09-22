"""Job matching utilities.

Provides helper functions for working with job descriptions alongside
resume analysis. The actual LLM-based matching is done inside the Gemini
service (via the job match prompt). This module handles pre/post-processing.
"""

from __future__ import annotations

from app.models.resume import FullResumeAnalysis, JobMatchAnalysis


def has_job_match(result: FullResumeAnalysis) -> bool:
    """Check if a result includes a job match analysis."""
    return result.job_match is not None


def get_match_reasons(match: JobMatchAnalysis) -> tuple[list[str], list[str]]:
    """Extract positive and negative match reasons.

    Returns:
        Tuple of (positive_reasons, negative_reasons) as concise strings.
    """
    positives: list[str] = []
    negatives: list[str] = []

    for req in match.matched_requirements:
        if req.met:
            positives.append(f"+ {req.requirement}: {req.evidence}")

    for req in match.missing_requirements:
        if not req.met:
            negatives.append(f"- {req.requirement}: {req.evidence}")

    # Add skill-based reasons
    if match.relevant_skills:
        positives.append(f"+ Skills matched: {', '.join(match.relevant_skills[:5])}")

    if match.missing_skills:
        negatives.append(f"- Missing skills: {', '.join(match.missing_skills[:5])}")

    return positives, negatives
