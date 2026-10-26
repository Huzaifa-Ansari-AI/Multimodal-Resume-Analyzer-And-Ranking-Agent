"""Tests for Vercel AI Gateway service."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.models.resume import ResumeAnalysis
from app.services.document_processor import ProcessedDocument
from app.services.vercel_gateway_service import (
    VercelGatewayServiceError,
    _extract_json,
    analyze_resume_gateway,
    build_gateway_messages,
    get_gateway_client,
)


class TestVercelGatewayClient:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "")
        with patch("app.services.vercel_gateway_service.get_ai_gateway_api_key", return_value=""):
            with pytest.raises(ValueError, match="AI_GATEWAY_API_KEY"):
                get_gateway_client()

    def test_get_gateway_client_configured(self):
        client = get_gateway_client(api_key="vck_test_key_12345")
        assert client is not None
        assert "ai-gateway.vercel.sh" in str(client.base_url)


class TestBuildGatewayMessages:
    def test_text_document_message(self):
        doc = ProcessedDocument(
            file_name="resume.txt",
            file_size=100,
            content_type="text",
            mime_type="text/plain",
            text_content="Candidate John Doe Experience",
        )
        schema = {"type": "object"}
        messages = build_gateway_messages(doc, "Analyze resume", schema)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Candidate John Doe Experience" in messages[1]["content"]

    def test_image_document_message(self):
        doc = ProcessedDocument(
            file_name="resume.png",
            file_size=200,
            content_type="image",
            mime_type="image/png",
            data_base64="iVBORw0KGgoAAAANSUhEUg==",
        )
        schema = {"type": "object"}
        messages = build_gateway_messages(doc, "Analyze resume", schema)

        assert len(messages) == 2
        assert isinstance(messages[1]["content"], list)
        assert any(item.get("type") == "image_url" for item in messages[1]["content"])


class TestExtractJson:
    def test_direct_json(self):
        data = {"score": 85, "name": "Alice"}
        result = _extract_json(json.dumps(data))
        assert result == data

    def test_markdown_json_block(self):
        text = "Here is the analysis:\n```json\n{\"score\": 90, \"name\": \"Bob\"}\n```\nEnjoy!"
        result = _extract_json(text)
        assert result == {"score": 90, "name": "Bob"}

    def test_bracket_detection(self):
        text = "Leading chatter... {\"score\": 75, \"name\": \"Charlie\"} ...trailing text"
        result = _extract_json(text)
        assert result == {"score": 75, "name": "Charlie"}

    def test_invalid_text_returns_none(self):
        assert _extract_json("Not a json at all") is None


class TestAnalyzeResumeGateway:
    def test_successful_call(self, mock_gemini_analysis_response):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_gemini_analysis_response)
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        doc = ProcessedDocument(
            file_name="resume.txt",
            file_size=100,
            content_type="text",
            mime_type="text/plain",
            text_content="Sample text",
        )

        result = analyze_resume_gateway(doc, client=mock_client)
        assert result["candidate_name"] == "John Doe"
        assert result["content_quality_score"] == 82

    def test_gateway_error_raised(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Gateway unreachable")

        doc = ProcessedDocument(
            file_name="resume.txt",
            file_size=100,
            content_type="text",
            mime_type="text/plain",
            text_content="Sample text",
        )

        with pytest.raises(VercelGatewayServiceError, match="Vercel AI Gateway error"):
            analyze_resume_gateway(doc, client=mock_client)
