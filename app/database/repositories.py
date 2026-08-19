"""
مستودعات البيانات - تغليف عمليات قاعدة البيانات
"""
from typing import Optional, List
from datetime import datetime, timedelta

from app.database.db_manager import db_manager
from app.models.package import (
    SMSPackage, UserSubscription, SMSUsageLog,
    SubscriptionStatus, UsageOperationType
)


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

    def save_provider_settings(self, username: str, provider: str = 'yemen_mobile', **kwargs):
        username = (username or 'default').strip() or 'default'
        provider = (provider or 'yemen_mobile').strip().lower()

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
                return {'username': username, 'provider': 'yemen_mobile'}
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


class SMSPackageRepository:
    """مستودع باقات الرسائل المدفوعة"""

    def get_all_packages(self, provider: str = None, only_active: bool = True) -> List[SMSPackage]:
        with db_manager.get_connection() as conn:
            query = 'SELECT * FROM sms_packages WHERE 1=1'
            params = []
            if provider:
                query += ' AND provider = ?'
                params.append(provider)
            if only_active:
                query += ' AND is_active = 1'
            query += ' ORDER BY sms_count ASC'
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_package(dict(r)) for r in rows]

    def get_package_by_id(self, package_id: int) -> Optional[SMSPackage]:
        with db_manager.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM sms_packages WHERE id = ?', (package_id,))
            row = cursor.fetchone()
            return self._row_to_package(dict(row)) if row else None

    def _row_to_package(self, row: dict) -> SMSPackage:
        return SMSPackage(
            id=row.get('id', 0),
            name=row.get('name', ''),
            provider=row.get('provider', 'yemen_mobile'),
            sms_count=row.get('sms_count', 0),
            price=row.get('price', 0.0),
            currency=row.get('currency', 'YER'),
            validity_days=row.get('validity_days', 30),
            is_active=bool(row.get('is_active', 1)),
            description=row.get('description', ''),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
        )


class UserSubscriptionRepository:
    """مستودع اشتراكات المستخدمين في الباقات"""

    def subscribe(self, username: str, package: SMSPackage, provider: str = None) -> UserSubscription:
        username = (username or 'default').strip() or 'default'
        provider = provider or package.provider or 'yemen_mobile'
        now = datetime.now()
        expiry = now + timedelta(days=package.validity_days or 30)

        with db_manager.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO user_subscriptions (
                    username, package_id, provider, sms_allocated, sms_remaining,
                    total_cost, subscription_date, expiry_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                username, package.id, provider, package.sms_count, package.sms_count,
                package.price, now, expiry, SubscriptionStatus.ACTIVE,
            ))
            sub_id = cursor.lastrowid

            usage_log = SMSUsageLog(
                username=username,
                provider=provider,
                subscription_id=sub_id,
                operation_type=UsageOperationType.SUBSCRIBE,
                sms_charged=0,
                amount=package.price,
                reference=f'PKG-{package.id}',
                notes=f'اشتراك في باقة: {package.name}'
            )
            SMSUsageLogRepository()._insert_log(conn, usage_log)

        return self.get_subscription_by_id(sub_id)

    def get_subscription_by_id(self, subscription_id: int) -> Optional[UserSubscription]:
        with db_manager.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM user_subscriptions WHERE id = ?', (subscription_id,))
            row = cursor.fetchone()
            return self._row_to_sub(dict(row)) if row else None

    def get_active_subscription(self, username: str, provider: str = 'yemen_mobile') -> Optional[UserSubscription]:
        username = (username or 'default').strip() or 'default'
        with db_manager.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM user_subscriptions
                WHERE username = ? AND provider = ? AND status = ?
                ORDER BY subscription_date DESC
                LIMIT 1
            ''', (username, provider, SubscriptionStatus.ACTIVE))
            row = cursor.fetchone()
            sub = self._row_to_sub(dict(row)) if row else None
            if sub and sub.is_active:
                return sub
            if sub:
                self._mark_expired(sub.id)
            return None

    def get_remaining_sms(self, username: str, provider: str = 'yemen_mobile') -> int:
        sub = self.get_active_subscription(username, provider)
        return sub.sms_remaining if sub else 0

    def has_sufficient_balance(self, username: str, required: int, provider: str = 'yemen_mobile') -> bool:
        remaining = self.get_remaining_sms(username, provider)
        return remaining >= required if required > 0 else remaining > 0

    def consume_sms(self, username: str, count: int, provider: str = 'yemen_mobile',
                    subscription_id: int = None, reference: str = None) -> bool:
        if count <= 0:
            return False
        username = (username or 'default').strip() or 'default'

        with db_manager.get_connection() as conn:
            if not subscription_id:
                cursor = conn.execute('''
                    SELECT id, sms_remaining FROM user_subscriptions
                    WHERE username = ? AND provider = ? AND status = ?
                    ORDER BY subscription_date DESC LIMIT 1
                ''', (username, provider, SubscriptionStatus.ACTIVE))
                row = cursor.fetchone()
                if not row:
                    return False
                subscription_id = row['id']
                sms_remaining = row['sms_remaining']
            else:
                cursor = conn.execute('SELECT sms_remaining FROM user_subscriptions WHERE id = ?', (subscription_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                sms_remaining = row['sms_remaining']

            if sms_remaining < count:
                return False

            conn.execute('''
                UPDATE user_subscriptions SET sms_remaining = sms_remaining - ? WHERE id = ?
            ''', (count, subscription_id))

            usage_log = SMSUsageLog(
                username=username,
                provider=provider,
                subscription_id=subscription_id,
                messages_sent=count,
                sms_charged=count,
                operation_type=UsageOperationType.SEND,
                reference=reference or '',
                notes=f'استهلاك {count} رسالة'
            )
            SMSUsageLogRepository()._insert_log(conn, usage_log)
            return True

    def refund_sms(self, username: str, count: int, provider: str = 'yemen_mobile',
                   subscription_id: int = None, reference: str = None) -> bool:
        if count <= 0:
            return False
        username = (username or 'default').strip() or 'default'

        with db_manager.get_connection() as conn:
            if not subscription_id:
                cursor = conn.execute('''
                    SELECT id, sms_allocated FROM user_subscriptions
                    WHERE username = ? AND provider = ? AND status = ?
                    ORDER BY subscription_date DESC LIMIT 1
                ''', (username, provider, SubscriptionStatus.ACTIVE))
                row = cursor.fetchone()
                if not row:
                    return False
                subscription_id = row['id']
                sms_allocated = row['sms_allocated']
            else:
                cursor = conn.execute('SELECT sms_allocated FROM user_subscriptions WHERE id = ?', (subscription_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                sms_allocated = row['sms_allocated']

            conn.execute('''
                UPDATE user_subscriptions
                SET sms_remaining = MIN(sms_remaining + ?, ?)
                WHERE id = ?
            ''', (count, sms_allocated, subscription_id))

            usage_log = SMSUsageLog(
                username=username,
                provider=provider,
                subscription_id=subscription_id,
                sms_charged=-count,
                operation_type=UsageOperationType.REFUND,
                reference=reference or '',
                notes=f'إرجاع {count} رسالة'
            )
            SMSUsageLogRepository()._insert_log(conn, usage_log)
            return True

    def get_all_subscriptions(self, username: str, provider: str = None) -> List[UserSubscription]:
        username = (username or 'default').strip() or 'default'
        with db_manager.get_connection() as conn:
            query = 'SELECT * FROM user_subscriptions WHERE username = ?'
            params = [username]
            if provider:
                query += ' AND provider = ?'
                params.append(provider)
            query += ' ORDER BY subscription_date DESC'
            cursor = conn.execute(query, params)
            return [self._row_to_sub(dict(r)) for r in cursor.fetchall()]

    def _mark_expired(self, subscription_id: int):
        with db_manager.get_connection() as conn:
            conn.execute('UPDATE user_subscriptions SET status = ? WHERE id = ?',
                         (SubscriptionStatus.EXPIRED, subscription_id))

    def _row_to_sub(self, row: dict) -> UserSubscription:
        return UserSubscription(
            id=row.get('id', 0),
            username=row.get('username', ''),
            package_id=row.get('package_id', 0),
            provider=row.get('provider', 'yemen_mobile'),
            sms_allocated=row.get('sms_allocated', 0),
            sms_remaining=row.get('sms_remaining', 0),
            total_cost=row.get('total_cost', 0.0),
            subscription_date=datetime.fromisoformat(row['subscription_date']) if row.get('subscription_date') else None,
            expiry_date=datetime.fromisoformat(row['expiry_date']) if row.get('expiry_date') else None,
            status=row.get('status', SubscriptionStatus.ACTIVE),
        )


class SMSUsageLogRepository:
    """مستودع سجل الاستهلاك"""

    def _insert_log(self, conn, log: SMSUsageLog) -> int:
        cursor = conn.execute('''
            INSERT INTO sms_usage_log (
                username, provider, subscription_id, messages_sent,
                sms_charged, operation_type, amount, reference, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log.username, log.provider, log.subscription_id, log.messages_sent,
            log.sms_charged, log.operation_type, log.amount, log.reference,
            log.notes, datetime.now()
        ))
        return cursor.lastrowid

    def add_log(self, log: SMSUsageLog) -> int:
        with db_manager.get_connection() as conn:
            return self._insert_log(conn, log)

    def get_usage_history(self, username: str, provider: str = None,
                          limit: int = 50) -> List[SMSUsageLog]:
        username = (username or 'default').strip() or 'default'
        with db_manager.get_connection() as conn:
            query = 'SELECT * FROM sms_usage_log WHERE username = ?'
            params = [username]
            if provider:
                query += ' AND provider = ?'
                params.append(provider)
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            cursor = conn.execute(query, params)
            return [self._row_to_log(dict(r)) for r in cursor.fetchall()]

    def _row_to_log(self, row: dict) -> SMSUsageLog:
        return SMSUsageLog(
            id=row.get('id', 0),
            username=row.get('username', ''),
            provider=row.get('provider', 'yemen_mobile'),
            subscription_id=row.get('subscription_id'),
            messages_sent=row.get('messages_sent', 0),
            sms_charged=row.get('sms_charged', 0),
            operation_type=row.get('operation_type', UsageOperationType.SEND),
            amount=row.get('amount', 0.0),
            reference=row.get('reference', ''),
            notes=row.get('notes', ''),
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
        )


# كائنات عامة
message_repo = MessageRepository()
provider_settings_repo = ProviderSettingsRepository()
operation_repo = OperationRepository()
sms_package_repo = SMSPackageRepository()
user_subscription_repo = UserSubscriptionRepository()
sms_usage_log_repo = SMSUsageLogRepository()
