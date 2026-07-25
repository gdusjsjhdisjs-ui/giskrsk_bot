"""Сервис отправки уведомлений пользователям."""

from __future__ import annotations

import logging

from app.integrations.telegram import TelegramClient
from app.repositories.notification_repo import NotificationRepo

logger = logging.getLogger(__name__)


class NotificationService:
    """Отправка уведомлений об изменениях участков."""

    def __init__(self, notif_repo: NotificationRepo, telegram: TelegramClient) -> None:
        self.notif_repo = notif_repo
        self.telegram = telegram

    async def send_notification(self, telegram_id: int, text: str) -> bool:
        """Отправить уведомление пользователю."""
        return await self.telegram.send_notification(telegram_id, text)

    async def process_pending(self) -> int:
        """Отправить все ожидающие уведомления. Возвращает количество."""
        pending = await self.notif_repo.get_pending()
        sent_count = 0

        for notif in pending:
            try:
                success = await self.telegram.send_notification(
                    notif.telegram_id,
                    notif.message_text or "Обнаружены изменения по отслеживаемому участку.",
                )
                if success:
                    await self.notif_repo.mark_sent(notif.id)
                    sent_count += 1
                else:
                    await self.notif_repo.mark_failed(notif.id)
            except Exception as e:
                logger.error("Failed to send notification %s: %s", notif.id, e)
                await self.notif_repo.mark_failed(notif.id)

        logger.info("Processed %d pending notifications, sent %d", len(pending), sent_count)
        return sent_count

    async def get_user_notifications(self, telegram_id: int, limit: int = 20) -> list[dict]:
        """Получить историю уведомлений пользователя."""
        notifs = await self.notif_repo.get_user_notifications(telegram_id, limit)
        return [
            {
                "id": str(n.id),
                "text": n.message_text,
                "status": n.status,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            }
            for n in notifs
        ]
