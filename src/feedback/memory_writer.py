"""Memory writer — applies approved MemoryUpdateDraft diffs to markdown files
and opens a GitHub PR.

The ONLY code path in the repo permitted to edit `memory/*.md`. All writes are
gated behind Telegram approval (see src/notifications/telegram.py). On approve:

  1. Fetch `origin/main` and create a fresh branch.
  2. Apply the draft's diffs to the relevant memory files.
  3. Commit + push the branch using `GITHUB_TOKEN`.
  4. Open a PR against `main` via the GitHub REST API.
  5. Return the PR URL to the caller, which stores it in
     `pending_memory_updates.commit_sha` and sends it back to the user via
     Telegram.

Design:
- The user merges (or closes) the PR on GitHub — no auto-merge. This gives a
  full audit trail + rollback before memory changes actually land on `main`.
- Idempotent: appending the same draft twice is a no-op (entries are keyed by
  a stable dedup marker embedded in each section).
- Append-only for MISTAKES.md and LEARNINGS.md.
- TRADING-STRATEGY.md: insert patch under '## Active Rules' section.
- WEEKLY-REVIEW.md: append new dated section.

Environment:
- `GITHUB_TOKEN`: PAT or fine-grained token with `contents:write` +
  `pull_requests:write` on the repo. Required.
- `GITHUB_REPO` (optional): `owner/name`. If unset, parsed from the
  `origin` remote.
- `MEMORY_PR_BASE` (optional): base branch for PRs, defaults to `main`.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger(__name__)


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR_NAME = "memory"
_GITHUB_API = "https://api.github.com"
_HTTP_TIMEOUT = 15.0


class MemoryWriter:
    """Applies approved memory-file diffs and opens a GitHub PR."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        github_token: Optional[str] = None,
        github_repo: Optional[str] = None,
        base_branch: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self._repo = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
        self._memory = self._repo / MEMORY_DIR_NAME
        self._token = github_token or os.getenv("GITHUB_TOKEN", "")
        self._github_repo = github_repo or os.getenv("GITHUB_REPO", "")
        self._base_branch = base_branch or os.getenv("MEMORY_PR_BASE", "main")
        # dry_run: apply file mutations in-place on the current working tree
        # and skip all git + GitHub operations. Used by unit tests.
        self._dry_run = dry_run

    # ---- Public API ----

    def apply_postmortem(
        self,
        draft: dict,
        trade_id: int,
        symbol: str,
    ) -> tuple[bool, str]:
        """Apply an approved postmortem draft to the three target files.

        Returns:
            (ok, pr_url_or_error)
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        branch = f"memory/postmortem-{trade_id}-{ts}"

        if not self._dry_run:
            ok, err = self._prepare_branch(branch)
            if not ok:
                return False, err

        touched = self._apply_postmortem_edits(draft, trade_id)
        if not touched:
            return False, "no changes to apply (already up to date)"
        if self._dry_run:
            return False, "dry_run"

        commit_msg = f"memory: postmortem for {symbol} (trade #{trade_id})"
        pr_title = f"Memory update: {symbol} postmortem (trade #{trade_id})"
        pr_body = _build_pr_body(
            draft, context=f"Postmortem for trade #{trade_id} ({symbol})."
        )
        return self._commit_push_and_open_pr(
            branch=branch,
            paths=touched,
            commit_msg=commit_msg,
            pr_title=pr_title,
            pr_body=pr_body,
        )

    def apply_weekly_review(
        self,
        draft: dict,
        week_ending: str,
    ) -> tuple[bool, str]:
        """Apply an approved weekly review draft. Returns (ok, pr_url_or_error)."""
        safe_week = re.sub(r"[^0-9A-Za-z_-]", "-", week_ending)
        branch = f"memory/weekly-{safe_week}"

        if not self._dry_run:
            ok, err = self._prepare_branch(branch)
            if not ok:
                return False, err

        touched = self._apply_weekly_edits(draft, week_ending)
        if not touched:
            return False, "no changes to apply (already up to date)"
        if self._dry_run:
            return False, "dry_run"

        commit_msg = f"memory: weekly review {week_ending}"
        pr_title = f"Memory update: weekly review ({week_ending})"
        pr_body = _build_pr_body(
            draft, context=f"Weekly review for week ending {week_ending}."
        )
        return self._commit_push_and_open_pr(
            branch=branch,
            paths=touched,
            commit_msg=commit_msg,
            pr_title=pr_title,
            pr_body=pr_body,
        )

    # ---- Edit composition ----

    def _apply_postmortem_edits(self, draft: dict, trade_id: int) -> list[Path]:
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

        return touched

    def _apply_weekly_edits(self, draft: dict, week_ending: str) -> list[Path]:
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

        return touched

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
            logger.info("memory_header_missing_appending", path=path.name, header=header)
            return self._append_if_new(path, content, dedup_marker)

        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1

        insertion = content if content.endswith("\n") else content + "\n"
        insertion += "\n"
        new_lines = lines[:insert_idx] + [insertion] + lines[insert_idx:]
        path.write_text("".join(new_lines), encoding="utf-8")
        logger.info("memory_inserted", path=path.name, header=header)
        return path

    # ---- Git + PR ----

    def _prepare_branch(self, branch: str) -> tuple[bool, str]:
        """Fetch origin/main and create/checkout `branch` off it.

        Modifies the working tree — only safe in ephemeral Routine sandboxes
        or a dedicated worktree. If the branch already exists (local or
        remote), we still point it at the latest `origin/<base>` to avoid
        carrying stale state from a previous run.
        """
        if not self._token:
            return False, "GITHUB_TOKEN not set"
        if not self._resolve_repo_slug():
            return False, "cannot resolve GitHub repo (set GITHUB_REPO or configure origin remote)"

        try:
            self._run_git(["fetch", "origin", self._base_branch])
            # Create-or-reset the branch from origin/<base>.
            self._run_git(["checkout", "-B", branch, f"origin/{self._base_branch}"])
            return True, ""
        except subprocess.CalledProcessError as e:
            err = _decode_stderr(e)
            logger.error("memory_prepare_branch_failed", error=err)
            return False, f"git checkout failed: {err}"

    def _commit_push_and_open_pr(
        self,
        branch: str,
        paths: list[Path],
        commit_msg: str,
        pr_title: str,
        pr_body: str,
    ) -> tuple[bool, str]:
        try:
            rel_paths = [str(p.relative_to(self._repo)) for p in paths]
            self._run_git(["add", *rel_paths])

            status = self._run_git(["status", "--porcelain", "--", *rel_paths])
            if not status.strip():
                return False, "nothing staged"

            self._run_git([
                "-c", "user.name=insight-alpha-bot",
                "-c", "user.email=memory@insight-alpha.local",
                "commit", "-m", commit_msg,
            ])
            sha = self._run_git(["rev-parse", "HEAD"]).strip()
        except subprocess.CalledProcessError as e:
            err = _decode_stderr(e)
            logger.error("memory_commit_failed", error=err)
            return False, f"git error: {err}"

        push_ok, push_err = self._push_with_token(branch)
        if not push_ok:
            return False, push_err

        pr_url, pr_err = self._open_pr(
            head=branch, title=pr_title, body=pr_body
        )
        if not pr_url:
            return False, pr_err

        logger.info(
            "memory_pr_opened",
            pr_url=pr_url,
            branch=branch,
            sha=sha[:8],
            files=rel_paths,
        )
        return True, pr_url

    def _push_with_token(self, branch: str) -> tuple[bool, str]:
        """Push `branch` to origin using an ephemeral tokenized URL.

        We use --force-with-lease in case a previous attempt left a stale
        remote branch behind (dedup cases where the user rejected then
        re-approved a similar draft).
        """
        slug = self._resolve_repo_slug()
        assert slug, "resolve_repo_slug must succeed before push"
        remote_url = f"https://x-access-token:{self._token}@github.com/{slug}.git"
        try:
            self._run_git([
                "push", remote_url, f"{branch}:{branch}", "--force-with-lease",
            ])
            return True, ""
        except subprocess.CalledProcessError as e:
            err = _decode_stderr(e)
            # Redact token from error message just in case.
            err = err.replace(self._token, "***")
            logger.error("memory_push_failed", error=err)
            return False, f"git push failed: {err}"

    def _open_pr(self, head: str, title: str, body: str) -> tuple[Optional[str], str]:
        slug = self._resolve_repo_slug()
        assert slug
        url = f"{_GITHUB_API}/repos/{slug}/pulls"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": self._base_branch,
            "maintainer_can_modify": True,
        }
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=_HTTP_TIMEOUT)
        except Exception as e:
            logger.error("memory_pr_request_failed", error=str(e))
            return None, f"PR request failed: {e}"

        if resp.status_code == 201:
            data = resp.json()
            return data.get("html_url"), ""

        # 422 — likely a PR already exists for this head. Try to look it up.
        if resp.status_code == 422:
            existing, err = self._find_existing_pr(head)
            if existing:
                return existing, ""
            return None, f"GitHub 422: {err or resp.text[:200]}"

        logger.error("memory_pr_bad_status", status=resp.status_code, body=resp.text[:500])
        return None, f"GitHub {resp.status_code}: {resp.text[:200]}"

    def _find_existing_pr(self, head: str) -> tuple[Optional[str], str]:
        slug = self._resolve_repo_slug()
        assert slug
        owner = slug.split("/", 1)[0]
        url = f"{_GITHUB_API}/repos/{slug}/pulls"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
        }
        params = {"head": f"{owner}:{head}", "state": "open"}
        try:
            resp = httpx.get(url, headers=headers, params=params, timeout=_HTTP_TIMEOUT)
            if resp.status_code == 200 and resp.json():
                return resp.json()[0].get("html_url"), ""
            return None, f"lookup status {resp.status_code}"
        except Exception as e:
            return None, str(e)

    def _resolve_repo_slug(self) -> Optional[str]:
        if self._github_repo:
            return self._github_repo.strip().strip("/")
        try:
            remote = self._run_git(["config", "--get", "remote.origin.url"]).strip()
        except subprocess.CalledProcessError:
            return None
        slug = _parse_github_slug(remote)
        if slug:
            self._github_repo = slug
        return slug

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


# ---- Helpers ----


def _parse_github_slug(remote_url: str) -> Optional[str]:
    """Extract `owner/repo` from common GitHub remote URL formats."""
    if not remote_url:
        return None
    # git@github.com:owner/repo.git
    m = re.match(r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?$", remote_url)
    if m:
        return m.group(1)
    # https://github.com/owner/repo(.git)
    try:
        parsed = urlparse(remote_url)
        if parsed.hostname and parsed.hostname.endswith("github.com"):
            path = parsed.path.lstrip("/")
            if path.endswith(".git"):
                path = path[:-4]
            return path or None
    except Exception:
        return None
    return None


def _decode_stderr(e: subprocess.CalledProcessError) -> str:
    raw = e.stderr
    if isinstance(raw, bytes):
        return raw.decode(errors="replace")
    return raw or str(e)


def _build_pr_body(draft: dict, context: str) -> str:
    parts = [context, ""]
    if draft.get("headline"):
        parts.append(f"**Headline:** {draft['headline']}")
        parts.append("")
    for key, label in (
        ("mistakes_entry", "MISTAKES.md"),
        ("learnings_entry", "LEARNINGS.md"),
        ("strategy_patch", "TRADING-STRATEGY.md"),
        ("weekly_entry", "WEEKLY-REVIEW.md"),
    ):
        value = draft.get(key)
        if value:
            parts.append(f"### {label}")
            parts.append("")
            parts.append(value.strip())
            parts.append("")
    if draft.get("config_suggestion"):
        parts.append("### Config suggestion")
        parts.append("")
        parts.append(draft["config_suggestion"])
        parts.append("")
    parts.append("---")
    parts.append("_Opened automatically after Telegram approval. Review and merge on GitHub; no auto-merge._")
    return "\n".join(parts)
