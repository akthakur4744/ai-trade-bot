"""Base agent — shared Claude API client, prompt construction, JSON parsing, retry logic."""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Dict, Optional

import anthropic
import structlog

from src.config import AgentConfig

logger = structlog.get_logger(__name__)


class BaseAgent:
    """Shared infrastructure for all AI agents.

    Handles:
    - Claude API client initialization
    - Prompt template construction
    - Structured JSON output parsing
    - Retry with exponential backoff
    - Token usage tracking
    """

    def __init__(self, config: AgentConfig, system_prompt: str = "") -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        self._client = anthropic.Anthropic(api_key=api_key)
        self._config = config
        self._system_prompt = system_prompt
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._call_count = 0

    @property
    def usage_stats(self) -> Dict[str, int]:
        return {
            "calls": self._call_count,
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
        }

    def call(self, user_prompt: str, expect_json: bool = True) -> Dict[str, Any]:
        """Call Claude API with retry logic and return parsed response.

        Args:
            user_prompt: The user message content.
            expect_json: If True, parse response as JSON. If False, return {"text": response}.

        Returns:
            Parsed JSON dict or {"text": raw_response}.
        """
        last_error = None

        for attempt in range(self._config.max_retries):
            try:
                response = self._client.messages.create(
                    model=self._config.model,
                    max_tokens=self._config.max_tokens,
                    system=self._system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                # Track usage
                self._call_count += 1
                self._total_input_tokens += response.usage.input_tokens
                self._total_output_tokens += response.usage.output_tokens

                raw_text = response.content[0].text.strip()

                if expect_json:
                    return self._parse_json(raw_text)
                return {"text": raw_text}

            except anthropic.RateLimitError:
                wait = 2 ** (attempt + 1) + random.uniform(0, 1)
                logger.warning("agent_rate_limited", attempt=attempt, wait=round(wait, 1))
                time.sleep(wait)
                last_error = "Rate limited"

            except anthropic.APIError as e:
                is_overloaded = getattr(e, "status_code", 0) == 529
                base = 2 ** (attempt + 2) if is_overloaded else 2 ** attempt
                wait = base + random.uniform(0, 2)
                logger.warning(
                    "agent_api_error",
                    attempt=attempt,
                    error=str(e),
                    wait=round(wait, 1),
                    overloaded=is_overloaded,
                )
                time.sleep(wait)
                last_error = str(e)

            except Exception as e:
                logger.error("agent_unexpected_error", error=str(e))
                last_error = str(e)
                break

        logger.error("agent_all_retries_failed", error=last_error)
        return {"error": last_error or "Unknown error"}

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from Claude's response.

        Handles common patterns:
        - Pure JSON response
        - JSON wrapped in markdown code blocks
        - JSON embedded in explanatory text
        """
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from code block
        if "```" in text:
            blocks = text.split("```")
            for block in blocks:
                cleaned = block.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    continue

        # Try finding JSON object in text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning("agent_json_parse_failed", text_preview=text[:200])
        return {"text": text, "parse_error": True}
