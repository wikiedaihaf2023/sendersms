"""
خدمة التحقق من صحة أرقام الهواتف
تدعم أكثر من 200 دولة عبر مكتبة phonenumbers
"""
from typing import Tuple, Optional

import phonenumbers

from app.core.config import settings
from app.models.contact import Contact, ContactStatus


class ValidatorService:
    """خدمة التحقق من أرقام الهواتف"""

    def __init__(self, default_country_code: Optional[str] = None):
        self.default_country_code = default_country_code or settings.default_country_code

    def validate_phone_number(self, phone) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        التحقق من رقم هاتف واحد

        Args:
            phone: رقم الهاتف بأي صيغة

        Returns:
            (is_valid, formatted_e164, error_message)
        """
        if phone is None or not str(phone).strip():
            return False, None, 'رقم فارغ'

        raw = str(phone).strip()

        try:
            parsed = phonenumbers.parse(raw, self.default_country_code)
        except phonenumbers.NumberParseException as e:
            reason = e.args[0] if e.args else 'تعذر التحليل'
            return False, None, f'رقم غير صالح ({reason})'

        if not phonenumbers.is_valid_number(parsed):
            return False, None, 'رقم غير صالح'
        if not phonenumbers.is_possible_number(parsed):
            return False, None, 'رقم غير محتمل'

        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return True, formatted, None

    def validate_contact(self, contact: Contact) -> Contact:
        """التحقق من جهة اتصال كاملة وتحديث حالتها"""
        is_valid, formatted, error = self.validate_phone_number(contact.phone_number)

        contact.formatted_phone = formatted or ''
        contact.is_valid = is_valid
        contact.error_message = error
        contact.status = ContactStatus.VALID if is_valid else ContactStatus.INVALID

        return contact


# كائن عام من الخدمة
validator_service = ValidatorService()
