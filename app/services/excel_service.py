"""
خدمة قراءة وكتابة ملفات الإكسل
"""
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import pandas as pd

from app.core.config import BASE_DIR
from app.core.logger import logger
from app.models.contact import Contact


class ExcelService:
    """خدمة التعامل مع ملفات الإكسل"""

    # أسماء الأعمدة المقبولة (عربي + إنجليزي) — تُخزَّن بالأحرف الصغيرة للمطابقة
    PHONE_COLUMNS = {
        'رقم الهاتف', 'الهاتف', 'الجوال', 'رقم الجوال', 'رقم الموبايل',
        'phone', 'phone_number', 'phone number', 'mobile', 'mobile_number',
        'contact_number', 'phonenumber'
    }
    NAME_COLUMNS = {
        'اسم صاحب الجواز', 'الاسم', 'اسم', 'الاسم الكامل',
        'name', 'full_name', 'fullname', 'contact_name', 'customer_name'
    }
    PASSPORT_COLUMNS = {
        'رقم الجواز', 'جواز السفر', 'رقم جواز السفر', 'رقم جواز',
        'passport', 'passport_number', 'passport_no', 'passport number'
    }

    def read_file(self, file_path: str) -> List[Contact]:
        """قراءة جهات الاتصال من ملف إكسل"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"الملف غير موجود: {file_path}")

        engine = 'xlrd' if path.suffix.lower() == '.xls' else None
        df = pd.read_excel(path, dtype=str, engine=engine)
        df.columns = [str(c).strip() for c in df.columns]

        phone_col, name_col, passport_col = self._resolve_columns(list(df.columns))

        if phone_col is None:
            raise ValueError(
                "لم يتم العثور على عمود رقم الهاتف. الأعمدة المتوقعة: "
                "'رقم الهاتف' أو 'phone'."
            )

        contacts: List[Contact] = []
        for idx, row in df.iterrows():
            phone = self._clean_value(row.get(phone_col))
            if not phone:
                continue
            name = self._clean_value(row.get(name_col)) if name_col else None
            passport = self._clean_value(row.get(passport_col)) if passport_col else None

            contacts.append(Contact(
                phone_number=phone,
                name=name or None,
                passport_number=passport or None,
                row_number=idx + 2  # صفوف الإكسل تبدأ من 1، والأول للعناوين
            ))

        return contacts

    def _resolve_columns(self, columns: List[str]):
        """تحديد أعمدة الهاتف والاسم والجواز من قائمة الأعمدة"""
        lower_cols = {c: c.lower() for c in columns}
        phone = name = passport = None
        used = set()

        # 1) مطابقة تامة
        for col, cl in lower_cols.items():
            if cl in self.PHONE_COLUMNS:
                phone, used = col, used | {col}
                break
        for col, cl in lower_cols.items():
            if col not in used and cl in self.PASSPORT_COLUMNS:
                passport, used = col, used | {col}
                break
        for col, cl in lower_cols.items():
            if col not in used and cl in self.NAME_COLUMNS:
                name, used = col, used | {col}
                break

        # 2) مطابقة جزئية لما تبقى
        if phone is None:
            for col, cl in lower_cols.items():
                if any(t in cl for t in ('هاتف', 'جوال', 'phone', 'mobile')):
                    phone, used = col, used | {col}
                    break
        if passport is None:
            for col, cl in lower_cols.items():
                if col not in used and any(t in cl for t in ('جواز', 'passport')):
                    passport, used = col, used | {col}
                    break
        if name is None:
            for col, cl in lower_cols.items():
                if col not in used and any(t in cl for t in ('اسم', 'name')):
                    name, used = col, used | {col}
                    break

        return phone, name, passport

    def _clean_value(self, value) -> str:
        """تنظيف قيمة الخلية (تحويل الأرقام الطويلة إلى نص صحيح)"""
        if value is None:
            return ''
        s = str(value).strip()
        # pandas قد تقرأ رقم الهاتف كـ float مثل 501234567.0
        if s.endswith('.0') and s[:-2].isdigit():
            s = s[:-2]
        return s

    def export_results(self, contacts: List[Contact]) -> str:
        """تصدير نتائج المعالجة إلى ملف إكسل"""
        out_dir = BASE_DIR / 'data' / 'results'
        out_dir.mkdir(parents=True, exist_ok=True)

        rows = []
        for c in contacts:
            rows.append({
                'رقم الهاتف': c.phone_number,
                'الرقم بصيغة دولية': c.formatted_phone or '',
                'الاسم': c.name or '',
                'رقم الجواز': c.passport_number or '',
                'الحالة': 'صحيح' if c.is_valid else 'غير صحيح',
                'ملاحظة': c.error_message or '',
                'الصف': c.row_number,
            })

        result_df = pd.DataFrame(rows)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = out_dir / f'results_{timestamp}.xlsx'
        result_df.to_excel(out_path, index=False)
        logger.success(f"تم تصدير النتائج إلى: {out_path}")
        return str(out_path)

    def create_template(self) -> str:
        """إنشاء قالب إكسل فارغ مع مثال توضيحي"""
        out_dir = BASE_DIR / 'data'
        out_dir.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame({
            'رقم الهاتف': ['0501234567', '+966512345678'],
            'اسم صاحب الجواز': ['محمد أحمد', 'فاطمة علي'],
            'رقم الجواز': ['A1234567', 'B7654321'],
        })

        out_path = out_dir / 'contacts_template.xlsx'
        df.to_excel(out_path, index=False)
        return str(out_path)


# كائن عام من الخدمة
excel_service = ExcelService()
