"""
خدمة SMS بدعم مزودات HTTP عامة مثل يمن موبايل، سبا فون، YOU
"""
import json
import time
from typing import Optional, Dict, Any

import requests

from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import ConfigurationError
from app.models.message import Message, MessageStatus


class GenericHTTPGatewayService:
    """مزود SMS عام عبر رابط HTTP/REST."""

    def __init__(self, provider_name: str):
        self.provider_name = (provider_name or '').strip().lower()
        config = settings.sms.get_provider_config(self.provider_name)
        if not config or not settings.sms.is_provider_configured(self.provider_name):
            raise ConfigurationError(f"إعدادات {self.provider_name} غير مكتملة")

        self.url = str(config.get('url', '')).strip()
        self.username = str(config.get('username', '')).strip()
        self.password = str(config.get('password', '')).strip()
        self.sender = str(config.get('sender', '')).strip() or 'MessageFlow'
        self.api_key = str(config.get('api_key', '')).strip()
        self.timeout = settings.sms.timeout_seconds
        logger.info(f"تم تهيئة خدمة SMS عبر {self.provider_name} / HTTP Gateway")

    def send(self, message: Message) -> Message:
        message.status = MessageStatus.SENDING
        message.provider = self.provider_name

        try:
            payload = self._build_payload(message)
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json() if response.headers.get('Content-Type', '').lower().startswith('application/json') else {}

            ok = self._is_success(data, response.text)
            if ok:
                message_id = self._extract_message_id(data, response.text)
                message.mark_as_sent(message_id)
                logger.success(f"تم إرسال SMS عبر {self.provider_name}", to=message.contact_phone, provider=self.provider_name)
                return message

            err = self._extract_error(data, response.text)
            message.mark_as_failed(err)
            logger.error(f"فشل إرسال SMS عبر {self.provider_name}", to=message.contact_phone, error=err)
            return message

        except requests.exceptions.RequestException as exc:
            message.mark_as_failed(f"خطأ شبكة {self.provider_name}: {exc}")
            logger.log_exception(exc, {'phone': message.contact_phone, 'type': 'sms', 'provider': self.provider_name})
            return message
        except Exception as exc:
            message.mark_as_failed(str(exc))
            logger.log_exception(exc, {'phone': message.contact_phone, 'type': 'sms', 'provider': self.provider_name})
            return message

    def _build_payload(self, message: Message) -> Dict[str, Any]:
        payload = {
            'to': message.contact_phone,
            'message': message.content,
            'sender': self.sender,
            'username': self.username,
            'password': self.password,
            'api_key': self.api_key,
            'from': self.sender,
            'text': message.content,
            'phone': message.contact_phone,
        }
        return {k: v for k, v in payload.items() if v not in (None, '', False)}

    def _is_success(self, data: Dict[str, Any], raw: str) -> bool:
        if not data:
            text = (raw or '').strip().lower()
            return any(token in text for token in ['success', 'ok', 'sent', 'accepted', 'messageid', 'id'])

        if isinstance(data, dict):
            values = [str(v).lower() for v in data.values()]
            combined = ' '.join(values)
            return any(token in combined for token in ['success', 'ok', 'sent', 'accepted', 'messageid', 'id'])

        return False

    def _extract_message_id(self, data: Dict[str, Any], raw: str) -> Optional[str]:
        if isinstance(data, dict):
            for key in ('message_id', 'msg_id', 'id', 'sms_id', 'messageId', 'request_id', 'requestId'):
                if key in data and data[key] not in (None, ''):
                    return str(data[key])
            for value in data.values():
                if isinstance(value, (int, str)) and str(value).strip() and 'error' not in str(value).lower():
                    return str(value)
        return raw[:120] if raw else None

    def _extract_error(self, data: Dict[str, Any], raw: str) -> str:
        if isinstance(data, dict):
            for key in ('error', 'message', 'detail', 'details', 'status', 'error_message'):
                if key in data and data[key] not in (None, ''):
                    return str(data[key])
        return raw[:200] if raw else f'فشل إرسال الرسالة عبر {self.provider_name}'


try:
    provider = settings.sms.provider
    if provider in {'yemen_mobile', 'sapa_phone', 'you'} and settings.sms.is_provider_configured(provider):
        sms_service = GenericHTTPGatewayService(provider)
    else:
        from app.services.sms_service import SMSService
        sms_service = SMSService()
except Exception:
    try:
        from app.services.sms_service import SMSService
        sms_service = SMSService()
    except Exception:
        sms_service = None
        logger.warning("خدمة SMS غير متاحة - لا توجد إعدادات فعالة")
