"""Read-only helpers for injecting memory/*.md content into agent prompts.

Agents call build_memory_context() during __init__ and concatenate the result
to their system prompt. This is the mechanism by which approved rules in
TRADING-STRATEGY.md actually influence future scoring — without it, the
markdown just sits in git.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from src.feedback.memory_writer import DEFAULT_REPO_ROOT, MEMORY_DIR_NAME

logger = structlog.get_logger(__name__)

MEMORY_CONTEXT_HEADER = """
---

MEMORY CONTEXT (read before scoring; rules here override your priors):

Any rule in TRADING-STRATEGY.md § Active Rules is binding. If a signal contradicts an active rule, lower confidence by 0.1 and cite the rule id (e.g. R001) in `key_drivers` or `risks`. Any pattern in LEARNINGS.md § Active Patterns should reduce confidence if matched, and be referenced by its L-id.
"""


def build_memory_context(max_chars: int = 8000) -> str:
    """Read TRADING-STRATEGY.md and LEARNINGS.md and return a system-prompt suffix.

    Returns an empty string if neither file exists.
    """
    memory_dir = Path(DEFAULT_REPO_ROOT) / MEMORY_DIR_NAME
    strategy_path = memory_dir / "TRADING-STRATEGY.md"
    learnings_path = memory_dir / "LEARNINGS.md"

    sections: list[str] = []
    if strategy_path.exists():
        sections.append(f"=== TRADING-STRATEGY.md ===\n{_tail(strategy_path, max_chars // 2)}")
    if learnings_path.exists():
        sections.append(f"=== LEARNINGS.md ===\n{_tail(learnings_path, max_chars // 2)}")

    if not sections:
        return ""

    logger.info("memory_context_loaded", sections=len(sections))
    return MEMORY_CONTEXT_HEADER + "\n" + "\n\n".join(sections)


def _tail(path: Path, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8")
    return text[-max_chars:] if len(text) > max_chars else text
