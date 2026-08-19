"""
خدمة إدارة الباقات والاشتراكات والفوترة
تحقق من الرصيد قبل الإرسال وتخفيض الرسائل من الباقة
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from app.core.logger import logger
from app.core.config import settings
from app.models.package import SMSPackage, UserSubscription
from app.database.repositories import (
    sms_package_repo,
    user_subscription_repo,
    sms_usage_log_repo,
)


@dataclass
class BalanceCheckResult:
    """نتيجة فحص الرصيد"""
    ok: bool
    provider: str
    remaining: int = 0
    required: int = 0
    shortfall: int = 0
    subscription_id: Optional[int] = None
    message: str = ''


class BillingService:
    """خدمة إدارة الفوترة والباقات والاشتراكات"""

    @staticmethod
    def list_packages(provider: str = 'yemen_mobile') -> List[SMSPackage]:
        """عرض الباقات المتاحة لمزود معين"""
        return sms_package_repo.get_all_packages(provider=provider, only_active=True)

    @staticmethod
    def subscribe_to_package(username: str, package_id: int,
                             provider: str = 'yemen_mobile') -> Optional[UserSubscription]:
        """اشتراك المستخدم في باقة"""
        username = (username or 'default').strip() or 'default'
        package = sms_package_repo.get_package_by_id(package_id)
        if not package:
            logger.warning(f"الباقة غير موجودة: {package_id}")
            return None
        if not package.is_active:
            logger.warning(f"الباقة غير مفعلة: {package_id}")
            return None

        sub = user_subscription_repo.subscribe(username=username, package=package, provider=provider)
        logger.success(
            f"اشتراك جديد - المستخدم: {username} | الباقة: {package.name} "
            f"| الرسائل: {package.sms_count} | المزود: {provider}"
        )
        return sub

    @staticmethod
    def get_subscription_summary(username: str, provider: str = 'yemen_mobile') -> Dict[str, Any]:
        """ملخص الاشتراك الحالي مع الرصيد"""
        username = (username or 'default').strip() or 'default'
        sub = user_subscription_repo.get_active_subscription(username, provider)
        packages = BillingService.list_packages(provider)

        if not sub:
            return {
                'has_active_subscription': False,
                'provider': provider,
                'remaining_sms': 0,
                'allocated_sms': 0,
                'usage_percentage': 0,
                'subscription': None,
                'packages': [BillingService._pkg_to_dict(p) for p in packages],
            }

        return {
            'has_active_subscription': True,
            'provider': provider,
            'remaining_sms': sub.sms_remaining,
            'allocated_sms': sub.sms_allocated,
            'usage_percentage': round(sub.usage_percentage, 1),
            'expiry_date': sub.expiry_date.isoformat() if sub.expiry_date else None,
            'subscription_date': sub.subscription_date.isoformat() if sub.subscription_date else None,
            'total_cost': sub.total_cost,
            'subscription': {
                'id': sub.id,
                'package_id': sub.package_id,
                'sms_remaining': sub.sms_remaining,
                'sms_allocated': sub.sms_allocated,
                'status': sub.status,
            },
            'packages': [BillingService._pkg_to_dict(p) for p in packages],
        }

    @staticmethod
    def check_balance(username: str, required_count: int,
                      provider: str = None) -> BalanceCheckResult:
        """
        فحص الرصيد قبل الإرسال

        Args:
            username: اسم المستخدم
            required_count: عدد الرسائل المطلوب إرسالها
            provider: المزود (يستخدم المزود الحالي من الإعدادات إذا لم يحدد)

        Returns:
            BalanceCheckResult مع نتيجة الفحص
        """
        username = (username or 'default').strip() or 'default'
        provider = provider or settings.sms.provider or 'yemen_mobile'

        if BillingService._is_unlimited_provider(provider):
            return BalanceCheckResult(
                ok=True, provider=provider, remaining=999999,
                required=required_count, shortfall=0,
                message=f'المزود {provider} يدعم إرسال غير محدود'
            )

        sub = user_subscription_repo.get_active_subscription(username, provider)
        if not sub:
            return BalanceCheckResult(
                ok=False, provider=provider, remaining=0,
                required=required_count, shortfall=required_count,
                message=f'لا يوجد اشتراك نشط لـ {provider}. يرجى الاشتراك في باقة.'
            )

        remaining = sub.sms_remaining
        if remaining < required_count:
            return BalanceCheckResult(
                ok=False, provider=provider, remaining=remaining,
                required=required_count, shortfall=required_count - remaining,
                message=(
                    f'الرصيد غير كافي: المطلوب {required_count} رسالة، '
                    f'والمتبقي {remaining} رسالة. العجز: {required_count - remaining} رسالة. '
                    f'يرجى تجديد الاشتراك.'
                ),
                subscription_id=sub.id,
            )

        return BalanceCheckResult(
            ok=True, provider=provider, remaining=remaining,
            required=required_count, shortfall=0,
            message=f'الرصيد كافي: {remaining} رسالة متاحة',
            subscription_id=sub.id,
        )

    @staticmethod
    def consume_messages(username: str, count: int,
                         provider: str = None, reference: str = None) -> bool:
        """
        خصم رسائل من الاشتراك

        Returns:
            True إذا تم الخصم بنجاح، False في حال فشل الخصم
        """
        if count <= 0:
            return True
        username = (username or 'default').strip() or 'default'
        provider = provider or settings.sms.provider or 'yemen_mobile'

        if BillingService._is_unlimited_provider(provider):
            return True

        result = user_subscription_repo.consume_sms(
            username=username, count=count, provider=provider, reference=reference
        )
        if result:
            logger.info(
                f"خصم {count} رسالة من رصيد {username} via {provider} | "
                f"مرجع: {reference or 'N/A'}"
            )
        else:
            logger.error(
                f"فشل خصم {count} رسالة من رصيد {username} via {provider} - الرصيد غير كافي"
            )
        return result

    @staticmethod
    def refund_messages(username: str, count: int,
                        provider: str = None, reference: str = None) -> bool:
        """إرجاع رسائل للاشتراك (للرسائل الفاشلة)"""
        if count <= 0:
            return True
        username = (username or 'default').strip() or 'default'
        provider = provider or settings.sms.provider or 'yemen_mobile'

        if BillingService._is_unlimited_provider(provider):
            return True

        return user_subscription_repo.refund_sms(
            username=username, count=count, provider=provider, reference=reference
        )

    @staticmethod
    def get_usage_history(username: str, provider: str = None,
                          limit: int = 30) -> List[Dict[str, Any]]:
        """سجل الاستهلاك"""
        username = (username or 'default').strip() or 'default'
        logs = sms_usage_log_repo.get_usage_history(username, provider, limit)
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'type': log.operation_type,
                'messages_sent': log.messages_sent,
                'sms_charged': log.sms_charged,
                'amount': log.amount,
                'reference': log.reference,
                'notes': log.notes,
                'provider': log.provider,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            })
        return result

    @staticmethod
    def _is_unlimited_provider(provider: str) -> bool:
        """المزودات التي لا تحتاج إلى باقة (Twilio - الدفع لكل إرسال)"""
        return (provider or '').strip().lower() in {'twilio'}

    @staticmethod
    def _pkg_to_dict(pkg: SMSPackage) -> Dict[str, Any]:
        return {
            'id': pkg.id,
            'name': pkg.name,
            'provider': pkg.provider,
            'sms_count': pkg.sms_count,
            'price': pkg.price,
            'currency': pkg.currency,
            'validity_days': pkg.validity_days,
            'description': pkg.description,
            'price_per_sms': round(pkg.price / pkg.sms_count, 2) if pkg.sms_count > 0 else 0,
        }


billing_service = BillingService()
