"""Researcher Agent — extracts entities, classifies sentiment, scores news strength.

Input: Raw news headlines + market data context
Output: Structured JSON with entities, sentiment, news_strength, key_drivers
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

from src.agents.base_agent import BaseAgent
from src.config import AgentConfig
from src.data.news_feed import NewsItem

logger = structlog.get_logger(__name__)

RESEARCHER_SYSTEM_PROMPT = """You are a financial market research analyst specializing in Indian equity markets (NSE/BSE).

Your role is to analyze news headlines and market data to produce structured trading intelligence.

RULES:
- Focus only on actionable, market-moving information
- Score sentiment objectively — avoid bias toward bullish or bearish
- Consider the source reliability when scoring news strength
- Flag any potential risks or conflicting signals
- Be concise and factual — no speculation

OUTPUT FORMAT (strict JSON):
{
    "entities": [
        {
            "symbol": "RELIANCE",
            "sector": "Energy",
            "impact": "direct"  // "direct" or "indirect"
        }
    ],
    "sentiment": "BULLISH",  // "BULLISH", "BEARISH", or "NEUTRAL"
    "news_strength": 0.75,   // 0.0 to 1.0
    "key_drivers": [
        "Earnings beat expectations by 12%",
        "Volume spike confirms institutional interest"
    ],
    "catalyst_type": "earnings",  // "earnings", "regulatory", "macro", "sector", "technical", "other"
    "urgency": "HIGH",  // "HIGH", "MEDIUM", "LOW"
    "affected_sectors": ["Energy", "Refining"],
    "summary": "One-sentence summary of the analysis"
}"""


class ResearcherAgent(BaseAgent):
    """Analyzes news and market data to extract structured sentiment signals."""

    def __init__(self, config: AgentConfig) -> None:
        from src.feedback.memory_context import build_memory_context

        super().__init__(
            config,
            system_prompt=RESEARCHER_SYSTEM_PROMPT + build_memory_context(),
        )

    def analyze_news(
        self,
        news_items: List[NewsItem],
        market_context: Dict[str, Any],
        watchlist_symbols: List[str],
    ) -> Dict[str, Any]:
        """Analyze a batch of news headlines with market context.

        Args:
            news_items: Recent news headlines to analyze.
            market_context: Current market snapshot (Nifty, VIX, etc.).
            watchlist_symbols: Symbols we're actively watching.

        Returns:
            Structured analysis dict with entities, sentiment, scores.
        """
        if not news_items:
            return self._empty_result()

        prompt = self._build_prompt(news_items, market_context, watchlist_symbols)
        result = self.call(prompt, expect_json=True)

        if "error" in result:
            logger.error("researcher_failed", error=result["error"])
            return self._empty_result()

        # Validate and normalize output
        return self._validate_output(result)

    def analyze_symbol(
        self,
        symbol: str,
        news_items: List[NewsItem],
        price_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Focused analysis for a single symbol.

        Args:
            symbol: Stock symbol to analyze.
            news_items: News filtered for this symbol.
            price_data: Recent price/volume data for context.
        """
        if not news_items:
            return self._empty_result()

        headlines = "\n".join(
            f"- [{item.source}] {item.title} (reliability: {item.reliability})"
            for item in news_items[:10]
        )

        prompt = f"""Analyze these news headlines for {symbol}:

{headlines}

Price context:
- Current price: {price_data.get('close', 'N/A')}
- Day change: {price_data.get('change_pct', 'N/A')}%
- Volume ratio: {price_data.get('volume_ratio', 'N/A')}x average

Focus on: How does this news affect {symbol}? What is the directional bias?
Respond with the JSON format specified in your instructions."""

        result = self.call(prompt, expect_json=True)
        if "error" in result:
            return self._empty_result()
        return self._validate_output(result)

    def _build_prompt(
        self,
        news_items: List[NewsItem],
        market_context: Dict[str, Any],
        watchlist_symbols: List[str],
    ) -> str:
        headlines = "\n".join(
            f"- [{item.source}] {item.title} (reliability: {item.reliability})"
            for item in news_items[:15]  # Limit to 15 most recent
        )

        return f"""Analyze these recent Indian market news headlines:

{headlines}

MARKET CONTEXT:
- Nifty 50: {market_context.get('nifty_price', 'N/A')} ({market_context.get('nifty_change_pct', 'N/A')}%)
- India VIX: {market_context.get('india_vix', 'N/A')}
- Market direction: {market_context.get('market_direction', 'N/A')}

WATCHLIST: {', '.join(watchlist_symbols[:20])}

Identify which watchlist stocks are affected by this news.
Score the overall news strength and sentiment.
Respond with the JSON format specified in your instructions."""

    def _validate_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure output has all required fields with valid ranges."""
        result.setdefault("entities", [])
        result.setdefault("sentiment", "NEUTRAL")
        result.setdefault("news_strength", 0.5)
        result.setdefault("key_drivers", [])
        result.setdefault("catalyst_type", "other")
        result.setdefault("urgency", "LOW")
        result.setdefault("affected_sectors", [])
        result.setdefault("summary", "")

        # Clamp news_strength
        try:
            result["news_strength"] = max(0.0, min(1.0, float(result["news_strength"])))
        except (ValueError, TypeError):
            result["news_strength"] = 0.5

        # Normalize sentiment
        sentiment = str(result["sentiment"]).upper()
        if sentiment not in ("BULLISH", "BEARISH", "NEUTRAL"):
            result["sentiment"] = "NEUTRAL"
        else:
            result["sentiment"] = sentiment

        return result

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        return {
            "entities": [],
            "sentiment": "NEUTRAL",
            "news_strength": 0.0,
            "key_drivers": [],
            "catalyst_type": "none",
            "urgency": "LOW",
            "affected_sectors": [],
            "summary": "No news to analyze",
        }
