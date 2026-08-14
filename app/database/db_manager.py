"""
إدارة قاعدة البيانات باستخدام SQLite (sqlite3 المدمج)
"""
import shutil
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict
from contextlib import contextmanager
from datetime import datetime

from app.core.logger import logger
from app.core.config import settings


class DatabaseManager:
    """مدير قاعدة البيانات (Singleton)"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.db_path = Path(settings.database.path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()
        logger.info(f"تم تهيئة قاعدة البيانات: {self.db_path}")

    @contextmanager
    def get_connection(self):
        """الحصول على اتصال بقاعدة البيانات"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """إنشاء مخطط قاعدة البيانات"""
        schema = '''
        -- جدول الرسائل المرسلة
        CREATE TABLE IF NOT EXISTS sent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_phone TEXT NOT NULL,
            formatted_phone TEXT NOT NULL,
            contact_name TEXT,
            passport_number TEXT,
            message_type TEXT NOT NULL,  -- 'sms' or 'whatsapp'
            message_content TEXT NOT NULL,
            status TEXT NOT NULL,        -- 'success', 'failed', 'pending'
            message_id TEXT,             -- معرف الرسالة من المزود
            provider TEXT,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(contact_phone, message_type)  -- منع التكرار
        );

        -- فهارس لتسريع البحث
        CREATE INDEX IF NOT EXISTS idx_phone_type
            ON sent_messages(contact_phone, message_type);
        CREATE INDEX IF NOT EXISTS idx_status
            ON sent_messages(status);
        CREATE INDEX IF NOT EXISTS idx_sent_at
            ON sent_messages(sent_at);

        -- جدول إعدادات المزودات لكل مستخدم
        CREATE TABLE IF NOT EXISTS provider_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            provider TEXT DEFAULT 'twilio',
            yemen_mobile_url TEXT,
            yemen_mobile_username TEXT,
            yemen_mobile_password TEXT,
            yemen_mobile_sender TEXT,
            yemen_mobile_api_key TEXT,
            sapa_phone_url TEXT,
            sapa_phone_username TEXT,
            sapa_phone_password TEXT,
            sapa_phone_sender TEXT,
            sapa_phone_api_key TEXT,
            you_url TEXT,
            you_username TEXT,
            you_password TEXT,
            you_sender TEXT,
            you_api_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- جدول سجل العمليات
        CREATE TABLE IF NOT EXISTS operation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,  -- 'import', 'send', 'export'
            total_records INTEGER,
            success_count INTEGER,
            failed_count INTEGER,
            details TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP
        );
        '''

        with self.get_connection() as conn:
            conn.executescript(schema)

    def backup_database(self, backup_dir: Optional[Path] = None):
        """إنشاء نسخة احتياطية من قاعدة البيانات"""
        if not backup_dir:
            backup_dir = Path('backups')
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"messageflow_backup_{timestamp}.db"

        # نسخة مباشرة من ملف قاعدة البيانات
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"تم إنشاء نسخة احتياطية: {backup_path}")

        return backup_path

    def cleanup_old_logs(self, days: int = 30):
        """تنظيف السجلات القديمة"""
        cutoff = datetime.now().timestamp() - (days * 86400)
        cutoff_str = datetime.fromtimestamp(cutoff).isoformat()

        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM operation_log WHERE started_at < ?",
                (cutoff_str,)
            )
            logger.info(f"تم حذف {cursor.rowcount} سجل قديم")

    def get_statistics(self) -> Dict:
        """الحصول على إحصائيات شاملة"""
        with self.get_connection() as conn:
            # إحصائيات الرسائل
            message_stats = {}
            cursor = conn.execute('''
                SELECT message_type, status, COUNT(*) as count
                FROM sent_messages
                GROUP BY message_type, status
            ''')
            for row in cursor.fetchall():
                if row['message_type'] not in message_stats:
                    message_stats[row['message_type']] = {}
                message_stats[row['message_type']][row['status']] = row['count']

            # إحصائيات العمليات
            operation_stats = {}
            cursor = conn.execute('''
                SELECT operation_type,
                       COUNT(*) as total_operations,
                       SUM(total_records) as total_records,
                       SUM(success_count) as total_success,
                       SUM(failed_count) as total_failed
                FROM operation_log
                GROUP BY operation_type
            ''')
            for row in cursor.fetchall():
                operation_stats[row['operation_type']] = {
                    'total_operations': row['total_operations'],
                    'total_records': row['total_records'] or 0,
                    'total_success': row['total_success'] or 0,
                    'total_failed': row['total_failed'] or 0
                }

            # إجمالي الرسائل الفريدة
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT contact_phone) as unique_contacts
                FROM sent_messages
                WHERE status = 'success'
            ''')
            unique_contacts = cursor.fetchone()['unique_contacts']

            return {
                'messages': message_stats,
                'operations': operation_stats,
                'unique_contact_count': unique_contacts
            }


# كائن عام من المدير
db_manager = DatabaseManager()
