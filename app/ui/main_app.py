"""Multimodal Resume Analyzer & Recruiter Ranking Agent — Streamlit App.

Entry point: streamlit run app/ui/main_app.py

Provides two modes:
1. Resume Analysis — single resume quality analysis with optional job matching
2. Compare Resumes — multi-resume recruiter mode with ranking and filtering
"""

from __future__ import annotations

import os
import sys

# Add project root to path so imports work when running via streamlit
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import streamlit as st
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

from app.config import (
    FAIRNESS_NOTICE,
    MAX_BATCH_SIZE,
    PRIVACY_NOTICE,
    SCORING_WEIGHTS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_FORMATS_DISPLAY,
)
from app.models.resume import FullResumeAnalysis, ResumeLevel
from app.services.job_matcher import get_match_reasons, has_job_match
from app.services.ranking import (
    SORT_OPTIONS,
    export_to_csv,
    export_to_json,
    filter_candidates,
    sort_candidates,
)
from app.services.resume_analyzer import analyze_batch, analyze_single_resume
from app.ui.components import (
    inject_custom_css,
    render_badge,
    render_comparison_table,
    render_main_score_card,
    render_mini_score,
    render_privacy_notice,
    render_progress_bar,
    render_recommendation_item,
    render_skill_badges,
    render_strength_item,
    render_verdict,
    render_weakness_item,
    score_color,
)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Resume Analyzer AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_custom_css()


# ---------------------------------------------------------------------------
# Landing / Hero
# ---------------------------------------------------------------------------

def render_landing():
    """Render the landing page hero."""
    st.markdown("""
    <div style="padding: 40px 0 20px 0;">
        <div class="hero-title">📄 Resume Analyzer AI</div>
        <div class="hero-subtitle">Analyze · Improve · Compare</div>
        <p style="text-align: center; color: #6b7280; max-width: 600px; margin: 0 auto;">
            Upload your resume and get an AI-powered, evidence-based analysis in seconds.
            Supports multimodal document understanding — PDFs, images, DOCX, and more.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <p style="text-align: center; color: #6b7280; font-size: 0.85rem; margin: 16px 0 8px 0;">
        Supported formats: {SUPPORTED_FORMATS_DISPLAY}
    </p>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Single resume analysis results
# ---------------------------------------------------------------------------

def render_single_result(result: FullResumeAnalysis):
    """Render the complete analysis for a single resume."""
    a = result.resume_analysis

    # Warnings
    if a.extraction_confidence == "Low":
        st.warning(
            "⚠️ Low-confidence document extraction detected. "
            "Some resume details may be incomplete.",
            icon="⚠️",
        )
    if a.warnings:
        for w in a.warnings[:3]:
            st.warning(w, icon="⚠️")

    # -- Top section: Score + Verdict --
    st.markdown("---")
    st.markdown(f"### 📋 Resume Analysis — {a.candidate_name}")

    col1, col2 = st.columns([1, 2])

    with col1:
        render_main_score_card(result.overall_score, a.level)

    with col2:
        render_verdict(a.verdict)

        # Quick stats row
        cols = st.columns(4)
        score_pairs = [
            ("ATS", a.ats_compatibility_score),
            ("Content", a.content_quality_score),
            ("Structure", a.structure_readability_score),
            ("Impact", a.impact_quantification_score),
        ]
        for col, (label, score) in zip(cols, score_pairs):
            with col:
                render_mini_score(label, score)

    # Job match card (if applicable)
    if result.job_match:
        st.markdown("---")
        jm = result.job_match
        jcol1, jcol2 = st.columns([1, 2])
        with jcol1:
            from app.models.resume import ResumeLevel as RL
            jm_level = (
                RL.EXCEPTIONAL if jm.job_match_score >= 90
                else RL.STRONG if jm.job_match_score >= 75
                else RL.GOOD if jm.job_match_score >= 60
                else RL.AVERAGE if jm.job_match_score >= 45
                else RL.NEEDS_WORK
            )
            render_main_score_card(jm.job_match_score, jm_level, label="Job Match Score")
        with jcol2:
            render_verdict(jm.match_summary)
            positives, negatives = get_match_reasons(jm)
            for p in positives[:3]:
                st.markdown(f'<span style="color: #00C851; font-size: 0.9rem;">{p}</span>', unsafe_allow_html=True)
            for n in negatives[:3]:
                st.markdown(f'<span style="color: #ff4444; font-size: 0.9rem;">{n}</span>', unsafe_allow_html=True)

    # -- Top 3s --
    st.markdown("---")
    col_s, col_w, col_r = st.columns(3)

    with col_s:
        st.markdown("#### ✅ Top Strengths")
        for item in a.strengths[:3]:
            render_strength_item(item.title, item.detail)

    with col_w:
        st.markdown("#### ⚠️ Top Weaknesses")
        for item in a.weaknesses[:3]:
            render_weakness_item(item.title, item.detail)

    with col_r:
        st.markdown("#### 💡 Top Improvements")
        for item in a.recommendations[:3]:
            render_recommendation_item(item.title, item.detail, item.priority)

    # -- Detailed scores --
    st.markdown("---")
    st.markdown("#### 📊 Category Scores")

    score_data = [
        ("Content Quality", a.content_quality_score, 20),
        ("Experience & Achievements", a.experience_achievements_score, 20),
        ("Skills Relevance", a.skills_relevance_score, 15),
        ("ATS Compatibility", a.ats_compatibility_score, 15),
        ("Structure & Readability", a.structure_readability_score, 10),
        ("Impact & Quantification", a.impact_quantification_score, 10),
        ("Language & Communication", a.language_communication_score, 5),
        ("Visual/Document Quality", a.visual_document_quality_score, 5),
    ]

    for label, score, weight in score_data:
        render_progress_bar(f"{label} (weight: {weight}%)", score)

    # -- Expandable detailed sections --
    st.markdown("---")
    st.markdown("#### 📑 Detailed Analysis")

    # ATS Analysis
    with st.expander("🤖 ATS Compatibility Analysis"):
        ats = a.ats_analysis
        st.markdown(f"**ATS Score:** {ats.score / 10:.1f}/10")

        status_items = [
            ("Standard Sections", ats.has_standard_sections),
            ("Contact Info Readable", ats.has_contact_info),
            ("Text Extractable", ats.text_extractable),
        ]
        for label, status in status_items:
            icon = "✅" if status else "❌"
            st.markdown(f"- {icon} {label}")

        if ats.issues:
            st.markdown("**Issues:**")
            for issue in ats.issues:
                st.markdown(f"- ⚠️ {issue}")

        if ats.suggestions:
            st.markdown("**Suggestions:**")
            for sug in ats.suggestions:
                st.markdown(f"- 💡 {sug}")

    # Visual Analysis
    with st.expander("🎨 Visual / Document Analysis"):
        vis = a.visual_analysis
        st.markdown(f"**Visual Score:** {vis.score / 10:.1f}/10")
        st.markdown(f"**Layout:** {vis.layout_type}")

        if vis.has_photo:
            st.info("📸 Profile photo detected. Photo is treated as a layout element and is NOT used for scoring.")

        if vis.observations:
            for obs in vis.observations:
                st.markdown(f"- {obs}")

    # Skills
    with st.expander("🛠️ Skills & Keywords"):
        if a.skills:
            st.markdown("**Skills Found:**")
            render_skill_badges(a.skills)

        if a.keywords.extracted_keywords:
            st.markdown("**Key Terms:**")
            render_skill_badges(a.keywords.extracted_keywords, variant="neutral")

        if a.keywords.missing_keywords:
            st.markdown("**Potentially Missing Keywords:**")
            render_skill_badges(a.keywords.missing_keywords, variant="warning")

    # Experience
    if a.experience:
        with st.expander("💼 Experience"):
            for exp in a.experience:
                st.markdown(f"**{exp.title}** at *{exp.company}*")
                if exp.duration:
                    st.caption(exp.duration)
                for h in exp.highlights:
                    st.markdown(f"  - {h}")

    # Education
    if a.education:
        with st.expander("🎓 Education"):
            for edu in a.education:
                st.markdown(f"**{edu.degree}** — {edu.institution}")
                if edu.year:
                    st.caption(edu.year)
                if edu.details:
                    st.markdown(f"  {edu.details}")

    # Projects
    if a.projects:
        with st.expander("🚀 Projects"):
            for proj in a.projects:
                st.markdown(f"**{proj.name}**")
                st.markdown(proj.description)
                if proj.technologies:
                    render_skill_badges(proj.technologies, variant="info")
                if proj.outcome:
                    st.markdown(f"*Outcome:* {proj.outcome}")

    # Certifications
    if a.certifications:
        with st.expander("📜 Certifications"):
            for cert in a.certifications:
                st.markdown(f"- {cert}")

    # Job Match Details
    if result.job_match:
        with st.expander("🎯 Job Match Details"):
            jm = result.job_match

            if jm.relevant_skills:
                st.markdown("**Matching Skills:**")
                render_skill_badges(jm.relevant_skills, variant="success")

            if jm.missing_skills:
                st.markdown("**Missing Skills:**")
                render_skill_badges(jm.missing_skills, variant="danger")

            if jm.keyword_matches:
                st.markdown("**Keyword Matches:**")
                render_skill_badges(jm.keyword_matches, variant="info")

            if jm.missing_keywords:
                st.markdown("**Missing Keywords:**")
                render_skill_badges(jm.missing_keywords, variant="warning")

            st.markdown(f"**Experience Alignment:** {jm.experience_alignment}")
            st.markdown(f"**Education Alignment:** {jm.education_alignment}")

            if jm.matched_requirements:
                st.markdown("**Met Requirements:**")
                for req in jm.matched_requirements:
                    st.markdown(f"- ✅ **{req.requirement}** ({req.category}) — {req.evidence}")

            if jm.missing_requirements:
                st.markdown("**Unmet Requirements:**")
                for req in jm.missing_requirements:
                    st.markdown(f"- ❌ **{req.requirement}** ({req.category}) — {req.evidence}")

    # All recommendations
    with st.expander("📝 All Recommendations"):
        for item in a.recommendations:
            render_recommendation_item(item.title, item.detail, item.priority)

    # -- Final Summary Card --
    st.markdown("---")
    st.markdown("#### 🏁 Final Summary")

    summary_cols = st.columns([1, 2])
    with summary_cols[0]:
        render_main_score_card(result.overall_score, a.level, "Final Score")
    with summary_cols[1]:
        # Summary table
        import pandas as pd

        summary_data = {
            "Category": [
                "Content Quality", "Experience & Achievements", "Skills Relevance",
                "ATS Compatibility", "Structure & Readability", "Impact & Quantification",
                "Language", "Visual Quality", "**Overall**",
            ],
            "Score": [
                f"{a.content_quality_score / 10:.1f}/10",
                f"{a.experience_achievements_score / 10:.1f}/10",
                f"{a.skills_relevance_score / 10:.1f}/10",
                f"{a.ats_compatibility_score / 10:.1f}/10",
                f"{a.structure_readability_score / 10:.1f}/10",
                f"{a.impact_quantification_score / 10:.1f}/10",
                f"{a.language_communication_score / 10:.1f}/10",
                f"{a.visual_document_quality_score / 10:.1f}/10",
                f"**{result.overall_score / 10:.1f}/10**",
            ],
        }
        st.table(summary_data)

        st.markdown("**Top 3 Actions:**")
        for i, rec in enumerate(a.recommendations[:3], 1):
            st.markdown(f"{i}. {rec.title}")


# ---------------------------------------------------------------------------
# Recruiter mode results
# ---------------------------------------------------------------------------

def render_recruiter_results(results):
    """Render batch comparison results."""
    from app.models.resume import RecruiterResults

    st.markdown("---")
    st.markdown("### 👥 Candidate Comparison")

    # Status summary
    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Analyzed", results.total_processed)
    col2.metric("❌ Failed", results.total_failed)
    col3.metric("📊 Total", results.total_processed + results.total_failed)

    if results.failed_files:
        with st.expander("❌ Failed Files"):
            for f in results.failed_files:
                st.markdown(f"- {f}")
            # Show error details
            for d in results.detailed_analyses:
                if d.processing_status == "failed":
                    st.markdown(f"  **{d.file_name}:** {d.error_message}")

    if not results.candidates:
        st.warning("No resumes were successfully analyzed.")
        return

    # Fairness notice
    st.info(f"ℹ️ {FAIRNESS_NOTICE}")

    # Filters and sorting
    has_jm = any(c.job_match_score is not None for c in results.candidates)

    with st.expander("🔧 Filters & Sorting", expanded=True):
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)

        with fcol1:
            sort_by = st.selectbox("Sort by", list(SORT_OPTIONS.keys()), index=0)
        with fcol2:
            min_overall = st.slider("Min Overall Score", 0, 100, 0, 5)
        with fcol3:
            min_ats = st.slider("Min ATS Score", 0, 100, 0, 5)
        with fcol4:
            min_jm = 0
            if has_jm:
                min_jm = st.slider("Min Job Match", 0, 100, 0, 5)

    # Apply filters
    filtered = filter_candidates(
        results.candidates,
        min_overall=min_overall,
        min_job_match=min_jm,
        min_ats=min_ats,
        detailed_analyses=results.detailed_analyses,
    )

    # Apply sorting
    sorted_candidates = sort_candidates(filtered, sort_by=sort_by)

    st.markdown(f"**Showing {len(sorted_candidates)} of {len(results.candidates)} candidates**")

    # Comparison table
    render_comparison_table(sorted_candidates, has_job_match=has_jm)

    # Export buttons
    ecol1, ecol2 = st.columns(2)
    with ecol1:
        csv_data = export_to_csv(results)
        st.download_button(
            "📥 Export CSV",
            csv_data,
            "resume_comparison.csv",
            "text/csv",
        )
    with ecol2:
        json_data = export_to_json(results)
        st.download_button(
            "📥 Export JSON",
            json_data,
            "resume_comparison.json",
            "application/json",
        )

    # Candidate detail cards
    st.markdown("---")
    st.markdown("### 📋 Candidate Details")

    for candidate in sorted_candidates:
        # Find matching detailed analysis
        detail = next(
            (d for d in results.detailed_analyses if d.file_name == candidate.file_name),
            None,
        )
        if not detail or detail.processing_status != "success":
            continue

        with st.expander(
            f"#{candidate.rank} {candidate.candidate_name} — "
            f"Overall: {candidate.overall_score}/100"
            + (f" · Job Match: {candidate.job_match_score}/100" if candidate.job_match_score else ""),
        ):
            render_single_result(detail)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    render_landing()

    # Mode selection
    mode = st.radio(
        "Choose mode:",
        ["👤 Analyze Resume", "👥 Compare Resumes (Recruiter Mode)"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("")

    # Optional job description
    with st.expander("🎯 Add Job Description (optional)"):
        job_description = st.text_area(
            "Paste the job description here",
            height=200,
            placeholder="Paste the full job description to enable job-match analysis...",
            help="When provided, the analyzer will score how well each resume matches the job requirements.",
        )
        if job_description:
            st.success("Job description loaded. Resumes will be matched against it.")

    job_desc = job_description.strip() if job_description and job_description.strip() else None

    st.markdown("---")

    # -----------------------------------------------------------------------
    # MODE: Single Resume Analysis
    # -----------------------------------------------------------------------
    if mode == "👤 Analyze Resume":
        uploaded_file = st.file_uploader(
            "Upload your resume",
            type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
            accept_multiple_files=False,
            help=f"Supported formats: {SUPPORTED_FORMATS_DISPLAY}",
        )

        if uploaded_file:
            st.markdown(f"**File:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

            if st.button("🔍 Analyze Resume", type="primary", use_container_width=True):
                file_bytes = uploaded_file.read()

                # Progress
                with st.status("Analyzing resume...", expanded=True) as status:
                    st.write("📂 File received")
                    st.write(f"📄 Document type: {uploaded_file.type or 'auto-detect'}")
                    st.write("🔍 Analyzing document with AI...")

                    result = analyze_single_resume(
                        uploaded_file.name, file_bytes, job_desc
                    )

                    if result.processing_status == "success":
                        st.write("✅ Analysis complete")
                        status.update(label="Analysis complete!", state="complete")
                    else:
                        st.write(f"❌ Analysis failed: {result.error_message}")
                        status.update(label="Analysis failed", state="error")

                if result.processing_status == "success":
                    render_single_result(result)
                else:
                    st.error(f"❌ {result.error_message}")

    # -----------------------------------------------------------------------
    # MODE: Recruiter / Multi-Resume Comparison
    # -----------------------------------------------------------------------
    elif mode == "👥 Compare Resumes (Recruiter Mode)":
        uploaded_files = st.file_uploader(
            "Upload multiple resumes",
            type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
            accept_multiple_files=True,
            help=f"Upload up to {MAX_BATCH_SIZE} resumes. Supported: {SUPPORTED_FORMATS_DISPLAY}",
        )

        if uploaded_files:
            if len(uploaded_files) > MAX_BATCH_SIZE:
                st.error(f"Maximum {MAX_BATCH_SIZE} files per batch. You uploaded {len(uploaded_files)}.")
            else:
                st.markdown(f"**Files:** {len(uploaded_files)} resumes ready")
                for f in uploaded_files:
                    st.caption(f"  📄 {f.name} ({f.size / 1024:.1f} KB)")

                if st.button("🔍 Analyze All Resumes", type="primary", use_container_width=True):
                    # Read all files
                    files = [(f.name, f.read()) for f in uploaded_files]

                    # Progress tracking
                    progress_bar = st.progress(0, text="Starting batch analysis...")
                    status_text = st.empty()

                    def progress_callback(current, total, file_name, status):
                        pct = current / total if total > 0 else 0
                        status_icon = "✅" if status == "success" else "❌" if status == "failed" else "⏳"
                        progress_bar.progress(pct, text=f"{status_icon} {file_name} ({current}/{total})")
                        status_text.text(f"Processing: {file_name}...")

                    results = analyze_batch(files, job_desc, progress_callback)

                    progress_bar.progress(1.0, text="Batch analysis complete!")
                    status_text.empty()

                    render_recruiter_results(results)

    # Privacy notice
    st.markdown("---")
    render_privacy_notice(PRIVACY_NOTICE)


if __name__ == "__main__":
    main()
