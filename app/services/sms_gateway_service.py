"""
خدمة SMS بدعم مزودات HTTP عامة مثل يمن موبايل، سبا فون، YOU، وبوابات الهاتف المحلية (Sapa GSM/Gateway)
"""
import json
import time
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import requests

from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import ConfigurationError
from app.models.message import Message, MessageStatus


PROVIDER_PROFILES: Dict[str, Dict[str, Any]] = {
    "yemen_mobile": {
        "method": "json",
        "to_field": "to",
        "text_field": "message",
        "sender_field": "sender",
        "username_field": "username",
        "password_field": "password",
        "api_key_field": "api_key",
        "from_field": "from",
        "phone_alt_field": "phone",
        "text_alt_field": "text",
        "success_tokens": ["success", "ok", "sent", "accepted", "messageid", "id", "تم"],
    },
    "sapa_phone": {
        "method": "json",
        "to_field": "to",
        "text_field": "message",
        "sender_field": "sender",
        "username_field": "username",
        "password_field": "password",
        "api_key_field": "api_key",
        "from_field": "from",
        "phone_alt_field": "phone",
        "text_alt_field": "text",
        "success_tokens": ["success", "ok", "sent", "accepted", "messageid", "id", "تم"],
    },
    "you": {
        "method": "json",
        "to_field": "to",
        "text_field": "message",
        "sender_field": "sender",
        "username_field": "username",
        "password_field": "password",
        "api_key_field": "api_key",
        "from_field": "from",
        "phone_alt_field": "phone",
        "text_alt_field": "text",
        "success_tokens": ["success", "ok", "sent", "accepted", "messageid", "id", "تم"],
    },
    "phone_gateway": {
        "method": "get",
        "to_field": "num",
        "text_field": "msg",
        "sender_field": "sender",
        "username_field": "username",
        "password_field": "password",
        "api_key_field": "api_key",
        "from_field": "from",
        "phone_alt_field": "to",
        "text_alt_field": "text",
        "success_tokens": ["success", "ok", "sent", "accepted", "messageid", "id", "queued", "pending", "تم", "true", "1"],
    },
}

PHONE_GATEWAY_PRESETS: Dict[str, Dict[str, Any]] = {
    "sapa_gsm": {
        "label": "Sapa GSM (الأكثر شيوعاً في اليمن)",
        "method": "get",
        "port": "8090",
        "path": "/sendsms",
        "to_field": "num",
        "text_field": "msg",
        "sender_field": "sender",
        "description": "منفذ 8090 + /sendsms مع بارامترات num / msg",
        "success_tokens": ["success", "ok", "sent", "queued", "pending", "true", "1", "تم"],
    },
    "sapa_gsm_post": {
        "label": "Sapa GSM (POST JSON)",
        "method": "json",
        "port": "8090",
        "path": "/sendsms",
        "to_field": "num",
        "text_field": "msg",
        "sender_field": "sender",
        "description": "نفس Sapa GSM ولكن عبر POST JSON للرسائل الطويلة",
        "success_tokens": ["success", "ok", "sent", "queued", "pending", "true", "1", "تم"],
    },
    "sms_gateway_pro": {
        "label": "SMS Gateway Pro (Moon Tech)",
        "method": "get",
        "port": "8080",
        "path": "/api/v1/sms/send",
        "to_field": "to",
        "text_field": "text",
        "sender_field": "sender",
        "description": "منفذ 8080 + /api/v1/sms/send مع بارامترات to / text",
        "success_tokens": ["success", "ok", "sent", "queued", "true", "تم"],
    },
    "sms_gateway_pro_json": {
        "label": "SMS Gateway Pro (POST JSON)",
        "method": "json",
        "port": "8080",
        "path": "/api/v1/sms/send",
        "to_field": "to",
        "text_field": "message",
        "sender_field": "sender",
        "description": "POST JSON مثالي لحملات كبيرة",
        "success_tokens": ["success", "ok", "sent", "true", "تم"],
    },
    "remote_sms_gateway": {
        "label": "Remote SMS Gateway (قديم)",
        "method": "get",
        "port": "9090",
        "path": "/send",
        "to_field": "phone",
        "text_field": "text",
        "sender_field": "from",
        "description": "منفذ 9090 + /send مع بارامترات phone / text",
        "success_tokens": ["success", "ok", "sent", "true", "تم"],
    },
    "gsm_modem": {
        "label": "Generic GSM Modem / Gateway",
        "method": "get",
        "port": "80",
        "path": "/",
        "to_field": "to",
        "text_field": "message",
        "sender_field": "sender",
        "description": "مولد عام - عدّل المنفذ والمسار حسب جهازك",
        "success_tokens": ["success", "ok", "sent", "true", "تم"],
    },
}


class GenericHTTPGatewayService:
    """مزود SMS عام عبر رابط HTTP/REST بدعم طرق وسمات متعددة."""

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

        self.profile = PROVIDER_PROFILES.get(self.provider_name, PROVIDER_PROFILES["yemen_mobile"])
        self.method = str(config.get('method', '')).strip().lower() or self.profile.get("method", "json")

        logger.info(f"تم تهيئة خدمة SMS عبر {self.provider_name} / HTTP Gateway (Method: {self.method.upper()})")

    def send(self, message: Message) -> Message:
        message.status = MessageStatus.SENDING
        message.provider = self.provider_name

        try:
            payload = self._build_payload(message)
            response = self._dispatch_request(payload)
            response.raise_for_status()
            data = {}
            try:
                ct = (response.headers.get('Content-Type', '') or '').lower()
                if ct.startswith('application/json'):
                    data = response.json()
            except Exception:
                data = {}

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

    def _dispatch_request(self, payload: Dict[str, Any]):
        method = self.method.lower()
        timeout = self.timeout
        if method == "get":
            sep = '&' if '?' in self.url else '?'
            final_url = f"{self.url}{sep}{urlencode(payload)}"
            return requests.get(final_url, timeout=timeout)
        if method == "form":
            return requests.post(self.url, data=payload, timeout=timeout)
        return requests.post(self.url, json=payload, timeout=timeout)

    def _build_payload(self, message: Message) -> Dict[str, Any]:
        p = self.profile
        to = message.contact_phone
        text = message.content

        payload: Dict[str, Any] = {}

        if p.get('to_field'):
            payload[p['to_field']] = to
        if p.get('text_field'):
            payload[p['text_field']] = text
        if p.get('sender_field') and self.sender:
            payload[p['sender_field']] = self.sender
        if p.get('from_field') and self.sender:
            payload[p['from_field']] = self.sender
        if p.get('username_field') and self.username:
            payload[p['username_field']] = self.username
        if p.get('password_field') and self.password:
            payload[p['password_field']] = self.password
        if p.get('api_key_field') and self.api_key:
            payload[p['api_key_field']] = self.api_key
        if p.get('phone_alt_field'):
            payload.setdefault(p['phone_alt_field'], to)
        if p.get('text_alt_field'):
            payload.setdefault(p['text_alt_field'], text)

        legacy_keys = ('to', 'message', 'sender', 'username', 'password', 'api_key', 'from', 'text', 'phone')
        for k in legacy_keys:
            if k not in payload:
                if k in ('to', 'phone'):
                    payload[k] = to
                elif k in ('message', 'text'):
                    payload[k] = text
                elif k in ('sender', 'from'):
                    if self.sender:
                        payload[k] = self.sender
                elif k == 'username' and self.username:
                    payload[k] = self.username
                elif k == 'password' and self.password:
                    payload[k] = self.password
                elif k == 'api_key' and self.api_key:
                    payload[k] = self.api_key

        return {k: v for k, v in payload.items() if v not in (None, '', False)}

    def _is_success(self, data: Dict[str, Any], raw: str) -> bool:
        tokens = self.profile.get("success_tokens", PROVIDER_PROFILES["yemen_mobile"]["success_tokens"])
        if not data:
            text = (raw or '').strip().lower()
            if not text:
                return False
            return any(token in text for token in tokens)

        if isinstance(data, dict):
            values = [str(v).lower() for v in data.values()]
            combined = ' '.join(values)
            if any(token in combined for token in tokens):
                return True
            for v in data.values():
                if isinstance(v, bool) and v is True:
                    return True
                if isinstance(v, (int, float)) and v >= 0 and 'error' not in combined:
                    if v == 1:
                        return True

        text = (raw or '').strip().lower()
        return any(token in text for token in tokens)

    def _extract_message_id(self, data: Dict[str, Any], raw: str) -> Optional[str]:
        if isinstance(data, dict):
            for key in ('message_id', 'msg_id', 'id', 'sms_id', 'messageId', 'request_id', 'requestId', 'reference', 'ref'):
                if key in data and data[key] not in (None, ''):
                    return str(data[key])
            for value in data.values():
                if isinstance(value, (int, str)) and str(value).strip() and 'error' not in str(value).lower():
                    return str(value)
        return raw[:120] if raw else None

    def _extract_error(self, data: Dict[str, Any], raw: str) -> str:
        if isinstance(data, dict):
            for key in ('error', 'message', 'detail', 'details', 'status', 'error_message', 'msg'):
                if key in data and data[key] not in (None, ''):
                    return str(data[key])
        return raw[:200] if raw else f'فشل إرسال الرسالة عبر {self.provider_name}'


PACKAGE_PROVIDERS = {'yemen_mobile', 'sapa_phone', 'you', 'phone_gateway'}


try:
    provider = settings.sms.provider
    if provider in PACKAGE_PROVIDERS and settings.sms.is_provider_configured(provider):
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
