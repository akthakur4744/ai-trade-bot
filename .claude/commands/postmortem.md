---
description: Draft a postmortem for a closed trade (Telegram-gated before writing memory/*.md)
argument-hint: <order_id>
---

Run a manual postmortem for the trade with order_id `$ARGUMENTS`.

Steps:
1. Run: `python scripts/postmortem.py $ARGUMENTS`
2. Report the pending_id printed in the log.
3. Remind me to approve or reject via Telegram (60 min expiry). No memory/*.md files will be edited until I approve.
