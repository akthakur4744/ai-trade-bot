"""Postmortem agent — uses Claude to draft memory-file updates after a trade closes.

Flow:
  close_trade -> PostmortemAgent.draft(outcome, recurrence_hint) -> MemoryUpdateDraft
  draft is persisted to pending_memory_updates DB row
  Telegram notifies user with Approve/Reject; only on Approve do the diffs land
  in memory/MISTAKES.md (+ LEARNINGS.md, TRADING-STRATEGY.md if applicable).

No file writes happen here — this is pure analysis. memory_writer.py applies
the diffs after approval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import structlog

from src.agents.base_agent import BaseAgent
from src.config import AgentConfig
from src.feedback.tracker import TradeOutcome

logger = structlog.get_logger(__name__)


POSTMORTEM_SYSTEM_PROMPT = """You are a trading postmortem analyst for an Indian-equity AI trading bot.

You receive one closed trade (winner or loser) plus recurrence metadata. Your job
is to draft memory-file updates that a human will approve or reject via Telegram.

OUTPUT FORMAT (strict JSON, no prose outside the object):
{
  "headline": "One-line summary of what happened (< 100 chars).",
  "mistakes_entry": "Full markdown section to append to MISTAKES.md. Must begin with '## <UTC date> — <symbol> — trade #<id>' on its own line, followed by: What happened / Root cause / Proposed guard. 120-250 words.",
  "learnings_entry": "Full markdown section to append to LEARNINGS.md, OR empty string. Only populate if recurrence_count >= 2 and the pattern is generalizable. Begin with '## L<YYYYMMDD-slug> — <short title>'.",
  "strategy_patch": "Short markdown snippet to append under TRADING-STRATEGY.md § Active Rules, OR empty string. Only populate if learnings_entry was populated AND the rule is enforceable as a config threshold. Must cite the config/default.yaml key.",
  "config_suggestion": "Optional. 'scoring.min_confidence: 0.65 -> 0.70' style one-liner, OR empty string."
}

RULES:
- Every closed trade gets a mistakes_entry — winners too, if the outcome surprised the thesis.
- learnings_entry is OPTIONAL. Leave empty unless recurrence_count >= 2.
- strategy_patch is STRICTLY OPTIONAL. Leave empty unless you included a learnings_entry AND the rule is mechanical.
- Cite specific numbers (entry/exit/stop) and the strategy name.
- Do NOT suggest changes that bypass the risk guardrails in CLAUDE.md.
"""


@dataclass
class MemoryUpdateDraft:
    headline: str
    mistakes_entry: str
    learnings_entry: str
    strategy_patch: str
    config_suggestion: str

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def touches_learnings(self) -> bool:
        return bool(self.learnings_entry.strip())

    @property
    def touches_strategy(self) -> bool:
        return bool(self.strategy_patch.strip())


class PostmortemAgent(BaseAgent):
    """Drafts memory-file updates for a closed trade via Claude."""

    def __init__(self, config: AgentConfig) -> None:
        super().__init__(config, system_prompt=POSTMORTEM_SYSTEM_PROMPT)

    def draft(
        self,
        outcome: TradeOutcome,
        trade_id: int,
        recurrence_count: int = 0,
        recurrence_hint: str = "",
    ) -> Optional[MemoryUpdateDraft]:
        """Produce a drafted memory update for a single closed trade.

        Args:
            outcome: The TradeOutcome to analyze.
            trade_id: DB id of the trade (for referencing in the markdown entry).
            recurrence_count: How many similar outcomes have already been logged.
            recurrence_hint: Short description of the recurring pattern, if any.

        Returns:
            MemoryUpdateDraft on success, None on Claude failure.
        """
        user_prompt = self._build_prompt(outcome, trade_id, recurrence_count, recurrence_hint)
        result = self.call(user_prompt, expect_json=True)

        if "error" in result or result.get("parse_error"):
            logger.warning("postmortem_draft_failed", trade_id=trade_id, result=result)
            return None

        try:
            return MemoryUpdateDraft(
                headline=result.get("headline", "").strip(),
                mistakes_entry=result.get("mistakes_entry", "").strip(),
                learnings_entry=result.get("learnings_entry", "").strip(),
                strategy_patch=result.get("strategy_patch", "").strip(),
                config_suggestion=result.get("config_suggestion", "").strip(),
            )
        except Exception as e:
            logger.error("postmortem_draft_parse_error", error=str(e))
            return None

    @staticmethod
    def _build_prompt(
        outcome: TradeOutcome,
        trade_id: int,
        recurrence_count: int,
        recurrence_hint: str,
    ) -> str:
        target = f"{outcome.target_price:.2f}" if outcome.target_price else "N/A"
        rr = outcome.risk_reward_actual
        return f"""Closed trade to analyze:

- trade_id: {trade_id}
- symbol: {outcome.symbol}
- strategy: {outcome.strategy_name}
- direction: {outcome.direction}
- entry: {outcome.entry_price:.2f} on {outcome.entry_time.isoformat()}
- exit: {outcome.exit_price:.2f} on {outcome.exit_time.isoformat()}
- stop_loss: {outcome.stop_loss:.2f}
- target: {target}
- quantity: {outcome.quantity}
- pnl: {outcome.pnl:+.2f} ({outcome.pnl_pct:+.2f}%)
- exit_reason: {outcome.exit_reason}
- holding_minutes: {outcome.holding_minutes:.0f}
- risk_reward_actual: {rr}
- outcome: {"WINNER" if outcome.is_winner else "LOSER"}

Recurrence metadata:
- recurrence_count: {recurrence_count}
- recurrence_hint: {recurrence_hint or "none"}

Produce the JSON draft per the system prompt."""
