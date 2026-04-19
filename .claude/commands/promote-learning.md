---
description: Manually promote a MISTAKES.md entry to a LEARNINGS.md pattern (Telegram-gated)
argument-hint: "<pattern description>"
---

The user wants to promote the pattern `$ARGUMENTS` from MISTAKES.md into LEARNINGS.md.

Steps:
1. Read `memory/MISTAKES.md` and find entries matching the pattern.
2. Draft a `## L<YYYYMMDD-slug> — <title>` section following the format already in `memory/LEARNINGS.md`, citing specific MISTAKES.md entries as evidence.
3. Show me the proposed entry and ask whether to file it as a pending_memory_update (same Telegram-approval path as automated postmortems).

Never edit `memory/LEARNINGS.md` directly — always route through the pending-update workflow so I approve via Telegram.
