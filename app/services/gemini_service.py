"""Gemini API integration service.

Handles client initialization, multimodal document analysis, structured output
parsing, retry logic, and error handling.

Uses the current google-genai SDK (>= 2.3.0) with client.interactions.create().
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from google import genai

from app.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_MODEL
from app.models.resume import JobMatchAnalysis, ResumeAnalysis, ResumeWithJobMatch
from app.prompts.analysis import SYSTEM_INSTRUCTION, build_analysis_prompt
from app.services.document_processor import ProcessedDocument, build_gemini_input

logger = logging.getLogger(__name__)

# Maximum retries for transient failures
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


class GeminiServiceError(Exception):
    """Raised when the Gemini API call fails after retries."""
    pass


def get_client() -> genai.Client:
    """Create and return a Gemini API client.

    Raises:
        ValueError: If the API key is not configured.
    """
    api_key = GEMINI_API_KEY
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Set it in your .env file or environment variables. "
            "Get a key at: https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=api_key)


def _build_response_schema(include_job_match: bool = False) -> dict:
    """Build the JSON schema for Gemini structured output.

    We use the Pydantic model's JSON schema, which Gemini uses to constrain
    its output format.
    """
    if include_job_match:
        return ResumeWithJobMatch.model_json_schema()
    return ResumeAnalysis.model_json_schema()


def analyze_resume(
    document: ProcessedDocument,
    job_description: str | None = None,
    client: genai.Client | None = None,
) -> dict:
    """Send a processed document to Gemini for analysis.

    Args:
        document: Processed document ready for API input.
        job_description: Optional job description for matching.
        client: Optional pre-created client (for reuse in batch processing).

    Returns:
        Raw parsed JSON dict from the model's structured output.

    Raises:
        GeminiServiceError: If analysis fails after retries.
    """
    if client is None:
        client = get_client()

    # Build the multimodal input
    input_content = build_gemini_input(document)

    # Add the analysis prompt
    prompt_text = build_analysis_prompt(job_description)
    input_content.append({"type": "text", "text": prompt_text})

    # Build response format
    include_job_match = bool(job_description and job_description.strip())
    response_schema = _build_response_schema(include_job_match)

    # Model fallback support: try primary model first, fall back if quota/rate limited
    current_model = GEMINI_MODEL
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            interaction = client.interactions.create(
                model=current_model,
                input=input_content,
                system_instruction=SYSTEM_INSTRUCTION,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": response_schema,
                },
                store=False,  # Privacy: don't store interactions
            )

            # Access generated text via documented SDK convenience property
            output_text = getattr(interaction, "output_text", None)

            # Defensive fallback: inspect steps if output_text property is not populated
            if not output_text and hasattr(interaction, "steps") and interaction.steps:
                for step in reversed(interaction.steps):
                    if getattr(step, "type", None) == "model_output":
                        for c in getattr(step, "content", []):
                            if getattr(c, "text", None):
                                output_text = c.text
                                break
                    if output_text:
                        break

            if not output_text:
                raise GeminiServiceError("Model returned empty response.")

            # Parse the JSON
            try:
                result = json.loads(output_text)
                return result
            except json.JSONDecodeError as e:
                logger.warning("JSON parse error on attempt %d: %s", attempt + 1, e)
                # Try to extract JSON from the response
                result = _extract_json(output_text)
                if result:
                    return result
                raise GeminiServiceError(f"Model returned invalid JSON: {e}") from e

        except GeminiServiceError:
            raise
        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # Check for rate limiting or quota exhaustion
            is_rate_limit = any(keyword in error_str for keyword in ["rate", "quota", "429"])
            is_transient = any(keyword in error_str for keyword in ["503", "500", "unavailable", "timeout"])

            if is_rate_limit:
                # If primary model is quota/rate limited, immediately switch to fallback model
                if current_model != GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL:
                    logger.warning(
                        "Model %s rate limited, falling back to %s: %s",
                        current_model, GEMINI_FALLBACK_MODEL, e,
                    )
                    current_model = GEMINI_FALLBACK_MODEL
                    continue

                # If already on fallback model or rate limited, delay and retry
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Rate limit on attempt %d/%d, retrying in %ds: %s",
                    attempt + 1, MAX_RETRIES, delay, e,
                )
                time.sleep(delay)
                continue

            if is_transient:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Transient server error on attempt %d/%d, retrying in %ds: %s",
                    attempt + 1, MAX_RETRIES, delay, e,
                )
                time.sleep(delay)
                continue

            # Non-transient error — don't retry
            raise GeminiServiceError(f"Gemini API error: {e}") from e

    raise GeminiServiceError(
        f"Analysis failed after {MAX_RETRIES} retries. Last error: {last_error}"
    )


def _extract_json(text: str) -> dict | None:
    """Attempt to extract JSON from a response that may have extra text.

    Handles cases where the model wraps JSON in markdown code blocks.
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown
    for marker in ("```json\n", "```\n"):
        if marker in text:
            start = text.index(marker) + len(marker)
            end = text.index("```", start)
            try:
                return json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                pass

    # Try to find first { to last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None
