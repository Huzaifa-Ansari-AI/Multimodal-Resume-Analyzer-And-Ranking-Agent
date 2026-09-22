"""Pydantic schemas for structured resume analysis output.

These schemas serve two purposes:
1. Define the JSON schema sent to Gemini's structured output (`response_format`)
2. Validate and type-check the model's response before rendering in the UI
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ResumeLevel(str, Enum):
    """Qualitative assessment of resume quality."""
    EXCEPTIONAL = "Exceptional"
    STRONG = "Strong"
    GOOD = "Good"
    AVERAGE = "Average"
    NEEDS_WORK = "Needs Work"
    POOR = "Poor"


class EvidenceStatus(str, Enum):
    """Whether information was found, missing, or unclear in the resume."""
    FOUND = "Found"
    NOT_FOUND = "Not Found"
    UNCLEAR = "Unclear"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ContactInfo(BaseModel):
    """Extracted contact information."""
    name: str = Field(default="Unknown", description="Candidate's full name")
    email: Optional[str] = Field(default=None, description="Email address if found")
    phone: Optional[str] = Field(default=None, description="Phone number if found")
    location: Optional[str] = Field(default=None, description="City/region if found")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn URL if found")
    portfolio: Optional[str] = Field(default=None, description="Portfolio/website URL if found")


class EducationEntry(BaseModel):
    """A single education entry."""
    degree: str = Field(description="Degree name or certification")
    institution: str = Field(description="School or institution name")
    year: Optional[str] = Field(default=None, description="Graduation year or date range")
    details: Optional[str] = Field(default=None, description="Notable achievements, GPA, etc.")


class ExperienceEntry(BaseModel):
    """A single work experience entry."""
    title: str = Field(description="Job title or role")
    company: str = Field(description="Company or organization name")
    duration: Optional[str] = Field(default=None, description="Date range")
    highlights: list[str] = Field(default_factory=list, description="Key bullet points or achievements")


class ProjectEntry(BaseModel):
    """A single project entry."""
    name: str = Field(description="Project name")
    description: str = Field(description="Brief project description")
    technologies: list[str] = Field(default_factory=list, description="Technologies used")
    outcome: Optional[str] = Field(default=None, description="Result or impact")


class CategoryScore(BaseModel):
    """Score for a single rubric category (0-100 internal, displayed as /10)."""
    category: str = Field(description="Category name")
    score: int = Field(ge=0, le=100, description="Score out of 100")
    evidence: str = Field(description="Brief evidence justifying the score")


class StrengthItem(BaseModel):
    """A resume strength with evidence."""
    title: str = Field(description="Short strength title")
    detail: str = Field(description="Evidence-based explanation")


class WeaknessItem(BaseModel):
    """A resume weakness with evidence."""
    title: str = Field(description="Short weakness title")
    detail: str = Field(description="Evidence-based explanation")


class RecommendationItem(BaseModel):
    """An actionable improvement recommendation."""
    title: str = Field(description="Short recommendation title")
    detail: str = Field(description="Specific, actionable advice with before/after examples where helpful")
    priority: str = Field(default="Medium", description="High, Medium, or Low priority")


class ATSAnalysis(BaseModel):
    """ATS compatibility analysis."""
    score: int = Field(ge=0, le=100, description="ATS compatibility score out of 100")
    has_standard_sections: bool = Field(description="Uses standard section headings")
    has_contact_info: bool = Field(description="Contact information is ATS-readable")
    text_extractable: bool = Field(description="Text can be extracted by parsers")
    issues: list[str] = Field(default_factory=list, description="Specific ATS issues found")
    suggestions: list[str] = Field(default_factory=list, description="Improvement suggestions")


class VisualAnalysis(BaseModel):
    """Visual/document quality analysis."""
    score: int = Field(ge=0, le=100, description="Visual quality score out of 100")
    has_photo: bool = Field(default=False, description="Whether a profile photo was detected")
    layout_type: str = Field(default="Standard", description="Single column, two column, creative, etc.")
    observations: list[str] = Field(default_factory=list, description="Objective visual observations")


class KeywordAnalysis(BaseModel):
    """Keyword extraction and analysis."""
    extracted_keywords: list[str] = Field(default_factory=list, description="Key skills/technologies found")
    missing_keywords: list[str] = Field(default_factory=list, description="Common keywords that are absent (general mode)")


# ---------------------------------------------------------------------------
# Main resume analysis model
# ---------------------------------------------------------------------------

class ResumeAnalysis(BaseModel):
    """Complete structured resume analysis — the primary output schema.

    Gemini returns this as structured JSON. Application logic then computes
    the weighted overall score from category scores for deterministic scoring.
    """
    # Identity
    candidate_name: str = Field(description="Candidate's name extracted from resume")
    contact: ContactInfo = Field(default_factory=ContactInfo, description="Contact information")

    # Summary
    summary: str = Field(description="Brief professional summary extracted or inferred")
    verdict: str = Field(description="One-sentence overall assessment of the resume")
    level: ResumeLevel = Field(description="Qualitative resume level")

    # Extracted content
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list, description="All skills found")
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list, description="Human languages")

    # Category scores (0-100 each)
    content_quality_score: int = Field(ge=0, le=100)
    experience_achievements_score: int = Field(ge=0, le=100)
    skills_relevance_score: int = Field(ge=0, le=100)
    ats_compatibility_score: int = Field(ge=0, le=100)
    structure_readability_score: int = Field(ge=0, le=100)
    impact_quantification_score: int = Field(ge=0, le=100)
    language_communication_score: int = Field(ge=0, le=100)
    visual_document_quality_score: int = Field(ge=0, le=100)

    # Category evidence
    category_scores: list[CategoryScore] = Field(
        default_factory=list,
        description="Detailed scores with evidence for each category"
    )

    # Qualitative analysis
    strengths: list[StrengthItem] = Field(min_length=1, description="Top strengths (3-5)")
    weaknesses: list[WeaknessItem] = Field(min_length=1, description="Top weaknesses (3-5)")
    recommendations: list[RecommendationItem] = Field(min_length=1, description="Actionable improvements (3-5)")

    # Specialized analysis
    ats_analysis: ATSAnalysis = Field(description="ATS compatibility details")
    visual_analysis: VisualAnalysis = Field(description="Visual/document quality details")
    keywords: KeywordAnalysis = Field(default_factory=KeywordAnalysis)

    # Warnings
    extraction_confidence: str = Field(
        default="High",
        description="High, Medium, or Low — reflects document readability"
    )
    warnings: list[str] = Field(default_factory=list, description="Any processing warnings")


# ---------------------------------------------------------------------------
# Job matching models
# ---------------------------------------------------------------------------

class JobRequirement(BaseModel):
    """A single requirement from the job description."""
    requirement: str = Field(description="The requirement text")
    category: str = Field(default="General", description="Required, Preferred, or Nice-to-have")
    met: bool = Field(description="Whether the resume meets this requirement")
    evidence: str = Field(description="Resume evidence or 'Not found in resume'")


class JobMatchAnalysis(BaseModel):
    """Resume-to-job-description match analysis."""
    job_match_score: int = Field(ge=0, le=100, description="Overall job match score")
    matched_requirements: list[JobRequirement] = Field(default_factory=list)
    missing_requirements: list[JobRequirement] = Field(default_factory=list)
    relevant_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list, description="Experience items relevant to the job")
    experience_alignment: str = Field(default="", description="Brief assessment of experience fit")
    education_alignment: str = Field(default="", description="Brief assessment of education fit")
    keyword_matches: list[str] = Field(default_factory=list, description="JD keywords found in resume")
    missing_keywords: list[str] = Field(default_factory=list, description="JD keywords NOT found in resume")
    match_summary: str = Field(description="Concise paragraph summarizing the match")


# ---------------------------------------------------------------------------
# Composite models for combined analysis
# ---------------------------------------------------------------------------

class ResumeWithJobMatch(ResumeAnalysis):
    """Extended analysis schema containing both resume analysis and job match."""
    job_match: Optional[JobMatchAnalysis] = Field(
        default=None,
        description="Job match analysis (only when a job description is provided)"
    )


class FullResumeAnalysis(BaseModel):
    """Combined resume analysis + optional job match."""
    resume_analysis: ResumeAnalysis
    job_match: Optional[JobMatchAnalysis] = None
    overall_score: int = Field(ge=0, le=100, description="Weighted overall score")
    file_name: str = Field(default="", description="Original uploaded file name")
    processing_status: str = Field(default="success", description="success, failed, or partial")
    error_message: Optional[str] = Field(default=None, description="Error details if failed")


# ---------------------------------------------------------------------------
# Recruiter / comparison models
# ---------------------------------------------------------------------------

class CandidateSummary(BaseModel):
    """Compact candidate summary for comparison tables."""
    rank: int = Field(ge=1)
    candidate_name: str
    file_name: str
    overall_score: int = Field(ge=0, le=100)
    job_match_score: Optional[int] = Field(default=None, ge=0, le=100)
    content_score: int = Field(ge=0, le=100)
    skills_score: int = Field(ge=0, le=100)
    experience_score: int = Field(ge=0, le=100)
    ats_score: int = Field(ge=0, le=100)
    top_strengths: list[str] = Field(default_factory=list)
    top_weaknesses: list[str] = Field(default_factory=list)


class RecruiterResults(BaseModel):
    """Complete recruiter batch analysis results."""
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    candidates: list[CandidateSummary] = Field(default_factory=list)
    detailed_analyses: list[FullResumeAnalysis] = Field(default_factory=list)
    total_processed: int = 0
    total_failed: int = 0
    failed_files: list[str] = Field(default_factory=list)
