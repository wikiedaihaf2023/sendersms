"""
مستودعات البيانات - تغليف عمليات قاعدة البيانات
"""
from typing import Optional, List
from datetime import datetime

from app.database.db_manager import db_manager


class MessageRepository:
    """مستودع الرسائل"""

    def is_already_sent(self, contact_phone: str, message_type: str) -> bool:
        """
        التحقق من إرسال رسالة سابقة لهذا الرقم والنوع

        Args:
            contact_phone: رقم الهاتف بصيغة E.164
            message_type: 'sms' أو 'whatsapp'

        Returns:
            True إذا تم الإرسال من قبل بنجاح
        """
        with db_manager.get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as count
                FROM sent_messages
                WHERE contact_phone = ?
                  AND message_type = ?
                  AND status = 'success'
            ''', (contact_phone, message_type))
            result = cursor.fetchone()
            return result['count'] > 0

    def log_message(
        self,
        contact_phone: str,
        formatted_phone: str,
        contact_name: Optional[str],
        passport_number: Optional[str],
        message_type: str,
        message_content: str,
        status: str,
        message_id: Optional[str] = None,
        provider: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0
    ):
        """تسجيل رسالة في قاعدة البيانات"""
        sent_at = datetime.now() if status == 'success' else None

        with db_manager.get_connection() as conn:
            conn.execute('''
                INSERT INTO sent_messages (
                    contact_phone, formatted_phone, contact_name, passport_number,
                    message_type, message_content, status, message_id, provider,
                    error_message, retry_count, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(contact_phone, message_type) DO UPDATE SET
                    status = excluded.status,
                    message_id = excluded.message_id,
                    error_message = excluded.error_message,
                    retry_count = excluded.retry_count,
                    sent_at = excluded.sent_at
            ''', (
                contact_phone, formatted_phone, contact_name, passport_number,
                message_type, message_content, status, message_id, provider,
                error_message, retry_count, sent_at
            ))

    def get_failed_messages(self, limit: int = 100) -> List[dict]:
        """الحصول على الرسائل الفاشلة"""
        with db_manager.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM sent_messages
                WHERE status = 'failed'
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_message_history(self, contact_phone: str) -> List[dict]:
        """الحصول على سجل رسائل لرقم معين"""
        with db_manager.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM sent_messages
                WHERE contact_phone = ?
                ORDER BY created_at DESC
            ''', (contact_phone,))

            return [dict(row) for row in cursor.fetchall()]


class ProviderSettingsRepository:
    """مستودع إعدادات المزودات لكل مستخدم"""

    def save_provider_settings(self, username: str, provider: str = 'twilio', **kwargs):
        username = (username or 'default').strip() or 'default'
        provider = (provider or 'twilio').strip().lower()

        payload = {
            'username': username,
            'provider': provider,
            'yemen_mobile_url': kwargs.get('yemen_mobile_url', ''),
            'yemen_mobile_username': kwargs.get('yemen_mobile_username', ''),
            'yemen_mobile_password': kwargs.get('yemen_mobile_password', ''),
            'yemen_mobile_sender': kwargs.get('yemen_mobile_sender', ''),
            'yemen_mobile_api_key': kwargs.get('yemen_mobile_api_key', ''),
            'sapa_phone_url': kwargs.get('sapa_phone_url', ''),
            'sapa_phone_username': kwargs.get('sapa_phone_username', ''),
            'sapa_phone_password': kwargs.get('sapa_phone_password', ''),
            'sapa_phone_sender': kwargs.get('sapa_phone_sender', ''),
            'sapa_phone_api_key': kwargs.get('sapa_phone_api_key', ''),
            'you_url': kwargs.get('you_url', ''),
            'you_username': kwargs.get('you_username', ''),
            'you_password': kwargs.get('you_password', ''),
            'you_sender': kwargs.get('you_sender', ''),
            'you_api_key': kwargs.get('you_api_key', ''),
        }

        with db_manager.get_connection() as conn:
            conn.execute('''
                INSERT INTO provider_settings (
                    username, provider,
                    yemen_mobile_url, yemen_mobile_username, yemen_mobile_password, yemen_mobile_sender, yemen_mobile_api_key,
                    sapa_phone_url, sapa_phone_username, sapa_phone_password, sapa_phone_sender, sapa_phone_api_key,
                    you_url, you_username, you_password, you_sender, you_api_key,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(username) DO UPDATE SET
                    provider = excluded.provider,
                    yemen_mobile_url = excluded.yemen_mobile_url,
                    yemen_mobile_username = excluded.yemen_mobile_username,
                    yemen_mobile_password = excluded.yemen_mobile_password,
                    yemen_mobile_sender = excluded.yemen_mobile_sender,
                    yemen_mobile_api_key = excluded.yemen_mobile_api_key,
                    sapa_phone_url = excluded.sapa_phone_url,
                    sapa_phone_username = excluded.sapa_phone_username,
                    sapa_phone_password = excluded.sapa_phone_password,
                    sapa_phone_sender = excluded.sapa_phone_sender,
                    sapa_phone_api_key = excluded.sapa_phone_api_key,
                    you_url = excluded.you_url,
                    you_username = excluded.you_username,
                    you_password = excluded.you_password,
                    you_sender = excluded.you_sender,
                    you_api_key = excluded.you_api_key,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                payload['username'],
                payload['provider'],
                payload['yemen_mobile_url'], payload['yemen_mobile_username'], payload['yemen_mobile_password'], payload['yemen_mobile_sender'], payload['yemen_mobile_api_key'],
                payload['sapa_phone_url'], payload['sapa_phone_username'], payload['sapa_phone_password'], payload['sapa_phone_sender'], payload['sapa_phone_api_key'],
                payload['you_url'], payload['you_username'], payload['you_password'], payload['you_sender'], payload['you_api_key'],
            ))

    def get_provider_settings(self, username: str) -> dict:
        username = (username or 'default').strip() or 'default'
        with db_manager.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM provider_settings WHERE username = ?
            ''', (username,))
            row = cursor.fetchone()
            if not row:
                return {'username': username, 'provider': 'twilio'}
            return dict(row)

    def get_provider_settings_for_default_user(self) -> dict:
        return self.get_provider_settings('default')


class OperationRepository:
    """مستودع سجل العمليات"""

    def start_operation(self, operation_type: str) -> int:
        """بدء عملية جديدة وإرجاع معرفها"""
        with db_manager.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO operation_log (operation_type, started_at)
                VALUES (?, ?)
            ''', (operation_type, datetime.now()))
            return cursor.lastrowid

    def finish_operation(
        self,
        operation_id: int,
        total_records: int,
        success_count: int,
        failed_count: int,
        details: str = ''
    ):
        """إنهاء عملية"""
        with db_manager.get_connection() as conn:
            conn.execute('''
                UPDATE operation_log
                SET finished_at = ?,
                    total_records = ?,
                    success_count = ?,
                    failed_count = ?,
                    details = ?
                WHERE id = ?
            ''', (
                datetime.now(),
                total_records,
                success_count,
                failed_count,
                details,
                operation_id
            ))


# كائنات عامة
message_repo = MessageRepository()
provider_settings_repo = ProviderSettingsRepository()
operation_repo = OperationRepository()
