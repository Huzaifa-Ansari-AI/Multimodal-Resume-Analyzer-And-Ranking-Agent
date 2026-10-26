"""Vercel AI Gateway integration service.

Provides multi-model routing, fallback resilience, and OpenAI-compatible SDK access
to models via Vercel AI Gateway (https://ai-gateway.vercel.sh/v1).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from openai import OpenAI

from app.config import (
    AI_GATEWAY_API_KEY,
    AI_GATEWAY_DEFAULT_MODEL,
    VERCEL_GATEWAY_BASE_URL,
    get_ai_gateway_api_key,
)
from app.models.resume import ResumeAnalysis, ResumeWithJobMatch
from app.prompts.analysis import SYSTEM_INSTRUCTION, build_analysis_prompt
from app.services.document_processor import ProcessedDocument

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds


class VercelGatewayServiceError(Exception):
    """Raised when a call to Vercel AI Gateway fails after retries."""
    pass


def get_gateway_client(api_key: str | None = None) -> OpenAI:
    """Create and return an OpenAI client pointing to Vercel AI Gateway.

    Raises:
        ValueError: If no gateway API key is configured.
    """
    key = api_key or get_ai_gateway_api_key() or AI_GATEWAY_API_KEY
    if not key:
        raise ValueError(
            "AI_GATEWAY_API_KEY is not set. "
            "Set it in your .env file or Streamlit secrets. "
            "Generate your key at: https://vercel.com/~/ai-gateway"
        )
    return OpenAI(
        api_key=key,
        base_url=VERCEL_GATEWAY_BASE_URL,
    )


def _build_response_schema(include_job_match: bool = False) -> dict:
    """Return JSON schema used to constrain the model output."""
    if include_job_match:
        return ResumeWithJobMatch.model_json_schema()
    return ResumeAnalysis.model_json_schema()


def build_gateway_messages(
    doc: ProcessedDocument,
    prompt_text: str,
    response_schema: dict,
) -> list[dict]:
    """Format the document and instructions into OpenAI-compatible chat messages."""
    schema_instruction = (
        "\n\nCRITICAL OUTPUT REQUIREMENT:\n"
        "You MUST respond ONLY with valid, unescaped JSON matching this schema:\n"
        f"{json.dumps(response_schema)}\n"
        "Do NOT include markdown formatting, backticks, or any explanatory text outside the JSON."
    )

    full_prompt = prompt_text + schema_instruction

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
    ]

    # Handle document types
    if doc.content_type == "text":
        user_text = (
            f"{full_prompt}\n\n"
            f"[RESUME DOCUMENT CONTENT — FILE: {doc.file_name}]\n\n"
            f"{doc.text_content}"
        )
        messages.append({"role": "user", "content": user_text})

    elif doc.content_type == "image":
        # Multimodal image input
        user_content = [
            {
                "type": "text",
                "text": f"{full_prompt}\n\n[RESUME DOCUMENT IMAGE — FILE: {doc.file_name}]",
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{doc.mime_type};base64,{doc.data_base64}"
                },
            },
        ]
        messages.append({"role": "user", "content": user_content})

    elif doc.content_type == "document":
        # Multi-page PDF or binary document
        # If text content is available, include text; otherwise provide base64 data URL
        if doc.text_content:
            user_text = (
                f"{full_prompt}\n\n"
                f"[RESUME DOCUMENT CONTENT (EXTRACTED) — FILE: {doc.file_name}]\n\n"
                f"{doc.text_content}"
            )
            messages.append({"role": "user", "content": user_text})
        else:
            # File data URL for vision-capable models supporting document inputs
            user_content = [
                {
                    "type": "text",
                    "text": f"{full_prompt}\n\n[RESUME DOCUMENT PDF — FILE: {doc.file_name}]",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{doc.mime_type};base64,{doc.data_base64}"
                    },
                },
            ]
            messages.append({"role": "user", "content": user_content})

    else:
        # Fallback text
        content_str = doc.text_content or f"[File: {doc.file_name} ({doc.content_type})]"
        messages.append({
            "role": "user",
            "content": f"{full_prompt}\n\n{content_str}",
        })

    return messages


def _extract_json(text: str) -> dict | None:
    """Safely parse JSON from raw model output or code blocks."""
    if not text:
        return None

    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try markdown json block
    for marker in ("```json\n", "```json\r\n", "```\n", "```\r\n"):
        if marker in text:
            try:
                start = text.index(marker) + len(marker)
                end = text.index("```", start)
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass

    # Try finding outer braces
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1].strip())
        except json.JSONDecodeError:
            pass

    return None


def analyze_resume_gateway(
    document: ProcessedDocument,
    job_description: str | None = None,
    model: str | None = None,
    client: OpenAI | None = None,
) -> dict:
    """Analyze a resume document through Vercel AI Gateway.

    Args:
        document: Processed document ready for input.
        job_description: Optional job description for matching.
        model: Vercel model ID (e.g. 'google/gemini-2.5-flash', 'openai/gpt-4o-mini').
        client: Pre-configured OpenAI client pointing to AI Gateway.

    Returns:
        Structured JSON dict adhering to the ResumeAnalysis schema.

    Raises:
        VercelGatewayServiceError: If the call fails after retries.
    """
    if client is None:
        client = get_gateway_client()

    target_model = model or AI_GATEWAY_DEFAULT_MODEL
    include_job_match = bool(job_description and job_description.strip())
    response_schema = _build_response_schema(include_job_match)

    prompt_text = build_analysis_prompt(job_description)
    messages = build_gateway_messages(document, prompt_text, response_schema)

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=target_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )

            if not response.choices or not response.choices[0].message:
                raise VercelGatewayServiceError("Vercel AI Gateway returned an empty response.")

            output_text = response.choices[0].message.content or ""
            parsed = _extract_json(output_text)

            if parsed is None:
                raise VercelGatewayServiceError(
                    f"Could not parse valid JSON from gateway response: {output_text[:200]}..."
                )

            return parsed

        except VercelGatewayServiceError:
            raise
        except Exception as e:
            last_error = e
            err_msg = str(e).lower()

            is_rate_limit = any(k in err_msg for k in ["rate", "quota", "429"])
            is_transient = any(k in err_msg for k in ["500", "502", "503", "504", "timeout"])

            if (is_rate_limit or is_transient) and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Vercel AI Gateway %s (attempt %d/%d). Retrying in %ds: %s",
                    "rate limit" if is_rate_limit else "transient error",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                    e,
                )
                time.sleep(delay)
                continue

            raise VercelGatewayServiceError(f"Vercel AI Gateway error: {e}") from e

    raise VercelGatewayServiceError(
        f"Vercel AI Gateway analysis failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )
