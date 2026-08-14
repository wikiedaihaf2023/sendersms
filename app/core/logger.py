"""
نظام تسجيل الأحداث (Logging) مع دعم اللغة العربية والألوان
يكتب إلى الطرفية وإلى ملف سجل يومي في مجلد logs/
"""
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Logger:
    """مسجّل الأحداث العام (Singleton)"""

    COLORS = {
        'DEBUG': '\033[36m',    # سماوي
        'INFO': '\033[37m',     # أبيض
        'SUCCESS': '\033[32m',  # أخضر
        'WARNING': '\033[33m',  # أصفر
        'ERROR': '\033[31m',    # أحمر
        'SECTION': '\033[35m',  # بنفسجي
    }
    RESET = '\033[0m'

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name='messageflow', level=None, log_dir=None):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.name = name
        self.level = (level or os.getenv('LOG_LEVEL', 'INFO')).upper()
        self.log_dir = Path(log_dir) if log_dir else BASE_DIR / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._tty = sys.stdout.isatty()
        self._no_color = os.getenv('NO_COLOR') is not None

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        # معالج الطرفية
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(self._level_number())
        console.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(console)

        # معالج الملف (يومي)
        log_file = self.log_dir / f"messageflow_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        self.logger.addHandler(file_handler)

    def _level_number(self) -> int:
        return getattr(logging, self.level, logging.INFO)

    def _colorize(self, text: str, color: str) -> str:
        if self._no_color or not self._tty:
            return text
        return f"{color}{text}{self.RESET}"

    def _log(self, level: str, msg: str, **kwargs):
        if kwargs:
            extras = ' | ' + ' | '.join(f"{k}={v}" for k, v in kwargs.items())
            msg = msg + extras

        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = self._colorize(f"[{timestamp}] [{level}]", self.COLORS.get(level, ''))
        line = f"{prefix} {msg}"

        if level == 'ERROR':
            self.logger.error(line)
        elif level == 'WARNING':
            self.logger.warning(line)
        elif level == 'DEBUG':
            self.logger.debug(line)
        else:
            self.logger.info(line)

    def debug(self, msg: str, **kwargs):
        self._log('DEBUG', msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log('INFO', msg, **kwargs)

    def success(self, msg: str, **kwargs):
        self._log('SUCCESS', msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log('WARNING', msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log('ERROR', msg, **kwargs)

    def section(self, title: str):
        """طباعة عنوان قسم بارز"""
        line = '=' * 60
        block = f"{line}\n  {title}\n{line}"
        self.logger.info(self._colorize(block, self.COLORS['SECTION']))

    def progress(self, current: int, total: int, label: str = ''):
        """عرض شريط تقدم"""
        if total <= 0:
            total = 1
        pct = int(current / total * 100)

        if self._tty:
            bar_len = 30
            filled = int(bar_len * current / total)
            bar = '█' * filled + '░' * (bar_len - filled)
            sys.stdout.write(f'\r[{bar}] {pct:3d}% {current}/{total} {label}')
            sys.stdout.flush()
            if current >= total:
                sys.stdout.write('\n')
        else:
            step = max(1, total // 10)
            if current == 1 or current >= total or current % step == 0:
                self.info(f"التقدم: {current}/{total} ({pct}%) {label}")

    def log_exception(self, exc: Exception, context: dict = None):
        """تسجيل استثناء مع تتبع كامل"""
        tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        ctx = f" | السياق: {context}" if context else ''
        self.error(f"استثناء غير متوقع{ctx}")
        self.logger.error(tb)


# الكائن العام للسجل
logger = Logger()
