"""
نموذج جهة الاتصال
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ContactStatus(str, Enum):
    PENDING = 'pending'
    VALID = 'valid'
    INVALID = 'invalid'
    SENT = 'sent'
    FAILED = 'failed'


@dataclass
class Contact:
    """جهة اتصال قادمة من ملف الإكسل"""

    phone_number: str
    name: Optional[str] = None
    passport_number: Optional[str] = None
    row_number: int = 0

    # تُملأ بعد التحقق
    formatted_phone: str = ''
    is_valid: bool = False
    error_message: Optional[str] = None
    status: ContactStatus = ContactStatus.PENDING

    @property
    def display_phone(self) -> str:
        """رقم العرض (بالصيغة الدولية إن وُجدت)"""
        return self.formatted_phone or self.phone_number
