"""
تطبيق ويب باستخدام Flask
"""
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename

from app.core.automation import AutomationEngine
from app.core.logger import logger
from app.core.config import settings
from app.database.repositories import provider_settings_repo
from app.services.billing_service import billing_service

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', settings.secret_key)
app.config['UPLOAD_FOLDER'] = 'data/uploads'
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)


def get_current_username():
    return (session.get('username') or 'default').strip() or 'default'


def get_provider_settings_for_user(username: str = None):
    return provider_settings_repo.get_provider_settings(username or get_current_username())


def validate_provider_configuration(provider: str):
    provider = (provider or '').strip().lower()
    if provider == 'twilio':
        return settings.twilio.is_sms_configured(), 'بيانات Twilio غير مكتملة: الرجاء إدخال Account SID و Auth Token ورقم الهاتف.'

    config = settings.sms.get_provider_config(provider)
    if not config:
        return False, f'مزود {provider} غير موجود.'

    url = str(config.get('url', '')).strip()
    username_value = str(config.get('username', '')).strip()
    password_value = str(config.get('password', '')).strip()
    api_key_value = str(config.get('api_key', '')).strip()
    sender_value = str(config.get('sender', '')).strip()

    if not url:
        return False, f'رابط {provider} مطلوب قبل الإرسال.'
    if not (username_value and password_value or api_key_value):
        return False, f'Username/Password أو API Key الخاص بـ {provider} مطلوبين قبل الإرسال.'
    if not sender_value:
        return False, f'Sender الخاص بـ {provider} مطلوب قبل الإرسال.'
    return True, ''

# قائمة لتخزين العمليات الجارية
active_jobs = {}
job_lock = threading.Lock()


def allowed_file(filename):
    """التحقق من نوع الملف"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['xlsx', 'xls']


@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """صفحة تسجيل الدخول"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            return render_template('login.html', error='يرجى إدخال اسم المستخدم وكلمة المرور'), 400
        session['username'] = username
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/api/provider-settings')
def provider_settings_api():
    """إرجاع إعدادات المزودات للمستخدم الحالي"""
    settings_for_user = get_provider_settings_for_user()
    return jsonify(settings_for_user)


@app.route('/save_provider_settings', methods=['POST'])
def save_provider_settings():
    """حفظ إعدادات المزود للمستخدم الحالي في قاعدة البيانات"""
    username = get_current_username()
    provider = (request.form.get('sms_provider') or settings.sms.provider or 'yemen_mobile').strip().lower()

    payload = {
        'yemen_mobile_url': request.form.get('yemen_mobile_url', ''),
        'yemen_mobile_username': request.form.get('yemen_mobile_username', ''),
        'yemen_mobile_password': request.form.get('yemen_mobile_password', ''),
        'yemen_mobile_sender': request.form.get('yemen_mobile_sender', ''),
        'yemen_mobile_api_key': request.form.get('yemen_mobile_api_key', ''),
        'sapa_phone_url': request.form.get('sapa_phone_url', ''),
        'sapa_phone_username': request.form.get('sapa_phone_username', ''),
        'sapa_phone_password': request.form.get('sapa_phone_password', ''),
        'sapa_phone_sender': request.form.get('sapa_phone_sender', ''),
        'sapa_phone_api_key': request.form.get('sapa_phone_api_key', ''),
        'you_url': request.form.get('you_url', ''),
        'you_username': request.form.get('you_username', ''),
        'you_password': request.form.get('you_password', ''),
        'you_sender': request.form.get('you_sender', ''),
        'you_api_key': request.form.get('you_api_key', ''),
    }

    provider_settings_repo.save_provider_settings(username=username, provider=provider, **payload)
    return jsonify({'success': True, 'provider': provider, 'username': username})


@app.route('/api/packages')
def api_list_packages():
    """إرجاع قائمة الباقات المتاحة للمزود الحالي أو المحدد"""
    provider = (request.args.get('provider') or settings.sms.provider or 'yemen_mobile').strip().lower()
    summary = billing_service.get_subscription_summary(
        username=get_current_username(), provider=provider
    )
    return jsonify(summary)


@app.route('/api/subscribe', methods=['POST'])
def api_subscribe():
    """اشتراك المستخدم في باقة"""
    username = get_current_username()
    package_id_raw = request.form.get('package_id') or request.json.get('package_id') if request.is_json else request.form.get('package_id')
    try:
        package_id = int(package_id_raw)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'معرف الباقة غير صالح'}), 400

    provider = (
        (request.form.get('provider') or settings.sms.provider or 'yemen_mobile')
        if not request.is_json
        else ((request.json or {}).get('provider') or settings.sms.provider or 'yemen_mobile')
    ).strip().lower()

    sub = billing_service.subscribe_to_package(username=username, package_id=package_id, provider=provider)
    if not sub:
        return jsonify({'success': False, 'error': 'فشل الاشتراك في الباقة - الباقة غير موجودة أو غير مفعلة'}), 400

    summary = billing_service.get_subscription_summary(username=username, provider=provider)
    return jsonify({
        'success': True,
        'message': f'تم الاشتراك بنجاح في الباقة. الرصيد: {sub.sms_remaining} رسالة.',
        'subscription': summary,
        'package_id': package_id,
        'provider': provider,
    })


@app.route('/api/balance')
def api_check_balance():
    """فحص الرصيد المطلوب قبل الإرسال"""
    username = get_current_username()
    provider = (request.args.get('provider') or settings.sms.provider or 'yemen_mobile').strip().lower()
    try:
        required = int(request.args.get('required', '0'))
    except ValueError:
        required = 0

    result = billing_service.check_balance(username=username, required_count=required, provider=provider)
    return jsonify({
        'ok': result.ok,
        'provider': result.provider,
        'remaining_sms': result.remaining,
        'required_sms': result.required,
        'shortfall_sms': result.shortfall,
        'subscription_id': result.subscription_id,
        'message': result.message,
    })


@app.route('/api/usage-history')
def api_usage_history():
    """سجل الاستهلاك للمستخدم الحالي"""
    username = get_current_username()
    provider = (request.args.get('provider') or settings.sms.provider or 'yemen_mobile').strip().lower()
    try:
        limit = int(request.args.get('limit', '30'))
    except ValueError:
        limit = 30

    logs = billing_service.get_usage_history(username=username, provider=provider, limit=limit)
    return jsonify({'logs': logs, 'provider': provider, 'username': username})


@app.route('/upload', methods=['POST'])
def upload_file():
    """تحميل ملف وتشغيل الأتمتة"""
    if 'excel_file' not in request.files:
        return jsonify({'error': 'لم يتم تحميل ملف'}), 400

    file = request.files['excel_file']

    if file.filename == '':
        return jsonify({'error': 'اسم الملف فارغ'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'نوع الملف غير مدعوم'}), 400

    # حفظ الملف
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # قراءة الخيارات
    sms_provider = (request.form.get('sms_provider') or settings.sms.provider or 'twilio').strip().lower()
    if sms_provider in {'yemen_mobile', 'yemen-mobile', 'yemen mobile'}:
        settings.sms.provider = 'yemen_mobile'
    elif sms_provider in {'sapa_phone', 'sapa-phone', 'sapa phone', 'sapa'}:
        settings.sms.provider = 'sapa_phone'
    elif sms_provider in {'you', 'you_sms', 'you-sms', 'you sms'}:
        settings.sms.provider = 'you'
    elif sms_provider in {'twilio'}:
        settings.sms.provider = 'twilio'

    # تحديث إعدادات المزود من الواجهة الحالية قبل التشغيل
    settings.sms.yemen_mobile_url = request.form.get('yemen_mobile_url', settings.sms.yemen_mobile_url).strip()
    settings.sms.yemen_mobile_username = request.form.get('yemen_mobile_username', settings.sms.yemen_mobile_username).strip()
    settings.sms.yemen_mobile_password = request.form.get('yemen_mobile_password', settings.sms.yemen_mobile_password).strip()
    settings.sms.yemen_mobile_sender = request.form.get('yemen_mobile_sender', settings.sms.yemen_mobile_sender).strip()
    settings.sms.yemen_mobile_api_key = request.form.get('yemen_mobile_api_key', settings.sms.yemen_mobile_api_key).strip()

    settings.sms.sapa_phone_url = request.form.get('sapa_phone_url', settings.sms.sapa_phone_url).strip()
    settings.sms.sapa_phone_username = request.form.get('sapa_phone_username', settings.sms.sapa_phone_username).strip()
    settings.sms.sapa_phone_password = request.form.get('sapa_phone_password', settings.sms.sapa_phone_password).strip()
    settings.sms.sapa_phone_sender = request.form.get('sapa_phone_sender', settings.sms.sapa_phone_sender).strip()
    settings.sms.sapa_phone_api_key = request.form.get('sapa_phone_api_key', settings.sms.sapa_phone_api_key).strip()

    settings.sms.you_url = request.form.get('you_url', settings.sms.you_url).strip()
    settings.sms.you_username = request.form.get('you_username', settings.sms.you_username).strip()
    settings.sms.you_password = request.form.get('you_password', settings.sms.you_password).strip()
    settings.sms.you_sender = request.form.get('you_sender', settings.sms.you_sender).strip()
    settings.sms.you_api_key = request.form.get('you_api_key', settings.sms.you_api_key).strip()

    valid, error_msg = validate_provider_configuration(settings.sms.provider)
    if not valid:
        return jsonify({'error': error_msg}), 400

    send_sms = request.form.get('send_sms', 'true').lower() == 'true'
    send_whatsapp = request.form.get('send_whatsapp', 'true').lower() == 'true'
    parallel = request.form.get('parallel', 'false').lower() == 'true'
    dry_run = request.form.get('dry_run', 'false').lower() == 'true'
    username = get_current_username()

    # إنشاء مهمة
    job_id = os.urandom(8).hex()

    def run_job():
        try:
            engine = AutomationEngine(
                excel_file=filepath,
                send_sms=send_sms,
                send_whatsapp=send_whatsapp,
                parallel=parallel,
                dry_run=dry_run,
                username=username
            )
            stats = engine.run()
            with job_lock:
                active_jobs[job_id]['status'] = 'completed'
                active_jobs[job_id]['stats'] = stats
        except Exception as e:
            with job_lock:
                active_jobs[job_id]['status'] = 'failed'
                active_jobs[job_id]['error'] = str(e)

    with job_lock:
        active_jobs[job_id] = {
            'status': 'running',
            'file': filename,
            'stats': None,
            'error': None
        }

    thread = threading.Thread(target=run_job)
    thread.daemon = True
    thread.start()

    return jsonify({'job_id': job_id}), 200


@app.route('/job/<job_id>')
def job_status(job_id):
    """حالة المهمة"""
    with job_lock:
        job = active_jobs.get(job_id)

    if not job:
        return jsonify({'error': 'المهمة غير موجودة'}), 404

    return jsonify(job)


@app.route('/dashboard')
def dashboard():
    """لوحة التحكم"""
    with job_lock:
        jobs = dict(active_jobs)
    return render_template('dashboard.html', jobs=jobs)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
