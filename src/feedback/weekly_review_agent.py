"""Weekly review agent — drafts the Friday retrospective + candidate rule changes.

Inputs:
  - memory/MISTAKES.md (this week's entries)
  - recent DailyMetric + closed trades
Outputs:
  - draft {weekly_entry, learnings_entry, strategy_patch, week_ending}
  - persisted to pending_memory_updates, Telegram approval required
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import structlog

from src.agents.base_agent import BaseAgent
from src.config import AgentConfig
from src.feedback.memory_writer import DEFAULT_REPO_ROOT, MEMORY_DIR_NAME
from src.feedback.postmortem_pipeline import EXPIRY_MINUTES, PostmortemPipeline
from src.feedback.tracker import FeedbackTracker
from src.notifications.telegram import TelegramNotifier
from src.storage.database import Database

logger = structlog.get_logger(__name__)


WEEKLY_REVIEW_SYSTEM_PROMPT = """You are a trading retrospective author for an Indian-equity AI trading bot.

You receive this week's performance stats and the accumulated MISTAKES.md entries.
Your job is to draft a Friday retrospective that a human will approve via Telegram.

OUTPUT FORMAT (strict JSON, no prose outside):
{
  "week_ending": "YYYY-MM-DD",
  "weekly_entry": "Full markdown section to append to WEEKLY-REVIEW.md. Must begin with '## Week ending <date>' and include: stats table, What worked (3-5 bullets), What didn't (3-5 bullets), Key lessons, Overall letter grade A-F.",
  "learnings_entry": "OPTIONAL full markdown section for LEARNINGS.md (only promote patterns that appeared >=2 times this week and are generalizable). Begin with '## L<YYYYMMDD-slug> — <title>'. Empty string if no promotion.",
  "strategy_patch": "OPTIONAL snippet for TRADING-STRATEGY.md § Active Rules (only when learnings_entry is populated and rule is mechanical). Cite config/default.yaml key. Empty string otherwise."
}

RULES:
- Never propose changes that bypass the risk guardrails listed in CLAUDE.md.
- Use the actual numbers. Don't editorialize without evidence.
- If the week had no trades, say so plainly and grade the process (discipline), not PnL.
"""


class WeeklyReviewAgent(BaseAgent):
    def __init__(self, config: AgentConfig) -> None:
        super().__init__(config, system_prompt=WEEKLY_REVIEW_SYSTEM_PROMPT)

    def run(
        self,
        db: Database,
        telegram: TelegramNotifier,
        writer_pipeline: PostmortemPipeline,
    ) -> Optional[int]:
        """Generate weekly draft, persist as pending_memory_update, notify Telegram.

        Returns pending_id, or None on failure.
        """
        week_ending = datetime.utcnow().strftime("%Y-%m-%d")
        stats_block = self._build_stats_block(db)
        mistakes_tail = self._read_mistakes_tail()

        user_prompt = (
            f"week_ending: {week_ending}\n\n"
            f"=== Performance stats (last 7 days) ===\n{stats_block}\n\n"
            f"=== MISTAKES.md (tail, most recent first) ===\n{mistakes_tail}\n\n"
            "Produce the JSON draft per the system prompt."
        )

        result = self.call(user_prompt, expect_json=True)
        if "error" in result or result.get("parse_error"):
            logger.warning("weekly_review_failed", result=result)
            return None

        draft = {
            "week_ending": result.get("week_ending", week_ending).strip() or week_ending,
            "weekly_entry": (result.get("weekly_entry") or "").strip(),
            "learnings_entry": (result.get("learnings_entry") or "").strip(),
            "strategy_patch": (result.get("strategy_patch") or "").strip(),
        }
        if not draft["weekly_entry"]:
            logger.warning("weekly_review_empty_entry")
            return None

        pending_id = db.save_pending_memory_update(
            source="weekly_review",
            title=f"Weekly review — week ending {draft['week_ending']}",
            draft=draft,
            expires_at=datetime.utcnow() + timedelta(minutes=EXPIRY_MINUTES),
        )
        if not pending_id:
            return None

        if telegram.is_configured:
            summary_parts = [f"[WEEKLY-REVIEW.md]\n{draft['weekly_entry'][:800]}"]
            if draft["learnings_entry"]:
                summary_parts.append(f"\n[LEARNINGS.md]\n{draft['learnings_entry'][:400]}")
            if draft["strategy_patch"]:
                summary_parts.append(f"\n[TRADING-STRATEGY.md]\n{draft['strategy_patch'][:300]}")
            msg_id = telegram.send_memory_update_for_approval(
                pending_id=pending_id,
                headline=f"Weekly review — {draft['week_ending']}",
                summary="\n".join(summary_parts),
                has_mistakes=False,
                has_learnings=bool(draft["learnings_entry"]),
                has_strategy=bool(draft["strategy_patch"]),
            )
            if msg_id:
                db.set_pending_memory_message_id(pending_id, msg_id)

        logger.info("weekly_review_enqueued", pending_id=pending_id, week=draft["week_ending"])
        return pending_id

    # ---- Helpers ----

    @staticmethod
    def _build_stats_block(db: Database) -> str:
        try:
            tracker = FeedbackTracker(db=db)
            overall = tracker.get_overall_stats()
            by_strategy = tracker.get_strategy_report()

            week_cutoff = datetime.utcnow() - timedelta(days=7)
            week_outcomes = [o for o in tracker.outcomes if o.exit_time >= week_cutoff]
            week_pnl = sum(o.pnl for o in week_outcomes)
            week_wins = sum(1 for o in week_outcomes if o.is_winner)

            lines = [
                "Overall (all time):",
                *[f"  {k}: {v}" for k, v in overall.items()],
                "",
                f"Last 7 days: trades={len(week_outcomes)}, wins={week_wins}, pnl={week_pnl:+.2f}",
                "",
                "By strategy:",
            ]
            for name, stats in by_strategy.items():
                lines.append(f"  {name}: {stats}")
            return "\n".join(lines) if lines else "(no trades yet)"
        except Exception as e:
            logger.warning("weekly_stats_build_failed", error=str(e))
            return f"(stats unavailable: {e})"

    @staticmethod
    def _read_mistakes_tail(max_chars: int = 6000) -> str:
        path = Path(DEFAULT_REPO_ROOT) / MEMORY_DIR_NAME / "MISTAKES.md"
        if not path.exists():
            return "(MISTAKES.md not found)"
        text = path.read_text(encoding="utf-8")
        return text[-max_chars:] if len(text) > max_chars else text
