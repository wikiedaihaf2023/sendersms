"""
واجهة سطر الأوامر للبرنامج
"""
import argparse
import sys
from pathlib import Path

# إضافة المسار إلى النظام للاستيراد
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logger import logger
from app.core.config import settings
from app.core.automation import AutomationEngine
from app.services.excel_service import excel_service
from app.database.db_manager import db_manager
from app.database.repositories import message_repo


def create_parser() -> argparse.ArgumentParser:
    """إنشاء محلل الوسائط"""
    parser = argparse.ArgumentParser(
        prog='MessageFlow Pro',
        description='نظام إرسال رسائل SMS وواتس آب جماعية احترافي',
        epilog='مثال: python run.py -f data/contacts.xlsx'
    )

    parser.add_argument(
        '-f', '--file',
        type=str,
        help='مسار ملف الإكسل المراد معالجته'
    )

    parser.add_argument(
        '--no-sms',
        action='store_true',
        help='تعطيل إرسال SMS'
    )

    parser.add_argument(
        '--no-whatsapp',
        action='store_true',
        help='تعطيل إرسال واتس آب'
    )

    parser.add_argument(
        '--parallel',
        action='store_true',
        help='استخدام المعالجة المتوازية'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='عدد العمال المتوازيين (افتراضي: 5)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='وضع التجربة - بدون إرسال فعلي'
    )

    parser.add_argument(
        '--template',
        action='store_true',
        help='إنشاء قالب إكسل فارغ'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='عرض إحصائيات قاعدة البيانات'
    )

    parser.add_argument(
        '--retry-failed',
        action='store_true',
        help='إعادة محاولة الرسائل الفاشلة'
    )

    parser.add_argument(
        '--backup-db',
        action='store_true',
        help='إنشاء نسخة احتياطية من قاعدة البيانات'
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {settings.app_version}'
    )

    return parser


def run_send(args):
    """تشغيل عملية الإرسال"""
    if not args.file:
        logger.error("يجب تحديد ملف الإكسل باستخدام -f أو --file")
        return 1

    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"الملف غير موجود: {file_path}")
        return 1

    try:
        engine = AutomationEngine(
            excel_file=str(file_path),
            send_sms=not args.no_sms,
            send_whatsapp=not args.no_whatsapp,
            parallel=args.parallel,
            max_workers=args.max_workers,
            dry_run=args.dry_run
        )

        engine.run()
        return 0

    except Exception as e:
        logger.error(f"فشلت العملية: {str(e)}")
        return 1


def create_template():
    """إنشاء قالب إكسل"""
    try:
        path = excel_service.create_template()
        logger.success(f"تم إنشاء القالب: {path}")
        return 0
    except Exception as e:
        logger.error(f"فشل إنشاء القالب: {str(e)}")
        return 1


def show_stats():
    """عرض الإحصائيات"""
    try:
        stats = db_manager.get_statistics()

        logger.section("إحصائيات النظام")

        logger.info("رسائل:")
        for msg_type, statuses in stats['messages'].items():
            logger.info(f"  {msg_type}:")
            for status, count in statuses.items():
                logger.info(f"    {status}: {count}")

        logger.info("العمليات:")
        for op_type, data in stats['operations'].items():
            logger.info(f"  {op_type}:")
            logger.info(f"    عدد العمليات: {data['total_operations']}")
            logger.info(f"    إجمالي السجلات: {data['total_records']}")
            logger.info(f"    نجاح: {data['total_success']}")
            logger.info(f"    فشل: {data['total_failed']}")

        logger.info(f"إجمالي جهات الاتصال الفريدة: {stats['unique_contact_count']}")

        return 0
    except Exception as e:
        logger.error(f"فشل عرض الإحصائيات: {str(e)}")
        return 1


def retry_failed():
    """إعادة محاولة الرسائل الفاشلة"""
    try:
        failed = message_repo.get_failed_messages()
        logger.info(f"وجدت {len(failed)} رسالة فاشلة")

        if failed:
            logger.info("الرسائل الفاشلة:")
            for msg in failed[:20]:
                logger.info(
                    f"  {msg.get('contact_phone')} "
                    f"({msg.get('message_type')}): {msg.get('error_message')}"
                )
            logger.info(
                "لإعادة الإرسال، أعد تشغيل الأمر مع نفس ملف الإكسل — "
                "سيتم إرسال الأرقام التي فشلت فقط."
            )

        return 0
    except Exception as e:
        logger.error(f"فشل إعادة المحاولة: {str(e)}")
        return 1


def backup_database():
    """إنشاء نسخة احتياطية"""
    try:
        path = db_manager.backup_database()
        logger.success(f"تم إنشاء النسخة الاحتياطية: {path}")
        return 0
    except Exception as e:
        logger.error(f"فشل النسخ الاحتياطي: {str(e)}")
        return 1


def main():
    """الدالة الرئيسية"""
    parser = create_parser()
    args = parser.parse_args()

    # عرض الترحيب
    logger.section(f"{settings.app_name} v{settings.app_version}")

    # تحديد العملية
    if args.template:
        return create_template()
    elif args.stats:
        return show_stats()
    elif args.retry_failed:
        return retry_failed()
    elif args.backup_db:
        return backup_database()
    elif args.file:
        return run_send(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
