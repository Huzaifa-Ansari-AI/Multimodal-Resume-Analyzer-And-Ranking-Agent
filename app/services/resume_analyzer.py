"""Resume analysis orchestrator.

Coordinates document processing → Gemini analysis → score validation → result assembly.
Handles both single and batch resume analysis.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.config import (
    AI_GATEWAY_API_KEY,
    AI_GATEWAY_DEFAULT_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    SCORING_WEIGHTS,
    get_ai_gateway_api_key,
    get_gemini_api_key,
)
from app.models.resume import (
    CandidateSummary,
    FullResumeAnalysis,
    JobMatchAnalysis,
    RecruiterResults,
    ResumeAnalysis,
)
from app.services.document_processor import ProcessedDocument, process_document
from app.services.gemini_service import GeminiServiceError, analyze_resume, get_client
from app.services.vercel_gateway_service import (
    VercelGatewayServiceError,
    analyze_resume_gateway,
)

logger = logging.getLogger(__name__)


def calculate_overall_score(analysis: ResumeAnalysis) -> int:
    """Calculate the weighted overall score from category scores.

    Uses deterministic weighted aggregation — NOT the LLM's opinion.
    This ensures score consistency.
    """
    scores = {
        "content_quality": analysis.content_quality_score,
        "experience_achievements": analysis.experience_achievements_score,
        "skills_relevance": analysis.skills_relevance_score,
        "ats_compatibility": analysis.ats_compatibility_score,
        "structure_readability": analysis.structure_readability_score,
        "impact_quantification": analysis.impact_quantification_score,
        "language_communication": analysis.language_communication_score,
        "visual_document_quality": analysis.visual_document_quality_score,
    }

    weighted_sum = sum(
        scores[category] * (weight / 100)
        for category, weight in SCORING_WEIGHTS.items()
    )

    return round(weighted_sum)


def validate_analysis(analysis: ResumeAnalysis) -> list[str]:
    """Validate the analysis for internal consistency.

    Returns a list of warnings if any issues found.
    """
    warnings: list[str] = []

    # Check that scores are reasonable
    score_fields = [
        analysis.content_quality_score,
        analysis.experience_achievements_score,
        analysis.skills_relevance_score,
        analysis.ats_compatibility_score,
        analysis.structure_readability_score,
        analysis.impact_quantification_score,
        analysis.language_communication_score,
        analysis.visual_document_quality_score,
    ]

    # Check for extreme variance (e.g., one score at 95 while others at 40)
    if score_fields:
        avg = sum(score_fields) / len(score_fields)
        max_score = max(score_fields)
        min_score = min(score_fields)

        if max_score - min_score > 60:
            warnings.append(
                f"Large score variance detected (range: {min_score}-{max_score}). "
                "Review individual category assessments."
            )

    # Check that strengths/weaknesses exist
    if not analysis.strengths:
        warnings.append("No strengths identified — analysis may be incomplete.")
    if not analysis.weaknesses:
        warnings.append("No weaknesses identified — analysis may be incomplete.")

    return warnings


def analyze_single_resume(
    file_name: str,
    file_bytes: bytes,
    job_description: str | None = None,
    provider: str = "auto",
    gateway_model: str | None = None,
) -> FullResumeAnalysis:
    """Analyze a single resume end-to-end.

    Pipeline:
    1. Process document (validate, extract/encode)
    2. Route to AI provider (Gemini Direct or Vercel AI Gateway) with auto-fallback
    3. Parse and validate structured output
    4. Calculate deterministic overall score
    5. Return assembled result

    Args:
        file_name: Original file name.
        file_bytes: Raw file content.
        job_description: Optional job description for matching.
        provider: 'auto', 'gemini', or 'gateway'.
        gateway_model: Specific model ID for Vercel AI Gateway.

    Returns:
        FullResumeAnalysis with all results and status.
    """
    # Step 1: Process document
    client = None
    try:
        client = get_client()
    except Exception:
        client = None

    doc = process_document(file_name, file_bytes, gemini_client=client)

    if not doc.is_valid:
        return FullResumeAnalysis(
            resume_analysis=_empty_analysis(doc.error or "Invalid document"),
            overall_score=0,
            file_name=file_name,
            processing_status="failed",
            error_message=doc.error,
        )

    can_use_gemini = client is not None or bool(get_gemini_api_key() or GEMINI_API_KEY)
    can_use_gateway = bool(get_ai_gateway_api_key() or AI_GATEWAY_API_KEY)

    if not can_use_gemini and not can_use_gateway:
        err_text = "Neither GEMINI_API_KEY nor AI_GATEWAY_API_KEY is configured."
        return FullResumeAnalysis(
            resume_analysis=_empty_analysis(err_text),
            overall_score=0,
            file_name=file_name,
            processing_status="failed",
            error_message=err_text + " Please set at least one in .env",
        )

    # Step 2: Route request
    raw_result = None
    provider_used = "gemini"
    model_used = GEMINI_MODEL

    # Route A: Explicit Vercel Gateway OR Auto when Gemini is not configured
    if provider == "gateway" or (provider == "auto" and not can_use_gemini and can_use_gateway):
        target_model = gateway_model or AI_GATEWAY_DEFAULT_MODEL
        try:
            raw_result = analyze_resume_gateway(doc, job_description, model=target_model)
            provider_used = "vercel_gateway"
            model_used = target_model
        except Exception as e:
            logger.warning("Vercel AI Gateway error for %s: %s", file_name, e)
            if provider == "auto" and can_use_gemini:
                try:
                    logger.info("Falling back to Gemini Direct for %s...", file_name)
                    raw_result = analyze_resume(doc, job_description, client=client)
                    provider_used = "gemini"
                    model_used = GEMINI_MODEL
                except Exception as fb_err:
                    return FullResumeAnalysis(
                        resume_analysis=_empty_analysis(f"Gateway failed: {e}; Gemini fallback: {fb_err}"),
                        overall_score=0,
                        file_name=file_name,
                        processing_status="failed",
                        error_message=f"Gateway failed: {e}. Gemini fallback failed: {fb_err}",
                    )
            else:
                return FullResumeAnalysis(
                    resume_analysis=_empty_analysis(str(e)),
                    overall_score=0,
                    file_name=file_name,
                    processing_status="failed",
                    error_message=str(e),
                    provider_used="vercel_gateway",
                    model_used=target_model,
                )

    # Route B: Gemini Direct (or Auto with Gemini configured)
    else:
        try:
            raw_result = analyze_resume(doc, job_description, client=client)
            provider_used = "gemini"
            model_used = GEMINI_MODEL
        except Exception as e:
            logger.warning("Gemini Direct failed for %s: %s", file_name, e)
            if provider == "auto" and can_use_gateway:
                try:
                    logger.info("Falling back to Vercel AI Gateway for %s...", file_name)
                    target_model = gateway_model or AI_GATEWAY_DEFAULT_MODEL
                    raw_result = analyze_resume_gateway(doc, job_description, model=target_model)
                    provider_used = "vercel_gateway"
                    model_used = target_model
                except Exception as fb_err:
                    return FullResumeAnalysis(
                        resume_analysis=_empty_analysis(f"Gemini failed: {e}; Gateway fallback: {fb_err}"),
                        overall_score=0,
                        file_name=file_name,
                        processing_status="failed",
                        error_message=f"Gemini failed: {e}. Gateway fallback failed: {fb_err}",
                    )
            else:
                return FullResumeAnalysis(
                    resume_analysis=_empty_analysis(str(e)),
                    overall_score=0,
                    file_name=file_name,
                    processing_status="failed",
                    error_message=str(e),
                    provider_used="gemini",
                    model_used=GEMINI_MODEL,
                )

    # Step 3: Parse and validate
    try:
        job_match_data = raw_result.pop("job_match", None)
        analysis = ResumeAnalysis.model_validate(raw_result)

        job_match: JobMatchAnalysis | None = None
        if job_match_data and job_description:
            try:
                job_match = JobMatchAnalysis.model_validate(job_match_data)
            except Exception as e:
                logger.warning("Failed to parse job match: %s", e)

    except Exception as e:
        logger.error("Failed to parse model output for %s: %s", file_name, e)
        return FullResumeAnalysis(
            resume_analysis=_empty_analysis(f"Failed to parse analysis: {e}"),
            overall_score=0,
            file_name=file_name,
            processing_status="failed",
            error_message=f"Output parsing failed: {e}",
            provider_used=provider_used,
            model_used=model_used,
        )

    # Step 4: Deterministic overall score
    overall_score = calculate_overall_score(analysis)

    # Step 5: Validation warnings
    validation_warnings = validate_analysis(analysis)
    if doc.warnings:
        analysis.warnings.extend(doc.warnings)
    if validation_warnings:
        analysis.warnings.extend(validation_warnings)

    return FullResumeAnalysis(
        resume_analysis=analysis,
        job_match=job_match,
        overall_score=overall_score,
        file_name=file_name,
        processing_status="success",
        provider_used=provider_used,
        model_used=model_used,
    )


def analyze_batch(
    files: list[tuple[str, bytes]],
    job_description: str | None = None,
    progress_callback=None,
    provider: str = "auto",
    gateway_model: str | None = None,
) -> RecruiterResults:
    """Analyze multiple resumes in batch.

    Processes resumes sequentially (to respect rate limits) but isolates
    failures so one bad file doesn't destroy the batch.

    Args:
        files: List of (file_name, file_bytes) tuples.
        job_description: Optional job description for matching.
        progress_callback: Optional callable(current, total, file_name, status) for UI updates.
        provider: 'auto', 'gemini', or 'gateway'.
        gateway_model: Specific model ID for Vercel AI Gateway.

    Returns:
        RecruiterResults with all analyses and comparison data.
    """
    results = RecruiterResults(
        job_description=job_description,
    )

    total = len(files)
    detailed: list[FullResumeAnalysis] = []
    failed_files: list[str] = []

    for i, (file_name, file_bytes) in enumerate(files):
        # Polite spacing between requests to respect API rate limits
        if i > 0:
            time.sleep(1)

        if progress_callback:
            progress_callback(i, total, file_name, "processing")

        result = analyze_single_resume(
            file_name,
            file_bytes,
            job_description,
            provider=provider,
            gateway_model=gateway_model,
        )
        detailed.append(result)

        if result.processing_status == "failed":
            failed_files.append(file_name)

        if progress_callback:
            progress_callback(i + 1, total, file_name, result.processing_status)

    # Build comparison table from successful analyses
    successful = [r for r in detailed if r.processing_status == "success"]

    # Sort by overall score descending
    successful.sort(key=lambda r: r.overall_score, reverse=True)

    candidates: list[CandidateSummary] = []
    for rank, result in enumerate(successful, 1):
        a = result.resume_analysis
        candidates.append(
            CandidateSummary(
                rank=rank,
                candidate_name=a.candidate_name,
                file_name=result.file_name,
                overall_score=result.overall_score,
                job_match_score=result.job_match.job_match_score if result.job_match else None,
                content_score=a.content_quality_score,
                skills_score=a.skills_relevance_score,
                experience_score=a.experience_achievements_score,
                ats_score=a.ats_compatibility_score,
                top_strengths=[s.title for s in a.strengths[:3]],
                top_weaknesses=[w.title for w in a.weaknesses[:3]],
            )
        )

    results.candidates = candidates
    results.detailed_analyses = detailed
    results.total_processed = len(successful)
    results.total_failed = len(failed_files)
    results.failed_files = failed_files

    return results


def _empty_analysis(error_msg: str) -> ResumeAnalysis:
    """Create a minimal ResumeAnalysis for error cases."""
    from app.models.resume import (
        ATSAnalysis,
        CategoryScore,
        ContactInfo,
        KeywordAnalysis,
        RecommendationItem,
        ResumeLevel,
        StrengthItem,
        VisualAnalysis,
        WeaknessItem,
    )

    return ResumeAnalysis(
        candidate_name="Unknown",
        contact=ContactInfo(),
        summary="Analysis could not be completed.",
        verdict=f"Analysis failed: {error_msg}",
        level=ResumeLevel.POOR,
        content_quality_score=0,
        experience_achievements_score=0,
        skills_relevance_score=0,
        ats_compatibility_score=0,
        structure_readability_score=0,
        impact_quantification_score=0,
        language_communication_score=0,
        visual_document_quality_score=0,
        strengths=[StrengthItem(title="N/A", detail="Analysis could not be completed.")],
        weaknesses=[WeaknessItem(title="Analysis Failed", detail=error_msg)],
        recommendations=[RecommendationItem(title="Retry", detail="Please try uploading the file again.", priority="High")],
        ats_analysis=ATSAnalysis(
            score=0,
            has_standard_sections=False,
            has_contact_info=False,
            text_extractable=False,
        ),
        visual_analysis=VisualAnalysis(score=0),
        extraction_confidence="Low",
        warnings=[error_msg],
    )
