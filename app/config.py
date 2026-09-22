"""Application configuration and constants."""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# API / Model
# ---------------------------------------------------------------------------
def get_gemini_api_key() -> str:
    """Retrieve Gemini API key from environment variables or Streamlit secrets."""
    # 1. Check environment variables (.env / system env)
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key

    # 2. Check Streamlit secrets (Streamlit Community Cloud deployment)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip().replace("\n", "").replace("\r", "")
    except Exception:
        pass

    return ""


GEMINI_API_KEY: str = get_gemini_api_key()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")

# Maximum file size for inline base64 (20 MB). Larger files use the Files API.
INLINE_SIZE_LIMIT_BYTES: int = 20 * 1024 * 1024

# ---------------------------------------------------------------------------
# Supported file types  →  (display_label, mime_type, processing_strategy)
# ---------------------------------------------------------------------------
SUPPORTED_FILE_TYPES: dict[str, tuple[str, str, str]] = {
    ".pdf":  ("PDF",  "application/pdf",  "document"),
    ".docx": ("DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    ".txt":  ("TXT",  "text/plain",  "text"),
    ".md":   ("Markdown", "text/markdown", "text"),
    ".rtf":  ("RTF",  "application/rtf", "rtf"),
    ".png":  ("PNG",  "image/png",  "image"),
    ".jpg":  ("JPEG", "image/jpeg", "image"),
    ".jpeg": ("JPEG", "image/jpeg", "image"),
    ".webp": ("WebP", "image/webp", "image"),
    ".bmp":  ("BMP",  "image/bmp",  "image"),
    ".tiff": ("TIFF", "image/tiff", "image"),
    ".tif":  ("TIFF", "image/tiff", "image"),
}

SUPPORTED_EXTENSIONS: list[str] = list(SUPPORTED_FILE_TYPES.keys())

# Human-readable list for UI
SUPPORTED_FORMATS_DISPLAY: str = "PDF · DOCX · TXT · MD · RTF · PNG · JPG · WEBP"

# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB: int = 50
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_BATCH_SIZE: int = 50  # max resumes per batch

# Temp upload directory
TEMP_UPLOAD_DIR: Path = Path("temp_uploads")

# ---------------------------------------------------------------------------
# Scoring weights  (total = 100)
# ---------------------------------------------------------------------------
SCORING_WEIGHTS: dict[str, int] = {
    "content_quality":       20,
    "experience_achievements": 20,
    "skills_relevance":      15,
    "ats_compatibility":     15,
    "structure_readability": 10,
    "impact_quantification": 10,
    "language_communication": 5,
    "visual_document_quality": 5,
}

assert sum(SCORING_WEIGHTS.values()) == 100, "Scoring weights must total 100"

# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------
PRIVACY_NOTICE: str = (
    "Your resume is processed for analysis and is not permanently stored "
    "by this application. Documents are sent to Google's Gemini API for "
    "AI-powered analysis. Temporary files are deleted after processing."
)

FAIRNESS_NOTICE: str = (
    "Candidate ranking is based on job-relevant resume evidence and should "
    "support — not replace — human review."
)
