import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.automation import AutomationEngine


class TestAutomationEngine(unittest.TestCase):
    def test_no_services_enabled_is_allowed_when_user_disables_both(self):
        engine = AutomationEngine(
            excel_file='dummy.xlsx',
            send_sms=False,
            send_whatsapp=False,
            dry_run=False,
        )

        self.assertFalse(engine.send_sms)
        self.assertFalse(engine.send_whatsapp)


if __name__ == '__main__':
    unittest.main()
