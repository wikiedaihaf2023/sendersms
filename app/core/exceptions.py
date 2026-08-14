"""
استثناءات التطبيق المخصصة
"""


class MessageFlowException(Exception):
    """الاستثناء الأساسي للتطبيق"""


class ConfigurationError(MessageFlowException):
    """خطأ في الإعدادات (مفاتيح API غير مكتملة وغيرها)"""


class MessageSendError(MessageFlowException):
    """خطأ في إرسال الرسائل"""


class ValidationError(MessageFlowException):
    """خطأ في التحقق من البيانات"""


class ExcelFileError(MessageFlowException):
    """خطأ في قراءة ملف الإكسل"""
