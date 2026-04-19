"""Memory writer — applies approved MemoryUpdateDraft diffs to markdown files.

The ONLY code path in the repo permitted to edit `memory/*.md`. All writes are
gated behind Telegram approval (see src/notifications/telegram.py). After
appending the approved diffs, a git commit + push is performed so the updates
are durable and auditable.

Design:
- Idempotent: appending the same draft twice is a no-op (entries are keyed by
  a stable dedup marker embedded in each section).
- Append-only for MISTAKES.md and LEARNINGS.md (never rewrite past entries).
- TRADING-STRATEGY.md: insert patch under '## Active Rules' section.
- WEEKLY-REVIEW.md: append new dated section.
- Git push is best-effort — failure to push does not roll back the file write.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR_NAME = "memory"


class MemoryWriter:
    """Applies approved memory-file diffs and commits to git."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        git_push: bool = True,
    ) -> None:
        self._repo = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
        self._memory = self._repo / MEMORY_DIR_NAME
        self._git_push = git_push

    # ---- Public API ----

    def apply_postmortem(
        self,
        draft: dict,
        trade_id: int,
        symbol: str,
    ) -> tuple[bool, str]:
        """Apply an approved postmortem draft to the three target files.

        Args:
            draft: MemoryUpdateDraft.to_dict() contents.
            trade_id: Trade id (used for dedup + commit message).
            symbol: Symbol (used for commit message).

        Returns:
            (ok, commit_sha_or_error)
        """
        touched: list[Path] = []
        dedup_key = f"trade #{trade_id}"

        if draft.get("mistakes_entry"):
            path = self._append_if_new(
                self._memory / "MISTAKES.md",
                draft["mistakes_entry"].strip() + "\n",
                dedup_key,
            )
            if path:
                touched.append(path)

        if draft.get("learnings_entry"):
            entry = draft["learnings_entry"].strip() + "\n"
            # Dedup learnings on the section header (first line) so re-runs don't duplicate.
            dedup = entry.splitlines()[0] if entry.strip() else dedup_key
            path = self._insert_under_header(
                self._memory / "LEARNINGS.md",
                header="## Active Patterns",
                content=entry,
                dedup_marker=dedup,
            )
            if path:
                touched.append(path)

        if draft.get("strategy_patch"):
            patch = draft["strategy_patch"].strip() + "\n"
            dedup = patch.splitlines()[0] if patch.strip() else dedup_key
            path = self._insert_under_header(
                self._memory / "TRADING-STRATEGY.md",
                header="## Active Rules",
                content=patch,
                dedup_marker=dedup,
            )
            if path:
                touched.append(path)

        if not touched:
            return False, "no changes to apply (already up to date)"

        message = f"memory: postmortem for {symbol} (trade #{trade_id})"
        return self._git_commit(touched, message)

    def apply_weekly_review(
        self,
        draft: dict,
        week_ending: str,
    ) -> tuple[bool, str]:
        """Apply an approved weekly review draft.

        Expected keys in draft: weekly_entry, learnings_entry (opt), strategy_patch (opt).
        """
        touched: list[Path] = []
        dedup_key = f"Week ending {week_ending}"

        if draft.get("weekly_entry"):
            path = self._append_if_new(
                self._memory / "WEEKLY-REVIEW.md",
                draft["weekly_entry"].strip() + "\n",
                dedup_key,
            )
            if path:
                touched.append(path)

        if draft.get("learnings_entry"):
            entry = draft["learnings_entry"].strip() + "\n"
            dedup = entry.splitlines()[0] if entry.strip() else dedup_key
            path = self._insert_under_header(
                self._memory / "LEARNINGS.md",
                header="## Active Patterns",
                content=entry,
                dedup_marker=dedup,
            )
            if path:
                touched.append(path)

        if draft.get("strategy_patch"):
            patch = draft["strategy_patch"].strip() + "\n"
            dedup = patch.splitlines()[0] if patch.strip() else dedup_key
            path = self._insert_under_header(
                self._memory / "TRADING-STRATEGY.md",
                header="## Active Rules",
                content=patch,
                dedup_marker=dedup,
            )
            if path:
                touched.append(path)

        if not touched:
            return False, "no changes to apply (already up to date)"

        return self._git_commit(touched, f"memory: weekly review {week_ending}")

    # ---- File ops ----

    def _append_if_new(self, path: Path, content: str, dedup_marker: str) -> Optional[Path]:
        """Append content to file unless dedup_marker already present. Returns path if written."""
        if not path.exists():
            logger.warning("memory_file_missing", path=str(path))
            return None

        existing = path.read_text(encoding="utf-8")
        if dedup_marker and dedup_marker in existing:
            logger.info("memory_append_skipped_duplicate", path=path.name, marker=dedup_marker)
            return None

        # Ensure a blank line separates entries.
        separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
        path.write_text(existing + separator + content, encoding="utf-8")
        logger.info("memory_appended", path=path.name, bytes=len(content))
        return path

    def _insert_under_header(
        self,
        path: Path,
        header: str,
        content: str,
        dedup_marker: str,
    ) -> Optional[Path]:
        """Insert content right after the given `## Header` line. Idempotent on dedup_marker."""
        if not path.exists():
            logger.warning("memory_file_missing", path=str(path))
            return None

        existing = path.read_text(encoding="utf-8")
        if dedup_marker and dedup_marker in existing:
            logger.info("memory_insert_skipped_duplicate", path=path.name, marker=dedup_marker)
            return None

        lines = existing.splitlines(keepends=True)
        insert_idx: Optional[int] = None
        for i, line in enumerate(lines):
            if line.strip() == header:
                insert_idx = i + 1
                break

        if insert_idx is None:
            # Header not found — append at end.
            logger.info("memory_header_missing_appending", path=path.name, header=header)
            return self._append_if_new(path, content, dedup_marker)

        # Skip a blank line if present so new entries land cleanly.
        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1

        insertion = content if content.endswith("\n") else content + "\n"
        insertion += "\n"
        new_lines = lines[:insert_idx] + [insertion] + lines[insert_idx:]
        path.write_text("".join(new_lines), encoding="utf-8")
        logger.info("memory_inserted", path=path.name, header=header)
        return path

    # ---- Git ----

    def _git_commit(self, paths: list[Path], message: str) -> tuple[bool, str]:
        """Stage, commit, and (optionally) push the given paths."""
        try:
            rel_paths = [str(p.relative_to(self._repo)) for p in paths]
            self._run_git(["add", *rel_paths])

            # Check if anything was actually staged (may be no-op if files unchanged).
            status = self._run_git(["status", "--porcelain", "--", *rel_paths])
            if not status.strip():
                return False, "nothing staged"

            self._run_git(["commit", "-m", message])
            sha = self._run_git(["rev-parse", "HEAD"]).strip()

            if self._git_push:
                try:
                    self._run_git(["push"])
                except subprocess.CalledProcessError as e:
                    logger.warning("memory_git_push_failed", error=str(e))
                    # Don't fail the whole operation — commit is durable locally.

            logger.info("memory_committed", sha=sha[:8], message=message, files=rel_paths)
            return True, sha
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or str(e))
            logger.error("memory_git_commit_failed", error=err)
            return False, f"git error: {err}"
        except Exception as e:
            logger.error("memory_commit_unexpected_error", error=str(e))
            return False, str(e)

    def _run_git(self, args: list[str]) -> str:
        env = os.environ.copy()
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        result = subprocess.run(
            ["git", *args],
            cwd=self._repo,
            check=True,
            capture_output=True,
            env=env,
        )
        return result.stdout.decode()
