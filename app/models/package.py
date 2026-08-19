"""
نماذج الباقات والاشتراكات
"""
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, List


class SubscriptionStatus(str, Enum):
    ACTIVE = 'active'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class UsageOperationType(str, Enum):
    SEND = 'send'
    SUBSCRIBE = 'subscribe'
    TOPUP = 'topup'
    REFUND = 'refund'


@dataclass
class SMSPackage:
    """باقة رسائل مدفوعة"""

    id: int = 0
    name: str = ''
    provider: str = 'yemen_mobile'
    sms_count: int = 0
    price: float = 0.0
    currency: str = 'YER'
    validity_days: int = 30
    is_active: bool = True
    description: str = ''
    created_at: Optional[datetime] = None


@dataclass
class UserSubscription:
    """اشتراك مستخدم في باقة رسائل"""

    id: int = 0
    username: str = ''
    package_id: int = 0
    provider: str = 'yemen_mobile'
    sms_allocated: int = 0
    sms_remaining: int = 0
    total_cost: float = 0.0
    subscription_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    status: str = SubscriptionStatus.ACTIVE

    @property
    def is_active(self) -> bool:
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        if self.expiry_date and datetime.now() > self.expiry_date:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        return bool(self.expiry_date and datetime.now() > self.expiry_date)

    @property
    def usage_percentage(self) -> float:
        if self.sms_allocated <= 0:
            return 0.0
        used = self.sms_allocated - self.sms_remaining
        return min(100.0, (used / self.sms_allocated) * 100)


@dataclass
class SMSUsageLog:
    """سجل استهلاك الرسائل"""

    id: int = 0
    username: str = ''
    provider: str = 'yemen_mobile'
    subscription_id: Optional[int] = None
    messages_sent: int = 0
    sms_charged: int = 0
    operation_type: str = UsageOperationType.SEND
    amount: float = 0.0
    reference: str = ''
    notes: str = ''
    created_at: Optional[datetime] = None
