"""
خدمة إرسال رسائل واتس آب
تدعم مزودين: Twilio و Meta Business API
"""
import time
import requests
from typing import Dict

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.core.logger import logger
from app.core.config import settings
from app.core.exceptions import MessageSendError, ConfigurationError
from app.models.message import Message, MessageType, MessageStatus


class WhatsAppService:
    """خدمة إرسال رسائل واتس آب"""

    def __init__(self, provider: str = 'auto'):
        """
        تهيئة الخدمة

        Args:
            provider: 'twilio' أو 'meta' أو 'auto' للاختيار التلقائي
        """
        self.provider = provider if provider != 'auto' else self._detect_provider()

        if self.provider == 'twilio':
            if not settings.twilio.is_whatsapp_configured():
                raise ConfigurationError("إعدادات Twilio غير مكتملة")
            self.client = Client(
                settings.twilio.account_sid,
                settings.twilio.auth_token
            )
            self.from_number = settings.twilio.whatsapp_number
        elif self.provider == 'meta':
            if not settings.meta.is_configured():
                raise ConfigurationError("إعدادات Meta غير مكتملة")
            self.base_url = f"https://graph.facebook.com/{settings.meta.api_version}"
            self.access_token = settings.meta.access_token
            self.phone_number_id = settings.meta.phone_number_id
        else:
            raise ConfigurationError("لا يوجد مزود واتس آب متاح")

        self.last_send_time = 0
        logger.info(f"تم تهيئة خدمة واتس آب باستخدام: {self.provider}")

    def _detect_provider(self) -> str:
        """الكشف التلقائي عن المزود المتاح"""
        if settings.twilio.is_whatsapp_configured():
            return 'twilio'
        elif settings.meta.is_configured():
            return 'meta'
        else:
            raise ConfigurationError("لا يوجد مزود واتس آب متاح")

    def send(self, message: Message) -> Message:
        """
        إرسال رسالة واتس آب

        Args:
            message: كائن الرسالة

        Returns:
            الرسالة مع الحالة المحدثة
        """
        self._apply_rate_limit()

        message.status = MessageStatus.SENDING
        message.provider = self.provider

        try:
            logger.debug(
                f"إرسال واتس آب",
                to=message.contact_phone,
                provider=self.provider
            )

            if self.provider == 'twilio':
                result = self._send_via_twilio(message)
            else:
                result = self._send_via_meta(message)

            if result['success']:
                message.mark_as_sent(result['message_id'])
                logger.success(
                    f"تم إرسال واتس آب",
                    to=message.contact_phone,
                    sid=result['message_id']
                )
            else:
                message.mark_as_failed(result['error'])
                logger.error(
                    f"فشل إرسال واتس آب",
                    to=message.contact_phone,
                    error=result['error']
                )

                # إعادة المحاولة إذا أمكن
                if message.can_retry:
                    message.increment_retry()
                    logger.info(
                        f"سيتم إعادة المحاولة "
                        f"({message.retry_count}/{settings.rate_limit.max_retries})"
                    )
                    time.sleep(settings.rate_limit.retry_delay)
                    return self.send(message)

            return message

        except Exception as e:
            message.mark_as_failed(str(e))
            logger.log_exception(e, {'phone': message.contact_phone})
            return message

    def _send_via_twilio(self, message: Message) -> Dict:
        """إرسال عبر Twilio"""
        try:
            whatsapp_to = f"whatsapp:{message.contact_phone}"

            twilio_message = self.client.messages.create(
                body=message.content,
                from_=self.from_number,
                to=whatsapp_to
            )

            return {
                'success': True,
                'message_id': twilio_message.sid,
                'error': None
            }

        except TwilioRestException as e:
            error_msg = self._parse_twilio_error(e)
            return {
                'success': False,
                'message_id': None,
                'error': error_msg
            }
        except Exception as e:
            return {
                'success': False,
                'message_id': None,
                'error': str(e)
            }

    def _send_via_meta(self, message: Message) -> Dict:
        """إرسال عبر Meta Business API"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": message.contact_phone.replace('+', ''),
            "type": "text",
            "text": {
                "body": message.content
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            message_id = result.get('messages', [{}])[0].get('id')

            return {
                'success': True,
                'message_id': message_id,
                'error': None
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"Meta API error: {str(e)}"
            if e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg = error_detail.get('error', {}).get('message', error_msg)
                except Exception:
                    pass
            return {
                'success': False,
                'message_id': None,
                'error': error_msg
            }

    def _apply_rate_limit(self):
        """تطبيق حد معدل الإرسال"""
        current_time = time.time()
        time_since_last = current_time - self.last_send_time
        min_interval = 1.0 / max(settings.rate_limit.whatsapp_per_second, 0.01)

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)

        self.last_send_time = time.time()

    def _parse_twilio_error(self, error: TwilioRestException) -> str:
        """تحليل رسالة خطأ Twilio"""
        error_codes = {
            63016: "لا يمكن إرسال رسائل إلى واتس آب في هذا الرقم",
            63018: "التطبيق غير مفعل للواتس آب",
            63012: "رقم واتس آب غير صالح",
            63013: "رقم تم حظره",
            63014: "رقم غير موجود في واتس آب",
            63015: "قناة غير قابلة للوصول"
        }

        return error_codes.get(error.code, f"خطأ Twilio: {error.msg}")


# كائن عام من الخدمة
try:
    whatsapp_service = WhatsAppService()
except ConfigurationError:
    whatsapp_service = None
    logger.warning("خدمة واتس آب غير متاحة - الإعدادات غير مكتملة")
