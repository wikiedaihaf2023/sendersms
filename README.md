# 📨 MessageFlow Pro

نظام احترافي لإرسال رسائل SMS وواتس آب الجماعية من ملف إكسل.

## ✨ المميزات

- ✅ قراءة ملفات إكسل (xlsx, xls) بسهولة
- ✅ التحقق التلقائي من صحة أرقام الهواتف (دعم +200 دولة عبر `phonenumbers`)
- ✅ تخصيص الرسائل باستخدام اسم صاحب الجواز ورقم الجواز
- ✅ إرسال متزامن أو متوازي
- ✅ منع الرسائل المكررة تلقائياً
- ✅ إعادة المحاولة التلقائية عند الفشل
- ✅ التحكم في معدل الإرسال (Rate Limiting)
- ✅ تسجيل شامل في قاعدة بيانات SQLite
- ✅ تصدير النتائج إلى إكسل
- ✅ واجهة سطر أوامر + واجهة ويب
- ✅ إحصائيات مفصلة

## 📋 المتطلبات

- Python 3.9+
- حساب Twilio أو Meta Business API
- مكتبات Python (انظر `requirements.txt`)

## 🚀 التثبيت

```bash
# استنساخ المشروع
git clone https://github.com/yourusername/messageflow-pro.git
cd messageflow-pro

# إنشاء بيئة افتراضية
python -m venv venv

# تفعيل البيئة
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# تثبيت المتطلبات
pip install -r requirements.txt

# نسخ ملف البيئة
cp .env.example .env

# تحرير .env وإضافة المفاتيح
nano .env
```

### 🔑 إعداد Twilio

1. سجّل في Twilio واحصل على رصيد مجاني.
2. احصل على Account SID و Auth Token من Dashboard.
3. اشترِ رقم هاتف يدعم SMS.
4. فعّل واتس آب Sandbox من Messaging → Try it out.

## 📊 تنسيق ملف الإكسل

| رقم الهاتف | اسم صاحب الجواز | رقم الجواز |
|------------|-----------------|------------|
| 0501234567 | محمد أحمد       | A1234567   |

### 📂 ملف إكسل افتراضي جاهز

المشروع يتضمن ملفاً افتراضياً ببيانات تجريبية في `data/contacts.xlsx` (10 جهات اتصال تجريبية)
يمكنك تجربته مباشرة:

```bash
python run.py -f data/contacts.xlsx --dry-run
```

ولإنشاء قالب فارغ بأعمدتك الخاصة:

```bash
python run.py --template
```

## 🖥️ الاستخدام

### واجهة سطر الأوامر

```bash
# إرسال الرسائل
python run.py -f data/contacts.xlsx

# إرسال SMS فقط
python run.py -f data/contacts.xlsx --no-whatsapp

# إرسال واتس آب فقط
python run.py -f data/contacts.xlsx --no-sms

# وضع التجربة (بدون إرسال فعلي)
python run.py -f data/contacts.xlsx --dry-run

# إرسال متوازي
python run.py -f data/contacts.xlsx --parallel --max-workers 10

# عرض الإحصائيات
python run.py --stats

# نسخ احتياطي لقاعدة البيانات
python run.py --backup-db
```

### واجهة الويب

```bash
python web/app.py
```

ثم افتح المتصفح على http://localhost:5000

## 📁 هيكل المشروع

```text
messageflow_pro/
├── app/
│   ├── core/          # الإعدادات، السجلات، محرك الأتمتة
│   ├── services/      # خدمات الإكسل، SMS، واتس آب، التحقق
│   ├── models/        # نماذج البيانات
│   ├── database/      # قاعدة البيانات والمستودعات
│   └── utils/         # أدوات مساعدة
├── cli/               # واجهة سطر الأوامر
├── web/               # واجهة الويب
├── tests/             # الاختبارات
├── data/              # ملفات البيانات والقوالب
├── logs/              # ملفات السجلات
├── backups/           # النسخ الاحتياطية
├── .env.example       # قالب ملف البيئة
├── requirements.txt   # المتطلبات
└── run.py             # نقطة الدخول
```

## ⚙️ الإعدادات المتقدمة

يمكنك تعديل `app/core/config.py` أو ملف `.env` لتغيير:

- معدل الإرسال (SMS/WhatsApp per second)
- عدد محاولات الإعادة
- قوالب الرسائل
- رمز الدولة الافتراضي

## 🔒 الأمان

- لا تقم برفع ملف `.env` إلى Git.
- استخدم مفاتيح API محدودة الصلاحيات.
- فعّل التحقق بخطوتين في حساب Twilio.
- احتفظ بنسخة احتياطية من قاعدة البيانات.

## 📄 الترخيص

MIT License

## 🤝 المساهمة

نرحب بالمساهمات! يرجى قراءة `CONTRIBUTING.md` للمزيد.

## 📞 الدعم

إذا واجهتك مشكلة، افتح issue على GitHub أو راسلنا.
