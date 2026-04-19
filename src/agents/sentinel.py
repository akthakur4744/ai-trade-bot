"""Sentinel Agent (Critic) — identifies counter-signals and computes risk penalty.

Input: Researcher output + market context + strategy signals
Output: Counter-arguments, conflicting signals, risk_penalty score
This is the adversarial agent — its job is to poke holes in bullish/bearish theses.
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

from src.agents.base_agent import BaseAgent
from src.config import AgentConfig

logger = structlog.get_logger(__name__)

SENTINEL_SYSTEM_PROMPT = """You are a risk-focused financial analyst who acts as a CRITIC for trading signals.

Your SOLE PURPOSE is to find reasons NOT to trade. You challenge every bullish or bearish thesis.

RULES:
- Always look for the other side of the trade
- Identify macro, sector, and stock-specific risks
- Flag conflicting signals between news and technicals
- Consider liquidity risk, event risk, and correlation risk
- Be skeptical — false positives are expensive
- Higher risk_penalty = more reasons to avoid the trade

OUTPUT FORMAT (strict JSON):
{
    "counter_arguments": [
        "Global markets are weak despite positive domestic news",
        "VIX is elevated suggesting high uncertainty"
    ],
    "conflicting_signals": [
        "Price trend is up but volume is declining",
        "Sector is weak despite stock-specific catalyst"
    ],
    "risk_factors": {
        "macro_divergence": 0.3,      // 0.0-1.0: global/domestic disconnect
        "event_risk": 0.2,            // 0.0-1.0: upcoming events that could invalidate
        "liquidity_risk": 0.1,        // 0.0-1.0: thin volume, wide spreads
        "correlation_risk": 0.1,      // 0.0-1.0: overlap with existing positions
        "signal_conflict": 0.2        // 0.0-1.0: news vs technicals disagreement
    },
    "risk_penalty": 0.35,             // 0.0-1.0: aggregate risk score
    "recommendation": "PROCEED_WITH_CAUTION",  // "PROCEED", "PROCEED_WITH_CAUTION", "REJECT"
    "summary": "One-sentence risk assessment"
}"""


class SentinelAgent(BaseAgent):
    """Adversarial agent that challenges trading theses and computes risk penalties."""

    def __init__(self, config: AgentConfig) -> None:
        super().__init__(config, system_prompt=SENTINEL_SYSTEM_PROMPT)

    def evaluate(
        self,
        researcher_output: Dict[str, Any],
        market_context: Dict[str, Any],
        strategy_signals: List[Dict[str, Any]],
        existing_positions: List[str],
    ) -> Dict[str, Any]:
        """Evaluate a trading thesis from the Researcher and find counter-arguments.

        Args:
            researcher_output: Output from ResearcherAgent.
            market_context: Current macro snapshot.
            strategy_signals: Active strategy signals for context.
            existing_positions: Symbols currently held (for correlation risk).

        Returns:
            Risk assessment with counter-arguments and risk_penalty.
        """
        prompt = self._build_prompt(
            researcher_output, market_context, strategy_signals, existing_positions
        )
        result = self.call(prompt, expect_json=True)

        if "error" in result:
            logger.error("sentinel_failed", error=result["error"])
            return self._default_high_risk()

        return self._validate_output(result)

    def _build_prompt(
        self,
        researcher_output: Dict[str, Any],
        market_context: Dict[str, Any],
        strategy_signals: List[Dict[str, Any]],
        existing_positions: List[str],
    ) -> str:
        entities = researcher_output.get("entities", [])
        entity_str = ", ".join(
            e.get("symbol", "?") for e in entities[:5]
        ) or "None identified"

        signals_str = "\n".join(
            f"- {s.get('symbol', '?')}: {s.get('direction', '?')} via {s.get('strategy', '?')} "
            f"(confidence inputs: {s.get('confidence_inputs', {})})"
            for s in strategy_signals[:5]
        ) or "No active signals"

        return f"""THESIS TO CHALLENGE:
Sentiment: {researcher_output.get('sentiment', 'N/A')}
News Strength: {researcher_output.get('news_strength', 'N/A')}
Key Drivers: {', '.join(researcher_output.get('key_drivers', []))}
Affected Entities: {entity_str}
Catalyst Type: {researcher_output.get('catalyst_type', 'N/A')}

MARKET CONTEXT:
- Nifty: {market_context.get('nifty_price', 'N/A')} ({market_context.get('nifty_change_pct', 'N/A')}%)
- VIX: {market_context.get('india_vix', 'N/A')}
- Market Direction: {market_context.get('market_direction', 'N/A')}
- Risk-Off: {market_context.get('is_risk_off', False)}

ACTIVE STRATEGY SIGNALS:
{signals_str}

EXISTING POSITIONS: {', '.join(existing_positions) or 'None'}

Find every reason this trade could fail. Challenge the thesis.
Score the risk_penalty from 0 (no risk) to 1 (maximum risk).
Respond with the JSON format specified in your instructions."""

    def _validate_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        result.setdefault("counter_arguments", [])
        result.setdefault("conflicting_signals", [])
        result.setdefault("risk_factors", {})
        result.setdefault("risk_penalty", 0.5)
        result.setdefault("recommendation", "PROCEED_WITH_CAUTION")
        result.setdefault("summary", "")

        # Clamp risk_penalty
        try:
            result["risk_penalty"] = max(0.0, min(1.0, float(result["risk_penalty"])))
        except (ValueError, TypeError):
            result["risk_penalty"] = 0.5

        # Normalize recommendation
        rec = str(result["recommendation"]).upper().replace(" ", "_")
        if rec not in ("PROCEED", "PROCEED_WITH_CAUTION", "REJECT"):
            result["recommendation"] = "PROCEED_WITH_CAUTION"
        else:
            result["recommendation"] = rec

        return result

    @staticmethod
    def _default_high_risk() -> Dict[str, Any]:
        """When the Sentinel fails, default to high risk (conservative)."""
        return {
            "counter_arguments": ["Sentinel analysis failed — defaulting to high risk"],
            "conflicting_signals": [],
            "risk_factors": {"system_error": 1.0},
            "risk_penalty": 0.8,
            "recommendation": "REJECT",
            "summary": "Analysis unavailable — blocking trade for safety",
        }
