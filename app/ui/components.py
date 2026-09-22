"""Reusable UI components for the Resume Analyzer.

Provides score cards, progress indicators, expandable sections,
comparison tables, and other visual elements.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from app.models.resume import (
    CandidateSummary,
    FullResumeAnalysis,
    ResumeAnalysis,
    ResumeLevel,
)


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def score_color(score: int) -> str:
    """Return a CSS color based on score value (0-100)."""
    if score >= 85:
        return "#00C851"  # Green
    elif score >= 70:
        return "#33b5e5"  # Blue
    elif score >= 55:
        return "#ffbb33"  # Amber
    elif score >= 40:
        return "#ff8800"  # Orange
    else:
        return "#ff4444"  # Red


def level_emoji(level: ResumeLevel) -> str:
    """Return an emoji for a resume level."""
    return {
        ResumeLevel.EXCEPTIONAL: "🏆",
        ResumeLevel.STRONG: "💪",
        ResumeLevel.GOOD: "👍",
        ResumeLevel.AVERAGE: "📋",
        ResumeLevel.NEEDS_WORK: "🔧",
        ResumeLevel.POOR: "⚠️",
    }.get(level, "📋")


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def inject_custom_css():
    """Inject custom CSS for polished UI."""
    st.markdown("""
    <style>
    /* --- Global --- */
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }

    /* --- Score Card --- */
    .score-card {
        background: linear-gradient(135deg, #1a1d29 0%, #2d1f4e 100%);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        border: 1px solid rgba(108, 99, 255, 0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .score-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(108, 99, 255, 0.15);
    }
    .score-value {
        font-size: 2.5rem;
        font-weight: 800;
        line-height: 1;
        margin: 8px 0;
    }
    .score-label {
        font-size: 0.85rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .score-sub {
        font-size: 0.9rem;
        color: #d1d5db;
        margin-top: 4px;
    }

    /* --- Mini Score --- */
    .mini-score {
        background: rgba(108, 99, 255, 0.08);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid rgba(108, 99, 255, 0.12);
    }
    .mini-score-value {
        font-size: 1.5rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .mini-score-label {
        font-size: 0.75rem;
        color: #9ca3af;
        margin-top: 4px;
    }

    /* --- Progress Bar --- */
    .progress-container {
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
        height: 8px;
        overflow: hidden;
        margin: 6px 0;
    }
    .progress-fill {
        height: 100%;
        border-radius: 8px;
        transition: width 0.5s ease;
    }

    /* --- Badge --- */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 2px 4px;
    }
    .badge-success { background: rgba(0,200,81,0.15); color: #00C851; }
    .badge-warning { background: rgba(255,187,51,0.15); color: #ffbb33; }
    .badge-danger { background: rgba(255,68,68,0.15); color: #ff4444; }
    .badge-info { background: rgba(51,181,229,0.15); color: #33b5e5; }
    .badge-neutral { background: rgba(255,255,255,0.08); color: #d1d5db; }

    /* --- Item List --- */
    .item-card {
        background: rgba(255,255,255,0.03);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 6px 0;
        border-left: 3px solid;
    }
    .item-title {
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 4px;
    }
    .item-detail {
        font-size: 0.85rem;
        color: #9ca3af;
        line-height: 1.4;
    }

    /* --- Verdict Banner --- */
    .verdict-banner {
        background: linear-gradient(135deg, rgba(108,99,255,0.1), rgba(108,99,255,0.03));
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid rgba(108,99,255,0.15);
        font-size: 1rem;
        line-height: 1.5;
        color: #e5e7eb;
        margin: 12px 0;
    }

    /* --- Privacy Notice --- */
    .privacy-notice {
        background: rgba(255,255,255,0.03);
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 0.8rem;
        color: #6b7280;
        text-align: center;
        margin: 20px 0;
        border: 1px solid rgba(255,255,255,0.05);
    }

    /* --- Comparison Table --- */
    .comparison-header {
        background: linear-gradient(135deg, #1a1d29, #2d1f4e);
        border-radius: 12px 12px 0 0;
        padding: 16px 20px;
        border: 1px solid rgba(108,99,255,0.2);
        border-bottom: none;
    }

    /* --- Landing Hero --- */
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6C63FF, #a78bfa, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 4px;
    }
    .hero-subtitle {
        text-align: center;
        color: #9ca3af;
        font-size: 1.1rem;
        margin-bottom: 24px;
    }

    /* Hide default Streamlit header */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Score rendering
# ---------------------------------------------------------------------------

def render_main_score_card(score: int, level: ResumeLevel, label: str = "Overall Score"):
    """Render the large main score card."""
    color = score_color(score)
    emoji = level_emoji(level)
    rating = f"{score / 10:.1f}/10"

    st.markdown(f"""
    <div class="score-card">
        <div class="score-label">{label}</div>
        <div class="score-value" style="color: {color}">{score}<span style="font-size: 1.2rem; color: #6b7280">/100</span></div>
        <div class="score-sub">{emoji} {level.value} · Rating: {rating}</div>
    </div>
    """, unsafe_allow_html=True)


def render_mini_score(label: str, score: int):
    """Render a compact score card."""
    color = score_color(score)
    st.markdown(f"""
    <div class="mini-score">
        <div class="mini-score-value" style="color: {color}">{score / 10:.1f}</div>
        <div class="mini-score-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def render_progress_bar(label: str, score: int, max_val: int = 100):
    """Render a labeled progress bar."""
    pct = min(100, max(0, (score / max_val) * 100))
    color = score_color(score)
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin: 4px 0 2px 0;">
        <span style="font-size: 0.85rem; color: #d1d5db;">{label}</span>
        <span style="font-size: 0.85rem; font-weight: 600; color: {color}">{score / 10:.1f}/10</span>
    </div>
    <div class="progress-container">
        <div class="progress-fill" style="width: {pct}%; background: {color};"></div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Content rendering
# ---------------------------------------------------------------------------

def render_verdict(text: str):
    """Render the verdict banner."""
    st.markdown(f'<div class="verdict-banner">💡 {text}</div>', unsafe_allow_html=True)


def render_strength_item(title: str, detail: str):
    """Render a strength item with green accent."""
    st.markdown(f"""
    <div class="item-card" style="border-color: #00C851;">
        <div class="item-title" style="color: #00C851;">✅ {title}</div>
        <div class="item-detail">{detail}</div>
    </div>
    """, unsafe_allow_html=True)


def render_weakness_item(title: str, detail: str):
    """Render a weakness item with red accent."""
    st.markdown(f"""
    <div class="item-card" style="border-color: #ff4444;">
        <div class="item-title" style="color: #ff4444;">⚠️ {title}</div>
        <div class="item-detail">{detail}</div>
    </div>
    """, unsafe_allow_html=True)


def render_recommendation_item(title: str, detail: str, priority: str = "Medium"):
    """Render a recommendation item with blue accent."""
    priority_colors = {"High": "#ff8800", "Medium": "#33b5e5", "Low": "#6b7280"}
    color = priority_colors.get(priority, "#33b5e5")
    st.markdown(f"""
    <div class="item-card" style="border-color: {color};">
        <div class="item-title" style="color: {color};">💡 {title} <span class="badge badge-info" style="font-size:0.7rem">{priority}</span></div>
        <div class="item-detail">{detail}</div>
    </div>
    """, unsafe_allow_html=True)


def render_badge(text: str, variant: str = "neutral"):
    """Render a badge."""
    return f'<span class="badge badge-{variant}">{text}</span>'


def render_skill_badges(skills: list[str], variant: str = "info", max_display: int = 20):
    """Render skills as badges."""
    badges = "".join(render_badge(s, variant) for s in skills[:max_display])
    if len(skills) > max_display:
        badges += render_badge(f"+{len(skills) - max_display} more", "neutral")
    st.markdown(f'<div style="margin: 8px 0;">{badges}</div>', unsafe_allow_html=True)


def render_privacy_notice(text: str):
    """Render the privacy notice."""
    st.markdown(f'<div class="privacy-notice">🔒 {text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

def render_comparison_table(candidates: list[CandidateSummary], has_job_match: bool = False):
    """Render the recruiter comparison table."""
    if not candidates:
        st.info("No candidates to compare.")
        return

    # Build dataframe-like data
    import pandas as pd

    data = []
    for c in candidates:
        row = {
            "Rank": c.rank,
            "Candidate": c.candidate_name,
            "File": c.file_name,
            "Overall": c.overall_score,
        }
        if has_job_match:
            row["Job Match"] = c.job_match_score or "—"
        row.update({
            "Content": c.content_score,
            "Skills": c.skills_score,
            "Experience": c.experience_score,
            "ATS": c.ats_score,
        })
        data.append(row)

    df = pd.DataFrame(data)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rank": st.column_config.NumberColumn("🏅 Rank", width="small"),
            "Candidate": st.column_config.TextColumn("👤 Candidate"),
            "File": st.column_config.TextColumn("📄 File", width="medium"),
            "Overall": st.column_config.ProgressColumn("Overall", min_value=0, max_value=100, format="%d"),
            "Job Match": st.column_config.ProgressColumn("Job Match", min_value=0, max_value=100, format="%d") if has_job_match else None,
            "Content": st.column_config.ProgressColumn("Content", min_value=0, max_value=100, format="%d"),
            "Skills": st.column_config.ProgressColumn("Skills", min_value=0, max_value=100, format="%d"),
            "Experience": st.column_config.ProgressColumn("Experience", min_value=0, max_value=100, format="%d"),
            "ATS": st.column_config.ProgressColumn("ATS", min_value=0, max_value=100, format="%d"),
        }
    )
