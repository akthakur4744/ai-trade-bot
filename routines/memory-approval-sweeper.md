# Routine: Memory Approval Sweeper

**Schedule:** hourly (cron: `15 * * * *` UTC — any hour).

## Purpose

Expire `pending_memory_updates` rows with `status='pending'` older than 60
minutes. On expiry:
- Mark row `status='expired'`.
- Edit the original Telegram message to "⏱ Expired".
- If a GitHub PR was already opened (shouldn't be, but defensive): close it.

## Behavior

```sql
UPDATE pending_memory_updates
   SET status = 'expired'
 WHERE status = 'pending' AND expires_at < now()
RETURNING id, telegram_message_id;
```

For each returned row, call
`TelegramNotifier.update_memory_message(msg_id, "expired")`.

## Entrypoint

```python
# routines/impl/memory_approval_sweeper.py
from datetime import datetime, timezone
from src.config import load_config
from src.storage.database import Database
from src.storage.models import PendingMemoryUpdate
from src.notifications.telegram import TelegramNotifier
import os

def main() -> int:
    cfg = load_config()
    db = Database(cfg.database.url)
    tg = TelegramNotifier(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )
    now = datetime.now(timezone.utc)
    with db.get_session() as s:
        expired = (
            s.query(PendingMemoryUpdate)
            .filter(PendingMemoryUpdate.status == "pending")
            .filter(PendingMemoryUpdate.expires_at < now)
            .all()
        )
        for row in expired:
            row.status = "expired"
            if row.telegram_message_id:
                tg.update_memory_message(row.telegram_message_id, "expired")
        s.commit()
    return 0
```
