"""
اختبارات خدمة التحقق
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.validator_service import ValidatorService


class TestPhoneValidator(unittest.TestCase):

    def setUp(self):
        self.validator = ValidatorService()

    def test_valid_saudi_mobile(self):
        """اختبار رقم سعودي صحيح"""
        is_valid, formatted, error = self.validator.validate_phone_number('0501234567')
        self.assertTrue(is_valid)
        self.assertEqual(formatted, '+966501234567')
        self.assertIsNone(error)

    def test_invalid_phone(self):
        """اختبار رقم غير صحيح"""
        is_valid, formatted, error = self.validator.validate_phone_number('123')
        self.assertFalse(is_valid)
        self.assertIsNone(formatted)
        self.assertIsNotNone(error)

    def test_international_format(self):
        """اختبار رقم بصيغة دولية"""
        is_valid, formatted, error = self.validator.validate_phone_number('+966501234567')
        self.assertTrue(is_valid)
        self.assertEqual(formatted, '+966501234567')

    def test_empty_phone(self):
        """اختبار رقم فارغ"""
        is_valid, formatted, error = self.validator.validate_phone_number('')
        self.assertFalse(is_valid)
        self.assertIsNone(formatted)
        self.assertEqual(error, 'رقم فارغ')


if __name__ == '__main__':
    unittest.main()
