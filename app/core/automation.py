"""
محرك الأتمتة الرئيسي - تنسيق عملية الإرسال الكاملة
"""
import time
import threading
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.logger import logger
from app.core.config import settings
from app.core.exceptions import MessageFlowException
from app.models.contact import Contact
from app.models.message import Message, MessageType
from app.services.excel_service import excel_service
from app.services.validator_service import validator_service
from app.services.sms_service import SMSService
from app.services.sms_gateway_service import GenericHTTPGatewayService
from app.services.whatsapp_service import whatsapp_service
from app.services.billing_service import billing_service
from app.database.repositories import message_repo, operation_repo


class AutomationEngine:
    """محرك الإرسال الآلي"""

    def __init__(
        self,
        excel_file: str,
        send_sms: bool = True,
        send_whatsapp: bool = True,
        parallel: bool = False,
        max_workers: int = 5,
        dry_run: bool = False,
        username: str = 'default'
    ):
        """
        تهيئة المحرك

        Args:
            excel_file: مسار ملف الإكسل
            send_sms: تفعيل إرسال SMS
            send_whatsapp: تفعيل إرسال واتس آب
            parallel: استخدام المعالجة المتوازية
            max_workers: عدد العمال المتوازيين
            dry_run: وضع التجربة (بدون إرسال فعلي)
            username: اسم المستخدم الحالي للتحقق من الرصيد والفوترة
        """
        self.excel_file = excel_file
        self.send_sms = send_sms
        self.send_whatsapp = send_whatsapp
        self.parallel = parallel
        self.max_workers = max_workers
        self.dry_run = dry_run
        self.username = (username or 'default').strip() or 'default'

        self.contacts: List[Contact] = []
        self.valid_contacts: List[Contact] = []
        self.invalid_contacts: List[Contact] = []
        self.sms_service = self._resolve_sms_service()

        self.stats = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'sms_sent': 0,
            'sms_failed': 0,
            'sms_skipped_duplicate': 0,
            'whatsapp_sent': 0,
            'whatsapp_failed': 0,
            'whatsapp_skipped_duplicate': 0,
            'balance_error': '',
            'error_contacts': [],
            'report_rows': []
        }
        self._stats_lock = threading.Lock()

        # التحقق من توفر الخدمات (باستثناء وضع التجربة الذي لا يُرسل فعلياً)
        if not self.dry_run:
            if send_sms and not self.sms_service:
                logger.warning("خدمة SMS غير متاحة، سيتم تجاهل إرسال SMS")
                self.send_sms = False
            if send_whatsapp and not whatsapp_service:
                logger.warning("خدمة واتس آب غير متاحة، سيتم تجاهل إرسال واتس آب")
                self.send_whatsapp = False

            # إذا كان المستخدم قد عطّل كلا الخدمتين صراحةً، فلا يعتبر هذا خطأ
            if not send_sms and not send_whatsapp:
                logger.info("لا توجد خدمات إرسال مفعلة من قبل المستخدم، سيتم إنهاء العملية دون إرسال")
                self.send_sms = False
                self.send_whatsapp = False
                return

            if not self.send_sms and not self.send_whatsapp:
                raise MessageFlowException("لا توجد خدمات إرسال مفعلة")

    def run(self) -> Dict:
        """
        تشغيل العملية الكاملة

        Returns:
            قاموس بالإحصائيات النهائية
        """
        operation_id = operation_repo.start_operation('send_messages')
        start_time = time.time()

        try:
            logger.section("بدء عملية الإرسال")
            logger.info(f"ملف الإكسل: {self.excel_file}")
            logger.info(f"إرسال SMS: {self.send_sms}")
            logger.info(f"إرسال واتس آب: {self.send_whatsapp}")
            logger.info(f"وضع التجربة: {self.dry_run}")

            # 1. قراءة الملف
            self._load_contacts()

            # 2. التحقق من البيانات
            self._validate_contacts()

            # 3. التحقق من رصيد الباقة قبل الإرسال (فقط إذا كان إرسال SMS مفعلاً)
            if self.send_sms and not self.dry_run:
                sms_to_send = len(self.valid_contacts)
                if sms_to_send > 0:
                    balance = billing_service.check_balance(
                        username=self.username,
                        required_count=sms_to_send,
                        provider=settings.sms.provider
                    )
                    if not balance.ok:
                        error_msg = (
                            f"لا يمكن بدء الإرسال - {balance.message}. "
                            f"يرجى الاشتراك في باقة كافية قبل المتابعة."
                        )
                        logger.error(error_msg)
                        self.stats['balance_error'] = balance.message
                        self._generate_summary(elapsed_time=0)
                        return self.stats

                    logger.info(
                        f"فحص الرصيد: {balance.remaining} رسالة متاحة، "
                        f"المطلوب: {sms_to_send} - الحالة: جيد ✓"
                    )

            # 4. إرسال الرسائل
            if self.valid_contacts:
                if self.parallel:
                    self._send_messages_parallel()
                else:
                    self._send_messages_sequential()
            else:
                logger.warning("لا توجد جهات اتصال صالحة للإرسال")

            # 4. تلخيص النتائج
            elapsed_time = time.time() - start_time
            self._generate_summary(elapsed_time)

            # 5. حفظ النتائج
            self._export_results()

            # 6. إنهاء العملية
            operation_repo.finish_operation(
                operation_id,
                total_records=self.stats['total'],
                success_count=self.stats['sms_sent'] + self.stats['whatsapp_sent'],
                failed_count=self.stats['sms_failed'] + self.stats['whatsapp_failed'],
                details=f"Elapsed: {elapsed_time:.2f}s"
            )

            return self.stats

        except Exception as e:
            logger.log_exception(e)
            operation_repo.finish_operation(
                operation_id,
                total_records=self.stats['total'],
                success_count=0,
                failed_count=0,
                details=f"Error: {str(e)}"
            )
            raise

    def _resolve_sms_service(self):
        """حل الخدمة الفعالة بناءً على المزود الحالي في الإعدادات."""
        provider = (settings.sms.provider or '').strip().lower()

        if provider in {'yemen_mobile', 'sapa_phone', 'you'}:
            if settings.sms.is_provider_configured(provider):
                return GenericHTTPGatewayService(provider)

        if provider == 'twilio' and settings.twilio.is_sms_configured():
            return SMSService()

        if settings.sms.is_yemen_mobile_configured():
            return GenericHTTPGatewayService('yemen_mobile')
        if settings.sms.is_sapa_phone_configured():
            return GenericHTTPGatewayService('sapa_phone')
        if settings.sms.is_you_configured():
            return GenericHTTPGatewayService('you')
        if settings.twilio.is_sms_configured():
            return SMSService()

        return None

    def _load_contacts(self):
        """قراءة البيانات من ملف الإكسل"""
        logger.section("قراءة البيانات")

        try:
            self.contacts = excel_service.read_file(self.excel_file)
            self.stats['total'] = len(self.contacts)
            logger.info(f"تم قراءة {len(self.contacts)} جهة اتصال")

            # عرض معاينة
            if self.contacts:
                first = self.contacts[0]
                logger.debug(
                    "مثال على أول سجل",
                    phone=first.phone_number,
                    name=first.name or "غير متوفر",
                    passport=first.passport_number or "غير متوفر"
                )
        except Exception as e:
            logger.error(f"فشل قراءة الملف: {str(e)}")
            raise

    def _validate_contacts(self):
        """التحقق من صحة جهات الاتصال"""
        logger.section("التحقق من البيانات")

        for i, contact in enumerate(self.contacts):
            # تحديث مؤشر التقدم كل 10 سجلات
            if (i + 1) % 10 == 0 or (i + 1) == len(self.contacts):
                logger.progress(i + 1, len(self.contacts), "جاري التحقق")

            validated = validator_service.validate_contact(contact)

            if validated.is_valid:
                self.valid_contacts.append(validated)
            else:
                self.invalid_contacts.append(validated)

        self.stats['valid'] = len(self.valid_contacts)
        self.stats['invalid'] = len(self.invalid_contacts)

        logger.success(f"تحقق ناجح: {len(self.valid_contacts)}")
        logger.warning(f"تحقق فاشل: {len(self.invalid_contacts)}")

        if self.invalid_contacts:
            logger.info("أمثلة على الأرقام غير الصالحة:")
            for c in self.invalid_contacts[:3]:
                logger.info(
                    f"  - {c.phone_number} -> {c.error_message} (صف {c.row_number})"
                )

    def _send_messages_sequential(self):
        """إرسال الرسائل بالتسلسل"""
        logger.section("إرسال الرسائل")

        total_operations = len(self.valid_contacts) * (
            (1 if self.send_sms else 0) + (1 if self.send_whatsapp else 0)
        )
        completed = 0

        for i, contact in enumerate(self.valid_contacts):
            logger.info(f"\n--- معالجة {i + 1}/{len(self.valid_contacts)}: {contact.display_phone} ---")

            if self.send_sms:
                completed += 1
                self._send_sms_for_contact(contact)
                logger.progress(completed, total_operations, "جاري الإرسال")

            if self.send_whatsapp:
                completed += 1
                self._send_whatsapp_for_contact(contact)
                logger.progress(completed, total_operations, "جاري الإرسال")

            # تأخير بين الأرقام
            if i < len(self.valid_contacts) - 1:
                time.sleep(settings.rate_limit.delay_between_messages)

    def _send_messages_parallel(self):
        """إرسال الرسائل بالتوازي"""
        logger.section("إرسال الرسائل (متوازي)")
        logger.info(f"عدد العمال: {self.max_workers}")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for contact in self.valid_contacts:
                if self.send_sms:
                    futures.append(executor.submit(self._send_sms_for_contact, contact))
                if self.send_whatsapp:
                    futures.append(executor.submit(self._send_whatsapp_for_contact, contact))

            for idx, future in enumerate(as_completed(futures)):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"خطأ في أحد المهام: {str(e)}")

                logger.progress(idx + 1, len(futures), "جاري الإرسال")

    def _send_sms_for_contact(self, contact: Contact):
        """إرسال SMS لجهة اتصال واحدة"""
        # تحضير محتوى الرسالة
        content = self._prepare_message_content(contact)

        # التحقق من التكرار
        if not self.dry_run and message_repo.is_already_sent(contact.formatted_phone, 'sms'):
            logger.info(f"تخطي SMS (مكرر): {contact.display_phone}")
            with self._stats_lock:
                self.stats['sms_skipped_duplicate'] += 1
            return

        if self.dry_run:
            logger.info(f"[DRY-RUN] سيتم إرسال SMS إلى {contact.display_phone}")
            with self._stats_lock:
                self.stats['sms_sent'] += 1
                self.stats['report_rows'].append({
                    'name': contact.name or 'غير محدد',
                    'phone': contact.formatted_phone,
                    'type': 'SMS',
                    'status': 'dry_run',
                    'provider': settings.sms.provider,
                    'message': 'تجربة فقط - لم يتم الإرسال الفعلي',
                    'error': ''
                })
            return

        # خصم رسالة واحدة من الباقة قبل الإرسال (ضمان عدم تجاوز الرصيد)
        consumed = billing_service.consume_messages(
            username=self.username,
            count=1,
            provider=settings.sms.provider,
            reference=f'SMS-{contact.formatted_phone}'
        )
        if not consumed:
            logger.warning(f"لا يوجد رصيد كافي لإرسال SMS إلى {contact.display_phone} - تم إيقاف الإرسال")
            with self._stats_lock:
                self.stats['sms_failed'] += 1
                self.stats['balance_error'] = self.stats.get('balance_error') or 'نفذ رصيد الباقة أثناء الإرسال'
                self.stats['error_contacts'].append({
                    'phone': contact.formatted_phone,
                    'type': 'sms',
                    'error': 'نفذ رصيد الباقة أثناء الإرسال'
                })
                self.stats['report_rows'].append({
                    'name': contact.name or 'غير محدد',
                    'phone': contact.formatted_phone,
                    'type': 'SMS',
                    'status': 'failed',
                    'provider': settings.sms.provider,
                    'message': content,
                    'error': 'نفذ رصيد الباقة - يرجى تجديد الاشتراك'
                })
            message_repo.log_message(
                contact_phone=contact.formatted_phone,
                formatted_phone=contact.formatted_phone,
                contact_name=contact.name,
                passport_number=contact.passport_number,
                message_type='sms',
                message_content=content,
                status='failed',
                error_message='نفذ رصيد الباقة',
                retry_count=0
            )
            return

        # إنشاء كائن الرسالة
        message = Message(
            contact_phone=contact.formatted_phone,
            contact_name=contact.name,
            passport_number=contact.passport_number,
            message_type=MessageType.SMS,
            content=content
        )

        # الإرسال
        result = self.sms_service.send(message)

        # تسجيل النتيجة
        if result.is_sent:
            with self._stats_lock:
                self.stats['sms_sent'] += 1
                self.stats['report_rows'].append({
                    'name': contact.name or 'غير محدد',
                    'phone': contact.formatted_phone,
                    'type': 'SMS',
                    'status': 'success',
                    'provider': result.provider or settings.sms.provider,
                    'message': content,
                    'error': ''
                })
            message_repo.log_message(
                contact_phone=contact.formatted_phone,
                formatted_phone=contact.formatted_phone,
                contact_name=contact.name,
                passport_number=contact.passport_number,
                message_type='sms',
                message_content=content,
                status='success',
                message_id=result.message_id,
                provider=result.provider
            )
        else:
            # إرجاع الرسالة للباقة بسبب الفشل
            billing_service.refund_messages(
                username=self.username,
                count=1,
                provider=settings.sms.provider,
                reference=f'REFUND-{contact.formatted_phone}'
            )
            with self._stats_lock:
                self.stats['sms_failed'] += 1
                self.stats['error_contacts'].append({
                    'phone': contact.formatted_phone,
                    'type': 'sms',
                    'error': result.error
                })
                self.stats['report_rows'].append({
                    'name': contact.name or 'غير محدد',
                    'phone': contact.formatted_phone,
                    'type': 'SMS',
                    'status': 'failed',
                    'provider': result.provider or settings.sms.provider,
                    'message': content,
                    'error': result.error
                })
            message_repo.log_message(
                contact_phone=contact.formatted_phone,
                formatted_phone=contact.formatted_phone,
                contact_name=contact.name,
                passport_number=contact.passport_number,
                message_type='sms',
                message_content=content,
                status='failed',
                error_message=result.error,
                retry_count=result.retry_count
            )

    def _send_whatsapp_for_contact(self, contact: Contact):
        """إرسال واتس آب لجهة اتصال واحدة"""
        content = self._prepare_message_content(contact)

        if not self.dry_run and message_repo.is_already_sent(contact.formatted_phone, 'whatsapp'):
            logger.info(f"تخطي واتس آب (مكرر): {contact.display_phone}")
            with self._stats_lock:
                self.stats['whatsapp_skipped_duplicate'] += 1
            return

        if self.dry_run:
            logger.info(f"[DRY-RUN] سيتم إرسال واتس آب إلى {contact.display_phone}")
            with self._stats_lock:
                self.stats['whatsapp_sent'] += 1
                self.stats['report_rows'].append({
                    'name': contact.name or 'غير محدد',
                    'phone': contact.formatted_phone,
                    'type': 'واتس آب',
                    'status': 'dry_run',
                    'provider': settings.sms.provider,
                    'message': 'تجربة فقط - لم يتم الإرسال الفعلي',
                    'error': ''
                })
            return

        message = Message(
            contact_phone=contact.formatted_phone,
            contact_name=contact.name,
            passport_number=contact.passport_number,
            message_type=MessageType.WHATSAPP,
            content=content
        )

        result = whatsapp_service.send(message)

        if result.is_sent:
            with self._stats_lock:
                self.stats['whatsapp_sent'] += 1
                self.stats['report_rows'].append({
                    'name': contact.name or 'غير محدد',
                    'phone': contact.formatted_phone,
                    'type': 'واتس آب',
                    'status': 'success',
                    'provider': result.provider or settings.sms.provider,
                    'message': content,
                    'error': ''
                })
            message_repo.log_message(
                contact_phone=contact.formatted_phone,
                formatted_phone=contact.formatted_phone,
                contact_name=contact.name,
                passport_number=contact.passport_number,
                message_type='whatsapp',
                message_content=content,
                status='success',
                message_id=result.message_id,
                provider=result.provider
            )
        else:
            with self._stats_lock:
                self.stats['whatsapp_failed'] += 1
                self.stats['error_contacts'].append({
                    'phone': contact.formatted_phone,
                    'type': 'whatsapp',
                    'error': result.error
                })
                self.stats['report_rows'].append({
                    'name': contact.name or 'غير محدد',
                    'phone': contact.formatted_phone,
                    'type': 'واتس آب',
                    'status': 'failed',
                    'provider': result.provider or settings.sms.provider,
                    'message': content,
                    'error': result.error
                })
            message_repo.log_message(
                contact_phone=contact.formatted_phone,
                formatted_phone=contact.formatted_phone,
                contact_name=contact.name,
                passport_number=contact.passport_number,
                message_type='whatsapp',
                message_content=content,
                status='failed',
                error_message=result.error,
                retry_count=result.retry_count
            )

    def _prepare_message_content(self, contact: Contact) -> str:
        """تحضير نص الرسالة المخصص"""
        if settings.message.enable_personalization:
            if contact.name and contact.passport_number:
                return settings.message.personalized_template.format(
                    name=contact.name,
                    passport=contact.passport_number
                )
            elif contact.name:
                return f"مرحباً {contact.name}، {settings.message.default_message}"

        return settings.message.default_message

    def _generate_summary(self, elapsed_time: float):
        """توليد ملخص نهائي"""
        logger.section("ملخص العملية")
        logger.info(f"الوقت المستغرق: {elapsed_time:.2f} ثانية")
        logger.info(f"إجمالي جهات الاتصال: {self.stats['total']}")
        logger.info(f"جهات صالحة: {self.stats['valid']}")
        logger.info(f"جهات غير صالحة: {self.stats['invalid']}")

        if self.send_sms:
            logger.info(f"SMS - تم الإرسال: {self.stats['sms_sent']}")
            logger.info(f"SMS - فشل: {self.stats['sms_failed']}")
            logger.info(f"SMS - تم تخطيها (مكررة): {self.stats['sms_skipped_duplicate']}")

        if self.send_whatsapp:
            logger.info(f"واتس آب - تم الإرسال: {self.stats['whatsapp_sent']}")
            logger.info(f"واتس آب - فشل: {self.stats['whatsapp_failed']}")
            logger.info(f"واتس آب - تم تخطيها (مكررة): {self.stats['whatsapp_skipped_duplicate']}")

        if self.stats['error_contacts']:
            logger.warning("أخطاء تفصيلية:")
            for err in self.stats['error_contacts'][:10]:
                logger.warning(
                    f"  {err['phone']} ({err['type']}): {err['error']}"
                )

    def _export_results(self):
        """تصدير النتائج إلى ملف إكسل"""
        try:
            # إضافة الحالة إلى جهات الاتصال
            all_contacts = self.valid_contacts + self.invalid_contacts
            excel_service.export_results(all_contacts)
        except Exception as e:
            logger.error(f"فشل تصدير النتائج: {str(e)}")

    def get_failed_contacts_summary(self) -> List[Dict]:
        """الحصول على ملخص جهات الاتصال الفاشلة"""
        return self.stats['error_contacts']
