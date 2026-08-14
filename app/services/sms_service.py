"""
خدمة إرسال رسائل SMS عبر Twilio
"""
import time

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.core.logger import logger
from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.models.message import Message, MessageStatus


class SMSService:
    """خدمة إرسال رسائل SMS"""

    def __init__(self):
        """تهيئة الخدمة — تتطلب إعدادات Twilio SMS مكتملة"""
        if not settings.twilio.is_sms_configured():
            raise ConfigurationError("إعدادات Twilio SMS غير مكتملة")

        self.client = Client(
            settings.twilio.account_sid,
            settings.twilio.auth_token
        )
        self.from_number = settings.twilio.phone_number
        self.last_send_time = 0
        logger.info("تم تهيئة خدمة SMS باستخدام Twilio")

    def send(self, message: Message) -> Message:
        """
        إرسال رسالة SMS

        Returns:
            الرسالة مع الحالة المحدثة
        """
        self._apply_rate_limit()

        message.status = MessageStatus.SENDING
        message.provider = 'twilio'

        try:
            logger.debug("إرسال SMS", to=message.contact_phone)

            twilio_message = self.client.messages.create(
                body=message.content,
                from_=self.from_number,
                to=message.contact_phone
            )

            message.mark_as_sent(twilio_message.sid)
            logger.success("تم إرسال SMS", to=message.contact_phone, sid=twilio_message.sid)

        except TwilioRestException as e:
            error_msg = self._parse_twilio_error(e)
            message.mark_as_failed(error_msg)
            logger.error("فشل إرسال SMS", to=message.contact_phone, error=error_msg)

            if message.can_retry:
                message.increment_retry()
                logger.info(
                    f"سيتم إعادة محاولة SMS "
                    f"({message.retry_count}/{settings.rate_limit.max_retries})"
                )
                time.sleep(settings.rate_limit.retry_delay)
                return self.send(message)

        except Exception as e:
            message.mark_as_failed(str(e))
            logger.log_exception(e, {'phone': message.contact_phone, 'type': 'sms'})

        return message

    def _apply_rate_limit(self):
        """تطبيق حد معدل الإرسال"""
        current_time = time.time()
        time_since_last = current_time - self.last_send_time
        min_interval = 1.0 / max(settings.rate_limit.sms_per_second, 0.01)

        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)

        self.last_send_time = time.time()

    def _parse_twilio_error(self, error: TwilioRestException) -> str:
        """تحليل رسالة خطأ Twilio"""
        error_codes = {
            21211: "رقم الهاتف غير صالح",
            21407: "الرقم موجود في قائمة الحظر",
            21610: "الرقم غير قابل للاستقبال (غير مفعّل)",
            30007: "تم تجاوز حد الإرسال",
        }
        return error_codes.get(error.code, f"خطأ Twilio: {error.msg}")


# كائن عام من الخدمة
try:
    sms_service = SMSService()
except ConfigurationError:
    sms_service = None
    logger.warning("خدمة SMS غير متاحة - الإعدادات غير مكتملة")
