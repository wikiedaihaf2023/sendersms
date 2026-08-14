"""
الإعدادات المركزية للتطبيق
تقرأ القيم من ملف .env وتوفرها عبر الكائن `settings`
"""
import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

# جذر المشروع (المجلد الذي يحتوي على run.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# تحميل متغيرات البيئة من ملف .env إن وُجد
load_dotenv(BASE_DIR / '.env')


def _get(key: str, default: str = '') -> str:
    return os.getenv(key, default)


def _get_bool(key: str, default: bool = False) -> bool:
    return _get(key, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get(key, str(default)))
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(_get(key, str(default)))
    except ValueError:
        return default


@dataclass
class TwilioSettings:
    account_sid: str = ''
    auth_token: str = ''
    phone_number: str = ''     # رقم الإرسال لرسائل SMS (بصيغة E.164)
    whatsapp_number: str = ''  # رقم الإرسال لواتس آب (whatsapp:+1...)

    def is_configured(self) -> bool:
        """توفر بيانات الاعتماد الأساسية"""
        return bool(self.account_sid and self.auth_token)

    def is_sms_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.phone_number)

    def is_whatsapp_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.whatsapp_number)


@dataclass
class SMSGatewaySettings:
    provider: str = 'twilio'
    yemen_mobile_url: str = ''
    yemen_mobile_username: str = ''
    yemen_mobile_password: str = ''
    yemen_mobile_sender: str = ''
    yemen_mobile_api_key: str = ''
    sapa_phone_url: str = ''
    sapa_phone_username: str = ''
    sapa_phone_password: str = ''
    sapa_phone_sender: str = ''
    sapa_phone_api_key: str = ''
    you_url: str = ''
    you_username: str = ''
    you_password: str = ''
    you_sender: str = ''
    you_api_key: str = ''
    timeout_seconds: int = 30

    def is_provider_configured(self, provider: str) -> bool:
        provider = (provider or '').strip().lower()
        settings_map = {
            'yemen_mobile': {
                'url': self.yemen_mobile_url,
                'username': self.yemen_mobile_username,
                'password': self.yemen_mobile_password,
                'api_key': self.yemen_mobile_api_key,
            },
            'sapa_phone': {
                'url': self.sapa_phone_url,
                'username': self.sapa_phone_username,
                'password': self.sapa_phone_password,
                'api_key': self.sapa_phone_api_key,
            },
            'you': {
                'url': self.you_url,
                'username': self.you_username,
                'password': self.you_password,
                'api_key': self.you_api_key,
            },
        }
        values = settings_map.get(provider)
        if not values:
            return False
        return bool(values['url'] and ((values['username'] and values['password']) or values['api_key']))

    def is_yemen_mobile_configured(self) -> bool:
        return self.is_provider_configured('yemen_mobile')

    def is_sapa_phone_configured(self) -> bool:
        return self.is_provider_configured('sapa_phone')

    def is_you_configured(self) -> bool:
        return self.is_provider_configured('you')

    def get_provider_config(self, provider: str):
        provider = (provider or '').strip().lower()
        return {
            'yemen_mobile': {
                'url': self.yemen_mobile_url,
                'username': self.yemen_mobile_username,
                'password': self.yemen_mobile_password,
                'sender': self.yemen_mobile_sender,
                'api_key': self.yemen_mobile_api_key,
            },
            'sapa_phone': {
                'url': self.sapa_phone_url,
                'username': self.sapa_phone_username,
                'password': self.sapa_phone_password,
                'sender': self.sapa_phone_sender,
                'api_key': self.sapa_phone_api_key,
            },
            'you': {
                'url': self.you_url,
                'username': self.you_username,
                'password': self.you_password,
                'sender': self.you_sender,
                'api_key': self.you_api_key,
            },
        }.get(provider, {})


@dataclass
class MetaSettings:
    access_token: str = ''
    phone_number_id: str = ''
    api_version: str = 'v19.0'

    def is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id)


@dataclass
class RateLimitSettings:
    sms_per_second: float = 1.0
    whatsapp_per_second: float = 1.0
    delay_between_messages: float = 1.0
    max_retries: int = 3
    retry_delay: float = 2.0


@dataclass
class MessageSettings:
    enable_personalization: bool = True
    default_message: str = (
        "عزيزي العميل، تم تجهيز جواز سفرك وهو جاهز للاستلام. شكراً لتعاملكم معنا."
    )
    personalized_template: str = (
        "عزيزي {name}، تم تجهيز جواز سفرك رقم {passport} وهو جاهز للاستلام. شكراً لتعاملكم معنا."
    )


@dataclass
class DatabaseSettings:
    path: str = str(BASE_DIR / 'data' / 'messageflow.db')


class Settings:
    """حاوية الإعدادات العامة"""

    def __init__(self):
        self.app_name = 'MessageFlow Pro'
        self.app_version = '1.0.0'
        self.default_country_code = 'SA'
        self.log_level = 'INFO'
        self.debug = False
        self.test_mode = False
        self.secret_key = 'change_this_to_random_secret'

        self.twilio = TwilioSettings()
        self.sms = SMSGatewaySettings()
        self.meta = MetaSettings()
        self.rate_limit = RateLimitSettings()
        self.message = MessageSettings()
        self.database = DatabaseSettings()

        self._load_from_env()

    def _load_from_env(self):
        self.app_name = _get('APP_NAME', self.app_name)
        self.app_version = _get('APP_VERSION', self.app_version)
        self.default_country_code = _get('DEFAULT_COUNTRY_CODE', self.default_country_code)
        self.log_level = _get('LOG_LEVEL', self.log_level).upper()
        self.debug = _get_bool('DEBUG', self.debug)
        self.test_mode = _get_bool('TEST_MODE', self.test_mode)
        self.secret_key = _get('SECRET_KEY', self.secret_key)

        # SMS provider selection
        self.sms.provider = _get('SMS_PROVIDER', self.sms.provider).lower() or 'twilio'
        self.sms.timeout_seconds = _get_int('SMS_TIMEOUT_SECONDS', self.sms.timeout_seconds)

        # Twilio
        self.twilio.account_sid = _get('TWILIO_ACCOUNT_SID')
        self.twilio.auth_token = _get('TWILIO_AUTH_TOKEN')
        self.twilio.phone_number = _get('TWILIO_PHONE_NUMBER')
        self.twilio.whatsapp_number = _get('TWILIO_WHATSAPP_NUMBER')

        # Yemen Mobile / generic HTTP gateways
        self.sms.yemen_mobile_url = _get('YEMEN_MOBILE_URL', self.sms.yemen_mobile_url)
        self.sms.yemen_mobile_username = _get('YEMEN_MOBILE_USERNAME', self.sms.yemen_mobile_username)
        self.sms.yemen_mobile_password = _get('YEMEN_MOBILE_PASSWORD', self.sms.yemen_mobile_password)
        self.sms.yemen_mobile_sender = _get('YEMEN_MOBILE_SENDER', self.sms.yemen_mobile_sender)
        self.sms.yemen_mobile_api_key = _get('YEMEN_MOBILE_API_KEY', self.sms.yemen_mobile_api_key)

        self.sms.sapa_phone_url = _get('SAPA_PHONE_URL', self.sms.sapa_phone_url)
        self.sms.sapa_phone_username = _get('SAPA_PHONE_USERNAME', self.sms.sapa_phone_username)
        self.sms.sapa_phone_password = _get('SAPA_PHONE_PASSWORD', self.sms.sapa_phone_password)
        self.sms.sapa_phone_sender = _get('SAPA_PHONE_SENDER', self.sms.sapa_phone_sender)
        self.sms.sapa_phone_api_key = _get('SAPA_PHONE_API_KEY', self.sms.sapa_phone_api_key)

        self.sms.you_url = _get('YOU_URL', self.sms.you_url)
        self.sms.you_username = _get('YOU_USERNAME', self.sms.you_username)
        self.sms.you_password = _get('YOU_PASSWORD', self.sms.you_password)
        self.sms.you_sender = _get('YOU_SENDER', self.sms.you_sender)
        self.sms.you_api_key = _get('YOU_API_KEY', self.sms.you_api_key)

        # Meta
        self.meta.access_token = _get('META_ACCESS_TOKEN')
        self.meta.phone_number_id = _get('META_PHONE_NUMBER_ID')
        self.meta.api_version = _get('META_API_VERSION', self.meta.api_version)

        # معدل الإرسال
        self.rate_limit.sms_per_second = _get_float('SMS_PER_SECOND', self.rate_limit.sms_per_second)
        self.rate_limit.whatsapp_per_second = _get_float('WHATSAPP_PER_SECOND', self.rate_limit.whatsapp_per_second)
        self.rate_limit.delay_between_messages = _get_float('DELAY_BETWEEN_MESSAGES', self.rate_limit.delay_between_messages)
        self.rate_limit.max_retries = _get_int('MAX_RETRIES', self.rate_limit.max_retries)
        self.rate_limit.retry_delay = _get_float('RETRY_DELAY', self.rate_limit.retry_delay)

        # الرسائل
        self.message.enable_personalization = _get_bool('ENABLE_PERSONALIZATION', self.message.enable_personalization)
        self.message.default_message = _get('DEFAULT_MESSAGE', self.message.default_message)
        self.message.personalized_template = _get('PERSONALIZED_TEMPLATE', self.message.personalized_template)

        # قاعدة البيانات
        db_path = _get('DB_PATH')
        if db_path:
            self.database.path = db_path


# الكائن العام للإعدادات
settings = Settings()
