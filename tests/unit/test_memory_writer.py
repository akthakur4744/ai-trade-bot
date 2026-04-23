"""Unit tests for MemoryWriter — append idempotency and insertion under headers.

Git calls are disabled by passing git_push=False and pointing the writer at a
temp directory with no git repo; _git_commit returns a failure that the
public API surfaces as (False, err). The file mutations we care about happen
BEFORE the git step, so we assert file state directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.feedback.memory_writer import MemoryWriter


@pytest.fixture
def memory_repo(tmp_path: Path) -> Path:
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "MISTAKES.md").write_text(
        "# Mistakes Log\n\n<!-- entries -->\n", encoding="utf-8"
    )
    (tmp_path / "memory" / "LEARNINGS.md").write_text(
        "# Learnings\n\n## Active Patterns\n\n<!-- entries -->\n", encoding="utf-8"
    )
    (tmp_path / "memory" / "TRADING-STRATEGY.md").write_text(
        "# Trading Strategy\n\n## Active Rules\n\n### R000 baseline\n", encoding="utf-8"
    )
    (tmp_path / "memory" / "WEEKLY-REVIEW.md").write_text(
        "# Weekly Review\n\n", encoding="utf-8"
    )
    return tmp_path


def _writer(repo: Path) -> MemoryWriter:
    return MemoryWriter(repo_root=repo, git_push=False)


def test_append_mistakes_is_idempotent(memory_repo: Path):
    w = _writer(memory_repo)
    draft = {
        "mistakes_entry": "## 2026-04-19 — RELIANCE — trade #42\nWhat happened: ...",
        "learnings_entry": "",
        "strategy_patch": "",
    }
    # First apply — git commit fails (no repo), but file mutation happens first.
    w.apply_postmortem(draft, trade_id=42, symbol="RELIANCE")
    content_first = (memory_repo / "memory" / "MISTAKES.md").read_text()
    assert "trade #42" in content_first

    # Second apply — dedup kicks in, file unchanged.
    w.apply_postmortem(draft, trade_id=42, symbol="RELIANCE")
    content_second = (memory_repo / "memory" / "MISTAKES.md").read_text()
    assert content_first == content_second


def test_insert_under_active_patterns_header(memory_repo: Path):
    w = _writer(memory_repo)
    draft = {
        "mistakes_entry": "## 2026-04-19 — INFY — trade #7\nBody.",
        "learnings_entry": "## L20260419-target-drift — Target overshoots on gap-ups\nBody.",
        "strategy_patch": "",
    }
    w.apply_postmortem(draft, trade_id=7, symbol="INFY")

    learnings = (memory_repo / "memory" / "LEARNINGS.md").read_text()
    header_idx = learnings.index("## Active Patterns")
    entry_idx = learnings.index("## L20260419-target-drift")
    # Entry must appear AFTER the header.
    assert entry_idx > header_idx


def test_strategy_patch_insert_idempotent(memory_repo: Path):
    w = _writer(memory_repo)
    draft = {
        "mistakes_entry": "",
        "learnings_entry": "",
        "strategy_patch": "### R001 — Drop confidence on late-day breakouts\nReason...",
    }
    w.apply_postmortem(draft, trade_id=99, symbol="TCS")
    first = (memory_repo / "memory" / "TRADING-STRATEGY.md").read_text()
    assert "R001" in first

    w.apply_postmortem(draft, trade_id=99, symbol="TCS")
    second = (memory_repo / "memory" / "TRADING-STRATEGY.md").read_text()
    assert first == second


def test_empty_draft_is_noop(memory_repo: Path):
    w = _writer(memory_repo)
    before = (memory_repo / "memory" / "MISTAKES.md").read_text()
    ok, msg = w.apply_postmortem(
        {"mistakes_entry": "", "learnings_entry": "", "strategy_patch": ""},
        trade_id=1,
        symbol="X",
    )
    after = (memory_repo / "memory" / "MISTAKES.md").read_text()
    assert before == after
    assert ok is False
    assert "no changes" in msg


def test_weekly_review_appends_dated_section(memory_repo: Path):
    w = _writer(memory_repo)
    draft = {
        "week_ending": "2026-04-17",
        "weekly_entry": "## Week ending 2026-04-17\nGrade: B+\n...",
        "learnings_entry": "",
        "strategy_patch": "",
    }
    w.apply_weekly_review(draft, week_ending="2026-04-17")
    text = (memory_repo / "memory" / "WEEKLY-REVIEW.md").read_text()
    assert "Week ending 2026-04-17" in text

    # Idempotent
    w.apply_weekly_review(draft, week_ending="2026-04-17")
    text_again = (memory_repo / "memory" / "WEEKLY-REVIEW.md").read_text()
    assert text == text_again
