#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
🏭 SYNTX AI — مصنع ومسجل الحسابات الاستباقي المستقل v2.0 (Syntx Account Factory)
================================================================================
المطور: زيزو الهندسية (Zizo Engineering)
الوصف:
  سكريبت تسجيل آلي بالكامل (Pure Requests / curl_cffi) بدون أي متصفح خارجي.
  يقوم بتوليد حسابات وتفعيلها وحفظها في خزان `accounts_syntx.json` بطريقة ذرية آمنة.
  يدعم توليد الحسابات عبر مزود البريد المباشر (TempMailClub)، ونمط التكرار المستمر (Loop Mode)،
  وإحصائيات نيون عربية متقدمة مع خروج آمن عند الضغط على Ctrl+C.
================================================================================
"""

import os
import sys
import time
import json
import random
import string
import re
import argparse
import urllib.parse
import threading
import secrets
import html
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field

# ======================================================================
# 🌐 ضبط ترميز UTF-8 لتفادي مشاكل الحروف العربية على ويندوز
# ======================================================================
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ======================================================================
# 🎨 إعداد الألوان والمظهر النيوني مع نظام Fallback آمن
# ======================================================================
try:
    from colorama import init, Fore, Style
    init(autoreset=True, strip=False)
    CYAN = Fore.CYAN
    GREEN = Fore.GREEN
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    MAGENTA = Fore.MAGENTA
    WHITE = Fore.WHITE
    BLUE = Fore.BLUE
    BRIGHT = Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    CYAN = GREEN = RED = YELLOW = MAGENTA = WHITE = BLUE = BRIGHT = RESET = ""

try:
    from curl_cffi import requests as cffi
except ImportError:
    print(f"{RED}❌ مكتبة curl_cffi غير مثبتة! يرجى تثبيتها عبر: pip install curl_cffi{RESET}")
    sys.exit(1)

# ======================================================================
# ⚙️ الثوابت العامة للموديول (Module-Level Constants)
# ======================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts_syntx.json")

LOOP_MODE: bool = True               # وضع التكرار الدائم كوضع افتراضي
MAX_ACCOUNTS: int = 10               # الحد الأقصى الافتراضي للحسابات المطلوب توليدها
DELAY_MIN: int = 5                   # أقل ثواني انتظار بين الحسابات
DELAY_MAX: int = 10                  # أكتر ثواني انتظار بين الحسابات
OTP_TIMEOUT: int = 15                # أقصى مهلة لانتظار كود التحقق بالثواني (Fast-Drop)
ACCOUNT_TIMEOUT: int = 180           # ثواني ماكس لإنشاء حساب واحد
DEFAULT_PROVIDER: str = "tempmailclub"  # المزود الافتراضي (Temp-Mail.club)

EMAIL_PROVIDERS: List[str] = ["tempmailclub"]

# قفل التزامن لمنع تصادم العمليات على الملف
_file_lock = threading.Lock()


# ======================================================================
# 🏗️ كلاس الإعدادات المركزية (Config Dataclass — SSOT)
# ======================================================================
@dataclass
class Config:
    """كلاس الإعدادات الموحد لمصنع حسابات Syntx AI"""
    base_api_url: str = "https://api.syntx.ai/api/v1"
    accounts_file: str = DEFAULT_ACCOUNTS_FILE
    loop_mode: bool = LOOP_MODE
    max_accounts: int = MAX_ACCOUNTS
    delay_min: int = DELAY_MIN
    delay_max: int = DELAY_MAX
    otp_timeout: int = OTP_TIMEOUT
    account_timeout: int = ACCOUNT_TIMEOUT
    email_provider: str = DEFAULT_PROVIDER
    target_pool_size: int = 10
    
    # إحصائيات الجلسة
    success_count: int = 0
    failure_count: int = 0
    start_time: float = field(default_factory=time.time)


# ======================================================================
# 📧 مزودات الإيميلات المؤقتة المقبولة في Syntx AI
# ======================================================================

class TempMailClubProvider:
    """عميل Temp-Mail.club لاستخراج إيميلات rc.mailings.live / msp.mailings.live مع تدوير IP ذكي"""
    def __init__(self):
        self.session = cffi.Session(impersonate="chrome124")
        self.fake_ip = f"{random.randint(11, 190)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'X-Forwarded-For': self.fake_ip,
            'X-Real-IP': self.fake_ip,
            'Client-IP': self.fake_ip,
        }
        self.csrf_token = ""
        self.app_fingerprint = None
        self.app_server_memo = None
        self.email = ""
        self.PROVIDER_NAME = "tempmailclub"

    def create_email(self) -> Optional[str]:
        import html
        try:
            r_home = self.session.get('https://temp-mail.club/', headers=self.headers, timeout=15)
            m_csrf = re.search(r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', r_home.text) or \
                     re.search(r'content=["\']([^"\']+)["\']\s+name=["\']csrf-token["\']', r_home.text)
            self.csrf_token = m_csrf.group(1) if m_csrf else ''

            action_comp = None
            for m in re.findall(r'wire:initial-data=["\'](.*?)["\']\s', r_home.text):
                try:
                    j = json.loads(html.unescape(m))
                    if j.get('fingerprint', {}).get('name') == 'frontend.actions':
                        action_comp = j
                        break
                except Exception:
                    pass

            if not action_comp:
                return None

            lw_headers = {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': self.csrf_token,
                'X-Livewire': 'true',
                'Origin': 'https://temp-mail.club',
                'Referer': 'https://temp-mail.club/',
                'Accept': 'text/html, application/xhtml+xml',
                'X-Forwarded-For': self.fake_ip,
                'X-Real-IP': self.fake_ip,
                'Client-IP': self.fake_ip,
            }
            payload = {
                'fingerprint': action_comp['fingerprint'],
                'serverMemo': action_comp['serverMemo'],
                'updates': [
                    {'type': 'callMethod', 'payload': {'id': secrets.token_hex(3), 'method': 'random', 'params': []}}
                ]
            }
            self.session.post('https://temp-mail.club/livewire/message/frontend.actions', json=payload, headers=lw_headers, timeout=10)

            r_box = self.session.get('https://temp-mail.club/mailbox', headers=self.headers, timeout=10)
            for mb in re.findall(r'wire:initial-data=["\'](.*?)["\']', r_box.text):
                try:
                    mb_j = json.loads(html.unescape(mb))
                    if mb_j.get('fingerprint', {}).get('name') == 'frontend.app':
                        self.email = mb_j.get('serverMemo', {}).get('data', {}).get('email', '')
                        self.app_fingerprint = mb_j.get('fingerprint')
                        self.app_server_memo = mb_j.get('serverMemo')
                        return self.email
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def poll_otp(self, timeout: int = 75) -> Optional[str]:
        if not self.app_fingerprint or not self.app_server_memo:
            return None
        lw_headers = {
            'Content-Type': 'application/json',
            'X-CSRF-TOKEN': self.csrf_token,
            'X-Livewire': 'true',
            'Origin': 'https://temp-mail.club',
            'Referer': 'https://temp-mail.club/mailbox',
            'Accept': 'text/html, application/xhtml+xml',
            'X-Forwarded-For': self.fake_ip,
            'X-Real-IP': self.fake_ip,
            'Client-IP': self.fake_ip,
        }
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(3)
            payload = {
                'fingerprint': self.app_fingerprint,
                'serverMemo': self.app_server_memo,
                'updates': [{'type': 'fireEvent', 'payload': {'id': secrets.token_hex(3), 'event': 'fetchMessages', 'params': []}}]
            }
            try:
                r_msg = self.session.post('https://temp-mail.club/livewire/message/frontend.app', json=payload, headers=lw_headers, timeout=10)
                if r_msg.status_code == 200:
                    res_j = r_msg.json()
                    if 'serverMemo' in res_j:
                        self.app_server_memo.update(res_j['serverMemo'])
                    html_content = res_j.get('effects', {}).get('html', '') or ''
                    msgs = res_j.get('serverMemo', {}).get('data', {}).get('messages', [])
                    for m_item in msgs:
                        content = m_item.get('content', '') or m_item.get('subject', '')
                        m = re.search(r'\b(\d{6})\b', content)
                        if m:
                            return m.group(1)
                    if 'verification code' in html_content.lower():
                        m = re.search(r'\b(\d{6})\b', html_content)
                        if m:
                            return m.group(1)
            except Exception:
                pass
        return None


# ======================================================================
# 💾 إدارة خزان الحسابات والكتابة الذرية الآمنة (Atomic DB Management)
# ======================================================================

def load_accounts_pool(cfg: Config) -> List[Dict[str, Any]]:
    """قراءة قاعدة بيانات الحسابات مع حماية من الأخطاء"""
    with _file_lock:
        if not os.path.exists(cfg.accounts_file):
            return []
        try:
            with open(cfg.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []


def save_accounts_pool(accounts: List[Dict[str, Any]], cfg: Config) -> bool:
    """حفظ قاعدة بيانات الحسابات بطريقة ذرية آمنة (Atomic Write) لمنع تلف البيانات"""
    with _file_lock:
        tmp_file = f"{cfg.accounts_file}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(accounts, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, cfg.accounts_file)
            return True
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            return False


def add_account_to_pool(email: str, token: str, provider: str, chat_uuid: Optional[str], cfg: Config) -> bool:
    """إضافة حساب نشط جديد إلى الخزان مع التحقق من عدم التكرار"""
    accounts = load_accounts_pool(cfg)
    
    # التحقق من عدم وجود الإيميل مسبقاً
    for a in accounts:
        if a.get("email") == email:
            a["token"] = token
            a["chat_uuid"] = chat_uuid or a.get("chat_uuid")
            a["status"] = "active"
            a["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            return save_accounts_pool(accounts, cfg)

    new_acc = {
        "email": email,
        "token": token,
        "chat_uuid": chat_uuid or "",
        "provider": provider,
        "status": "active",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_in_days": 365
    }
    accounts.append(new_acc)
    return save_accounts_pool(accounts, cfg)


# ======================================================================
# 🚀 محرك التسجيل والتوثيق المباشر (Registration Engine)
# ======================================================================

def create_syntx_chat(token: str, cfg: Config) -> Optional[str]:
    """إنشاء شات أولي واستخراج معرف الشات (chat_uuid)"""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    payload = {"title": "Syntx Master Session", "scope": "text"}
    try:
        r = cffi.post(f"{cfg.base_api_url}/chats", json=payload, headers=headers, timeout=15)
        if r.status_code in [200, 201]:
            return r.json().get("uuid")
    except Exception:
        pass
    return None


def register_single_syntx_account(cfg: Config) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    تنفيذ عملية تسجيل حساب واحد بالكامل عبر مزود البريد المؤقت:
    1. توليد إيميل مؤقت (*.mailings.live / *.klvibe.org)
    2. طلب إرسال كود الـ OTP
    3. استلام الكود والتوثيق واستخراج الـ Token
    مع الالتزام بمهلة الحساب الكلية ACCOUNT_TIMEOUT ومهلة OTP_TIMEOUT السريعة (Fast-Drop)
    """
    start_account_time = time.time()
    attempt = 0

    while (time.time() - start_account_time) < cfg.account_timeout:
        attempt += 1
        elapsed = int(time.time() - start_account_time)
        remaining = int(cfg.account_timeout - elapsed)

        if attempt > 1:
            print(f"\n{YELLOW}🔄 [محاولة تدوير #{attempt}] مستهلك {elapsed}s | متبقي {remaining}s — جاري تجربة إيميل جديد...{RESET}")

        headers_syntx = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        tmc = TempMailClubProvider()
        print(f"{YELLOW}[*] جاري توليد إيميل جديد عبر مزود: {CYAN}{tmc.PROVIDER_NAME}{RESET}...")
        email = tmc.create_email()

        if not email:
            print(f"{RED}[✗] تعذر توليد إيميل صالح من مزود TempMailClub.{RESET}")
            time.sleep(1)
            continue

        print(f"{GREEN}[✓] تم توليد الإيميل بنجاح ({tmc.PROVIDER_NAME}): {WHITE}{BRIGHT}{email}{RESET}")

        # 1. إرسال طلب كود التحقق
        print(f"{YELLOW}[*] إرسال طلب كود التحقق (OTP) إلى سيرفرات Syntx...{RESET}")
        payload_send = {"email": email, "ref_uuid": None, "utm": ""}
        try:
            r_send = cffi.post(f"{cfg.base_api_url}/auth/email/send-otp", json=payload_send, headers=headers_syntx, timeout=15)
            if r_send.status_code != 200:
                print(f"{RED}[✗] فشل إرسال كود التحقق ({r_send.status_code}): {r_send.text}{RESET}")
                time.sleep(1)
                continue
        except Exception as e:
            print(f"{RED}[✗] خطأ في الاتصال أثناء إرسال OTP: {e}{RESET}")
            time.sleep(1)
            continue

        # 2. انتظار استلام كود التحقق بمهلة سريعة (Fast-Drop)
        print(f"{MAGENTA}[⏳] بانتظار استلام كود التحقق (مهلة سريعة {cfg.otp_timeout} ثانية للنطاق)...{RESET}")
        otp_code = tmc.poll_otp(timeout=cfg.otp_timeout)
            
        if not otp_code:
            print(f"{YELLOW}⚡ [Fast-Drop] مهلة الـ OTP انتهت ({cfg.otp_timeout}s) دون وصول الكود! النطاق بطيء — يتم إسقاطه والتدوير فوراً.{RESET}")
            continue

        print(f"{GREEN}[✓] تم استلام كود التحقق بنجاح: {WHITE}{BRIGHT}{otp_code}{RESET} ⚡")

        # 3. توثيق الكود واستخراج الـ Token
        print(f"{YELLOW}[*] جاري توثيق الكود لدى Syntx واستخراج رمز الدخول (Bearer Token)...{RESET}")
        payload_verify = {"email": email, "otp_code": otp_code, "ref_uuid": None, "utm": ""}
        try:
            r_ver = cffi.post(f"{cfg.base_api_url}/auth/email/verify-otp", json=payload_verify, headers=headers_syntx, timeout=15)
            if r_ver.status_code == 200 and r_ver.json().get("success"):
                token = r_ver.json().get("token")
                print(f"{GREEN}[✓] تم توثيق الحساب بنجاح واستخراج الـ Token!{RESET}")
                return token, email, tmc.PROVIDER_NAME
            else:
                print(f"{RED}[✗] فشل توثيق الكود: {r_ver.text}{RESET}")
        except Exception as e:
            print(f"{RED}[✗] خطأ أثناء توثيق الـ OTP: {e}{RESET}")

    print(f"{RED}[✗] تم تجاوز المهلة القصوى لإنشاء الحساب الواحد ({cfg.account_timeout} ثانية) دون نجاح.{RESET}")
    return None, None, None


# ======================================================================
# 📊 لوحات التحكم والبانرات الملونة (Visual Banners & Dashboards)
# ======================================================================

def print_start_banner(cfg: Config):
    """طباعة بانر البداية النيوني الفخم"""
    accounts = load_accounts_pool(cfg)
    active_now = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
    
    print(f"\n{CYAN}{BRIGHT}╔══════════════════════════════════════════════════════════════════════════════════╗")
    print(f"║             🏭 SYNTX AI ACCOUNT FACTORY — مصنع ومسجل الحسابات المستقل            ║")
    print(f"║          Pure Requests Engine • Multi-Email Rotation • Atomic Database           ║")
    print(f"╚══════════════════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"{WHITE}• وضع التشغيل: {YELLOW}{'تكرار دائم (Loop Mode)' if cfg.loop_mode else 'عدد محدد (Target Count)'}{RESET}")
    print(f"{WHITE}• الحسابات المطلوبة: {YELLOW}{cfg.max_accounts} حساب{RESET} | المهلة بين العمليات: {YELLOW}{cfg.delay_min}-{cfg.delay_max} ثواني (عشوائي){RESET}")
    print(f"{WHITE}• مزود الإيميلات: {CYAN}{cfg.email_provider.upper()}{RESET} | مهلة الـ OTP: {YELLOW}{cfg.otp_timeout}s (Fast-Drop){RESET} | مهلة الحساب: {YELLOW}{cfg.account_timeout}s{RESET}")
    print(f"{WHITE}• خزان الحسابات الحالي: {GREEN}{BRIGHT}{active_now} حساب نشط{RESET} في {YELLOW}{os.path.basename(cfg.accounts_file)}{RESET}")
    print(f"{CYAN}{'═' * 82}{RESET}\n")


def print_final_stats(cfg: Config):
    """طباعة إحصائيات الجلسة الختامية عند الانتهاء أو الضغط على Ctrl+C"""
    elapsed = int(time.time() - cfg.start_time)
    accounts = load_accounts_pool(cfg)
    active_now = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
    
    print(f"\n{CYAN}{BRIGHT}╔══════════════════════════════════════════════════════════════════════════════════╗")
    print(f"║                      📊 تقرير إحصائيات مصنع الحسابات الختامي                     ║")
    print(f"╚══════════════════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"{WHITE}• مدة التشغيل الكلية: {YELLOW}{elapsed // 60} دقيقة و {elapsed % 60} ثانية{RESET}")
    print(f"{WHITE}• الحسابات المسجلة بنجاح: {GREEN}{BRIGHT}{cfg.success_count} حساب{RESET}")
    print(f"{WHITE}• المحاولات الفاشلة: {RED}{cfg.failure_count} محاولة{RESET}")
    print(f"{WHITE}• إجمالي الحسابات الجاهزة بالخزان: {GREEN}{BRIGHT}{active_now} حساب نشط ⚡{RESET}")
    print(f"{WHITE}• مسار ملف الحفظ: {YELLOW}{cfg.accounts_file}{RESET}")
    print(f"{CYAN}╚══════════════════════════════════════════════════════════════════════════════════╝{RESET}\n")


# ======================================================================
# 🔄 الحلقة الرئيسية للتوليد والتسجيل (Main Factory Loop)
# ======================================================================

def run_factory_loop(cfg: Config):
    """تشغيل حلقة المصنع لتسجيل الحسابات بشكل متكرر حتى الهدف أو إشارة الإيقاف"""
    print_start_banner(cfg)
    
    iteration = 0
    try:
        while True:
            # التحقق من الوصول للحد الأقصى في حال عدم تفعيل التكرار اللانهائي
            if not cfg.loop_mode and cfg.success_count >= cfg.max_accounts:
                print(f"{GREEN}🎉 تم الوصول للعدد المطلوب بنجاح ({cfg.success_count} حساب)!{RESET}")
                break
                
            iteration += 1
            print(f"{BLUE}{BRIGHT}══════════════════════════════════════════════════════════════════════{RESET}")
            print(f"{CYAN}🚀 [عملية #{iteration}] جاري تسجيل حساب جديد ({cfg.success_count + 1} من {cfg.max_accounts})...{RESET}")
            
            token, email, prov = register_single_syntx_account(cfg)
            
            if token and email:
                chat_uuid = create_syntx_chat(token, cfg)
                saved = add_account_to_pool(email, token, prov, chat_uuid, cfg)
                if saved:
                    cfg.success_count += 1
                    print(f"{GREEN}{BRIGHT}🎉 [SUCCESS 100%] تم تفعيل وتثبيت الحساب في الخزان بنجاح!{RESET}")
                    print(f"{WHITE}• الإيميل: {CYAN}{email}{RESET}")
                    print(f"{WHITE}• التوكن: {YELLOW}{token[:35]}...{RESET}")
                    print(f"{WHITE}• المعرف: {MAGENTA}{chat_uuid}{RESET}")
                else:
                    cfg.failure_count += 1
                    print(f"{RED}[✗] فشل حفظ الحساب في قاعدة البيانات.{RESET}")
            else:
                cfg.failure_count += 1
                print(f"{RED}⚠️ تعذر إتمام عملية التسجيل الحالية.{RESET}")

            # فحص التوقف لو وصلنا للحد في وضع العدد المحدد
            if not cfg.loop_mode and cfg.success_count >= cfg.max_accounts:
                print(f"\n{GREEN}🎉 اكتمل تسجيل الهدف المطلوب بالكامل!{RESET}")
                break

            # حساب المهلة العشوائية بين DELAY_MIN و DELAY_MAX
            delay = random.randint(min(cfg.delay_min, cfg.delay_max), max(cfg.delay_min, cfg.delay_max))
            print(f"{YELLOW}⏳ انتظار {delay} ثواني قبل العملية التالية (عشوائي بين {cfg.delay_min} و {cfg.delay_max} ث)...{RESET}\n")
            time.sleep(delay)

    except (KeyboardInterrupt, SystemExit):
        print(f"\n{RED}⛔ تم إيقاف المصنع يدوياً بواسطة المستخدم (Ctrl+C).{RESET}")
    finally:
        print_final_stats(cfg)


# ======================================================================
# 🎮 واجهة سطر الأوامر (CLI Arguments & Entry Point)
# ======================================================================

def main():
    """نقطة انطلاق السكربت ودعم الخيارات من التيرمينال"""
    parser = argparse.ArgumentParser(description="Syntx AI Account Factory — مصنع حسابات Syntx AI المستقل")
    parser.add_argument("--max", "-m", type=int, default=MAX_ACCOUNTS, help=f"الحد الأقصى لعدد الحسابات (الافتراضي: {MAX_ACCOUNTS})")
    parser.add_argument("--loop", action="store_true", default=True, help="تشغيل في وضع التكرار الدائم (الافتراضي)")
    parser.add_argument("--no-loop", action="store_false", dest="loop", help="إيقاف التكرار عند الوصول للعدد المحدد بـ --max")
    parser.add_argument("--delay-min", type=int, default=DELAY_MIN, help=f"أقل ثواني انتظار بين الحسابات (الافتراضي: {DELAY_MIN})")
    parser.add_argument("--delay-max", type=int, default=DELAY_MAX, help=f"أكثر ثواني انتظار بين الحسابات (الافتراضي: {DELAY_MAX})")
    parser.add_argument("--delay", "-d", type=int, default=None, help="مهلة انتظار ثابتة (تتجاوز delay-min و delay-max)")
    parser.add_argument("--timeout", "-t", type=int, default=OTP_TIMEOUT, help=f"أقصى مهلة لانتظار كود OTP (الافتراضي: {OTP_TIMEOUT})")
    parser.add_argument("--account-timeout", type=int, default=ACCOUNT_TIMEOUT, help=f"أقصى مهلة لإنشاء حساب واحد بالكامل (الافتراضي: {ACCOUNT_TIMEOUT})")
    parser.add_argument("--provider", "-p", choices=EMAIL_PROVIDERS, default=DEFAULT_PROVIDER, help="مزود الإيميل (tempmailclub)")
    parser.add_argument("--count", "-c", action="store_true", help="عرض عدد الحسابات النشطة بالخزان فقط")
    parser.add_argument("--list", "-l", action="store_true", help="عرض قائمة بجميع الحسابات المسجلة وحالتها")
    parser.add_argument("--file", "-f", type=str, default=DEFAULT_ACCOUNTS_FILE, help="مسار ملف الحفظ")
    args = parser.parse_args()

    d_min = args.delay if args.delay is not None else args.delay_min
    d_max = args.delay if args.delay is not None else args.delay_max

    cfg = Config(
        accounts_file=args.file,
        loop_mode=args.loop,
        max_accounts=args.max,
        delay_min=d_min,
        delay_max=d_max,
        otp_timeout=args.timeout,
        account_timeout=args.account_timeout,
        email_provider=args.provider
    )

    # عرض عدد الحسابات فقط
    if args.count:
        accounts = load_accounts_pool(cfg)
        active = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
        print(f"\n{CYAN}📊 إجمالي الحسابات النشطة في الخزان: {GREEN}{BRIGHT}{active}{RESET} حساب جاهز.\n")
        return

    # عرض قائمة الحسابات
    if args.list:
        accounts = load_accounts_pool(cfg)
        print(f"\n{CYAN}📋 قائمة الحسابات في {YELLOW}{cfg.accounts_file}:{RESET}")
        if not accounts:
            print(f"{RED}لا توجد أي حسابات مسجلة بعد.{RESET}\n")
            return
        for i, a in enumerate(accounts, 1):
            status_color = GREEN if a.get("status") == "active" else RED
            print(f"  {i}. {WHITE}{a.get('email'):<35}{RESET} | المزود: {CYAN}{a.get('provider', 'N/A'):<12}{RESET} | الحالة: {status_color}{a.get('status', 'active')}{RESET}")
        print()
        return

    run_factory_loop(cfg)


if __name__ == "__main__":
    main()
