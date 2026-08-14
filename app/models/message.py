"""
نموذج الرسالة
"""
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import Optional


class MessageType(str, Enum):
    SMS = 'sms'
    WHATSAPP = 'whatsapp'


class MessageStatus(str, Enum):
    PENDING = 'pending'
    SENDING = 'sending'
    SENT = 'sent'
    FAILED = 'failed'


@dataclass
class Message:
    """رسالة جاهزة للإرسال"""

    contact_phone: str
    content: str
    message_type: MessageType = MessageType.SMS
    contact_name: Optional[str] = None
    passport_number: Optional[str] = None

    status: MessageStatus = MessageStatus.PENDING
    message_id: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    sent_at: Optional[datetime] = None

    @property
    def is_sent(self) -> bool:
        return self.status == MessageStatus.SENT

    @property
    def is_failed(self) -> bool:
        return self.status == MessageStatus.FAILED

    @property
    def can_retry(self) -> bool:
        from app.core.config import settings
        return self.retry_count < settings.rate_limit.max_retries

    def mark_as_sent(self, message_id: Optional[str] = None):
        self.status = MessageStatus.SENT
        self.message_id = message_id
        self.error = None
        self.sent_at = datetime.now()

    def mark_as_failed(self, error: str):
        self.status = MessageStatus.FAILED
        self.error = error

    def increment_retry(self):
        self.retry_count += 1
        self.status = MessageStatus.PENDING
