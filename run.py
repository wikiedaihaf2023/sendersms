#!/usr/bin/env python3
"""
نقطة الدخول الرئيسية للتطبيق
"""

import sys
from pathlib import Path

# إضافة المسار الجذر إلى PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from cli.main import main

if __name__ == '__main__':
    sys.exit(main())
