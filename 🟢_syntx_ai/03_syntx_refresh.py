#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""On-demand token health report; --clean/--purge explicitly removes candidates.

STOP ALL POOL WRITERS before cleaning. Atomic replace is not a shared lock.
No registration, daemon, token refresh, retries, or live calls at import time.
Evidence and user-approved deletion policy: Root/SYNTX_REFRESH_SPEC.md.
Uses the same sibling pool, JSON record contract and HTTP libraries as steps 1/2.
"""
import argparse
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_POOL = BASE_DIR / 'accounts_syntx.json'
API = 'https://api.syntx.ai/api/v1'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              'Chrome/124.0.0.0 Safari/537.36')
MIN_HEALTHY = 5


def make_session():
    try:
        from curl_cffi import requests
    except ImportError:
        import requests
    return requests.Session()


def load_pool(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('ملف الخزان غير موجود أو ليس ملفًا عاديًا؛ لم تتم الكتابة.')
    snapshot = path.read_bytes()
    try:
        accounts = json.loads(snapshot.decode('utf-8-sig'))
    except (ValueError, UnicodeError):
        raise ValueError('ملف الخزان تالف؛ لم تتم الكتابة.') from None
    if not isinstance(accounts, list) or any(not isinstance(row, dict) for row in accounts):
        raise ValueError('الخزان يجب أن يكون قائمة سجلات؛ لم تتم الكتابة.')
    return accounts, snapshot


def number(value, maximum=None):
    if type(value) not in (int, float):
        return None
    try:
        if not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
            return None
    except OverflowError:
        return None
    return value


def fetch_health(session, endpoint, token, timeout):
    # Headers approved explicitly in GO, matching 01_syntx_chat.py:555-559.
    headers = {'Authorization': f'Bearer {token}', 'User-Agent': USER_AGENT,
               'Content-Type': 'application/json'}
    try:
        response = session.get(API + endpoint, headers=headers, timeout=timeout,
                               allow_redirects=False)
        try:
            status = response.status_code
            if status != 200:
                return status, None
            body = response.json()
            return status, body if isinstance(body, dict) else None
        finally:
            response.close()
    except Exception:
        # Never print arbitrary exception text, response bodies or credentials.
        return None, None


def check_account(account, session, timeout=15):
    result = {'state': 'unknown', 'reason': 'بيانات أو استجابة غير محسومة',
              'balance': None, 'six': None, 'seven': None}
    token = account.get('token')
    if (not isinstance(token, str) or not token or not token.isascii()
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in token)):
        result['reason'] = 'توكن مفقود أو غير صالح محليًا؛ الاحتفاظ بالسجل'
        return result
    observations = []
    for endpoint in ('/user/balance', '/llm/limits'):
        status, body = fetch_health(session, endpoint, token, timeout)
        observations.append((status, body))
        if status in (401, 403, 429):
            # Explicit GO policy: removal candidate, not proof of permanent expiry.
            result.update(state='dead', reason=f'مرشح للتطهير وفق السياسة: HTTP {status}')
            return result
        if status == 200 and body is not None:
            if endpoint == '/user/balance':
                result['balance'] = number(body.get('balance'))
            else:
                for window, key in (('window_6h', 'six'), ('window_7d', 'seven')):
                    value = body.get(window)
                    if isinstance(value, dict):
                        result[key] = number(value.get('percent_left'), 100)
    if result['balance'] == 0 or result['six'] == 0:
        result.update(state='dead', reason='مرشح للتطهير: الرصيد أو نسبة 6h تساوي صفرًا')
    elif all(result[key] is not None for key in ('balance', 'six', 'seven')):
        if result['seven'] == 0:
            result.update(state='limited', reason='نسبة 7d صفر؛ ليست وحدها سببًا معتمدًا للحذف')
        else:
            result.update(state='healthy', reason='رصيد ونسب استخدام موجبة')
    elif any(status != 200 for status, _ in observations):
        result['reason'] = 'فشل اتصال أو HTTP غير محسوم؛ الاحتفاظ بالسجل'
    return result


def save_clean_pool(path, retained, snapshot):
    """Unique same-directory .tmp -> flush/fsync -> replace; no unsafe fallback.

    Snapshot checking is best-effort only. All writers MUST already be stopped.
    """
    if path.is_symlink() or path.read_bytes() != snapshot:
        raise ValueError('تغير الخزان أثناء الفحص؛ أُلغي التطهير. أوقف جميع الكتّاب.')
    original_mode = stat.S_IMODE(path.stat().st_mode)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(retained, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, original_mode)
        if path.is_symlink() or path.read_bytes() != snapshot:
            raise ValueError('تغير الخزان قبل الحفظ؛ أُلغي التطهير دون استبداله.')
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def emit(message, color='yellow'):
    colors = {'green': '32', 'yellow': '33', 'red': '31', 'cyan': '36'}
    if sys.stdout.isatty() and 'NO_COLOR' not in os.environ:
        print(f'\033[{colors[color]}m{message}\033[0m')
    else:
        print(message)


def report(results, clean, removed):
    labels = {'healthy': 'صالح', 'dead': 'مرشح تطهير', 'limited': 'محدود', 'unknown': 'غير محسوم'}
    for index, item in enumerate(results, 1):
        values = ['?' if item[key] is None else format(item[key], 'g')
                  for key in ('balance', 'six', 'seven')]
        color = 'green' if item['state'] == 'healthy' else 'red' if item['state'] == 'dead' else 'yellow'
        emit(f"#{index} | {labels[item['state']]} | balance={values[0]} | "
             f"6h={values[1]}% | 7d={values[2]}% | {item['reason']}", color)
    healthy = sum(item['state'] == 'healthy' for item in results)
    candidates = sum(item['state'] == 'dead' for item in results)
    unknown = sum(item['state'] == 'unknown' for item in results)
    emit(f'الإجمالي={len(results)} | الصالح المؤكد={healthy} | مرشحو التطهير={candidates} | '
         f'غير المحسوم={unknown} | المحذوف فعليًا={removed}', 'cyan')
    if not clean:
        emit('وضع التقرير فقط: لم يتم تعديل الخزان. للتطهير استخدم --clean بعد إيقاف جميع الكتّاب.')
    if healthy < MIN_HEALTHY:
        emit(f'تنبيه: الحسابات الصالحة أقل من {MIN_HEALTHY}. إعادة الملء مسؤولية منظومة الشات؛ '
             'لم يتم استدعاء التسجيل.', 'yellow')


def timeout_value(value):
    try:
        timeout = float(value)
        if not math.isfinite(timeout) or not 1 <= timeout <= 120:
            raise ValueError
        return timeout
    except ValueError:
        raise argparse.ArgumentTypeError('timeout must be between 1 and 120 seconds') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='فحص خزان Syntx يدويًا؛ التقرير لا يكتب، والتطهير اختياري.')
    parser.add_argument('--clean', '--purge', action='store_true',
                        help='حذف المرشحين ذريًا؛ يجب إيقاف جميع العمليات التي تكتب في الخزان أولًا')
    parser.add_argument('--file', type=Path, default=DEFAULT_POOL, help='مسار ملف الخزان')
    parser.add_argument('--timeout', type=timeout_value, default=15, help='مهلة كل طلب بالثواني (15 افتراضيًا)')
    args = parser.parse_args(argv)
    try:
        from colorama import just_fix_windows_console
        just_fix_windows_console()
    except ImportError:
        pass
    try:
        accounts, snapshot = load_pool(args.file)
        if args.clean:
            emit('وضع التطهير: يفترض توقف جميع كتّاب الخزان؛ الحفظ الذري لا يمنع تعارض العمليات.', 'red')
        results = []
        if accounts:
            with make_session() as session:
                for index, account in enumerate(accounts, 1):
                    emit(f'فحص السجل {index}/{len(accounts)}...', 'cyan')
                    results.append(check_account(account, session, args.timeout))
        retained = [row for row, item in zip(accounts, results) if item['state'] != 'dead']
        removed = 0
        if args.clean and len(retained) != len(accounts):
            save_clean_pool(args.file, retained, snapshot)
            removed = len(accounts) - len(retained)
        report(results, args.clean, removed)
        return 1 if any(item['state'] == 'unknown' for item in results) else 0
    except (OSError, ValueError, ImportError):
        emit('تعذر إكمال العملية: تحقق من الخزان وصلاحياته والاعتماديات وثبات الملف. '
             'لم تُطبع بيانات حساسة؛ راجع وضع الخزان قبل إعادة التشغيل.', 'red')
        return 2
    except KeyboardInterrupt:
        emit('تم الإيقاف. إن وقع الإيقاف بعد الاستبدال الذري، فقد تم اعتماد التطهير.', 'yellow')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
