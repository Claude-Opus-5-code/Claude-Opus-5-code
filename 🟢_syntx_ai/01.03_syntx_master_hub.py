# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════════
🟢 Syntx AI Master Hub (Grok Hub) — Flagship Grok & Background Pool
══════════════════════════════════════════════════════════════════════
- كلاس كونفج موحد وشامل (SSOT) في أول السكربت يتحكم في كل المتغيرات.
- خزان حسابات استباقي (Account Pool) في ملف accounts_syntx.json:
    • سحب فوري للحسابات الجاهزة في 0.01 ثانية (Zero Startup Latency).
    • خيط خلفي ذكي (Background Daemon Thread) يولد 5 حسابات تلقائياً.
    • حماية ذرية للملفات (Atomic Write & Thread-Safe Locking).
- محرك بريد متطور:
    • 🌟 Temp-Mail.club (Livewire + rc.mailings.live / msp.mailings.live).
- دعم كامل لموديلات Grok الخارقة:
    • grok-4.5 (Grok 4.5 Flagship - Deep Reasoning)
    • grok-4.3 (Grok 4.3)
    • grok-4   (Grok 4)
    • grok-3   (Grok 3)
- شات مفتوح بدون ليمت رسائل + ملفات chat_send.txt و chat_reply.txt.
══════════════════════════════════════════════════════════════════════
"""
from dataclasses import dataclass, field
import json
import os
import sys
import time
import pathlib
import argparse
import re
import urllib.parse
import tempfile
import random
import string
import secrets
import threading

# ضبط ترميز الطرفية للويندوز لدعم العربي والإيموجي
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# دعم الألوان مع fallback آمن
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class _F:
        def __getattr__(self, _): return ""
    Fore = Style = _F()

# استيراد مكتبة curl_cffi لتخطي الحمايات ومطابقة بصمة Chrome
try:
    from curl_cffi import requests as cffi
except ImportError:
    import requests as cffi


# ======================================================================
# ⚙️ كلاس الإعدادات الموحد (Config) - مصدر الحقيقة الوحيد (SSOT)
# ======================================================================
@dataclass
class Config:
    # 🤖 الموديل الافتراضي المستخدم
    model: str = "grok-4.5"
    
    # 📋 قائمة بموديلات Grok المعتمدة في السكربت
    available_models: dict = field(default_factory=lambda: {
        "grok-4.5": "🌟 جروك 4.5 الخارق (Grok 4.5 Flagship - Elite Coding & Logic)",
        "grok-4.3": "⚡ جروك 4.3 (Grok 4.3 - Fast & Smart)",
        "grok-4":   "🧠 جروك 4 (Grok 4 - Advanced Reasoning)",
        "grok-3":   "🚀 جروك 3 (Grok 3)",
    })
    
    # 🌐 الرابط الأساسي لواجهة Syntx AI
    base_api_url: str = "https://api.syntx.ai/api/v1"
    
    # 🗄️ إعدادات خزان الحسابات التلقائي (Background Account Pool)
    accounts_file: str = "accounts_syntx.json"
    min_pool_size: int = 5                  # الحد الأدنى للحسابات الجاهزة في الخلفية
    auto_refill_background: bool = True     # تفعيل خيط التوليد في الخلفية تلقائياً
    background_check_interval: int = 20     # ثواني فحص الخزان في الخلفية
    
    # 📧 إعدادات مزودات البريد المؤقت
    email_provider: str = "tempmailclub"
    preferred_domains: list[str] = field(default_factory=lambda: ["rc.mailings.live", "msp.mailings.live"])
    
    # 🔑 توكن الجلسة (لو تم تمريره يدوياً عبر CLI)
    auth_token: str | None = None
    chat_uuid: str | None = None
    
    # 📂 مسارات ملفات الإدخال والإخراج
    input_file: str = "chat_send.txt"
    output_file: str = "chat_reply.txt"
    
    # 📏 ليمت الأسطر والحروف (None = كامل بدون ليمت)
    max_lines: int | None = None
    max_chars: int | None = None
    
    # ⏱️ مهل الانتظار بالثواني
    otp_timeout: int = 90
    reply_timeout: int = 120
    
    # 🎭 البرومبت العام لنظام Grok
    system_prompt: str = ""


# ======================================================================
# 🗄️ محرك خزان الحسابات وإدارتها الذرية (Account Pool Engine)
# ======================================================================
BASE_DIR = pathlib.Path(__file__).resolve().parent
_pool_lock = threading.Lock()

def get_accounts_file_path(cfg: Config) -> pathlib.Path:
    return BASE_DIR / cfg.accounts_file

def load_accounts_pool(cfg: Config) -> list[dict]:
    """قراءة الحسابات من ملف JSON بأمان مع قفل التزامن"""
    path = get_accounts_file_path(cfg)
    if not path.exists():
        return []
    with _pool_lock:
        try:
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                return []
            return json.loads(content)
        except Exception:
            return []

def save_accounts_pool(accounts: list[dict], cfg: Config):
    """حفظ ذري متزامن في ملف JSON لمنع تلف البيانات (Atomic Write)"""
    path = get_accounts_file_path(cfg)
    tmp_path = path.with_suffix(".tmp")
    with _pool_lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(accounts, f, ensure_ascii=False, indent=2)
            tmp_path.replace(path)
        except Exception as e:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(accounts, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

def get_active_account(cfg: Config) -> dict | None:
    """جلب أول حساب نشط جاهز للاستخدام من الخزان فوراً"""
    accounts = load_accounts_pool(cfg)
    for acc in accounts:
        if acc.get("status") == "active" and acc.get("token"):
            return acc
    return None

def mark_account_expired(token: str, cfg: Config):
    """تحديد الحساب كـ Expired في حالة انتهاء صلاحيته"""
    accounts = load_accounts_pool(cfg)
    updated = False
    for acc in accounts:
        if acc.get("token") == token:
            acc["status"] = "expired"
            acc["expired_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            updated = True
            break
    if updated:
        save_accounts_pool(accounts, cfg)

def add_account_to_pool(email: str, token: str, provider: str, chat_uuid: str | None, cfg: Config):
    """إضافة حساب جديد مفعل إلى الخزان"""
    accounts = load_accounts_pool(cfg)
    new_acc = {
        "email": email,
        "token": token,
        "chat_uuid": chat_uuid,
        "provider": provider,
        "status": "active",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # منع تكرار نفس الإيميل
    accounts = [a for a in accounts if a.get("email") != email]
    accounts.append(new_acc)
    save_accounts_pool(accounts, cfg)


# ======================================================================
# 🛠️ محرك الإيميلات والتسجيل التلقائي (Email Providers Engine)
# ======================================================================
class TempMailClubProvider:
    """عميل temp-mail.club الرسمي المتطابق مع Livewire لدومينات rc.mailings.live"""
    def __init__(self):
        self.session = cffi.Session(impersonate="chrome124")
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
        }
        self.csrf_token = ""
        self.email = ""
        self.app_fingerprint = None
        self.app_server_memo = None

    def create_email(self) -> str | None:
        try:
            r_home = self.session.get('https://temp-mail.club/', headers=self.headers, timeout=15)
            m_csrf = re.search(r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', r_home.text) or re.search(r'content=["\']([^"\']+)["\']\s+name=["\']csrf-token["\']', r_home.text)
            self.csrf_token = m_csrf.group(1) if m_csrf else ''
            
            matches = re.findall(r'wire:initial-data=["\']([^"\']+)["\']', r_home.text)
            action_comp = None
            for m in matches:
                j = json.loads(m.replace('&quot;', '"').replace('&#039;', "'"))
                if j.get('fingerprint', {}).get('name') == 'frontend.actions':
                    action_comp = j
                    break
                    
            if not action_comp:
                return None
                
            lw_headers = {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': self.csrf_token,
                'X-Livewire': 'true',
                'Origin': 'https://temp-mail.club',
                'Referer': 'https://temp-mail.club/',
                'Accept': 'text/html, application/xhtml+xml'
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
            for mb in re.findall(r'wire:initial-data=["\']([^"\']+)["\']', r_box.text):
                mb_j = json.loads(mb.replace('&quot;', '"').replace('&#039;', "'"))
                if mb_j.get('fingerprint', {}).get('name') == 'frontend.app':
                    self.email = mb_j.get('serverMemo', {}).get('data', {}).get('email', '')
                    self.app_fingerprint = mb_j.get('fingerprint')
                    self.app_server_memo = mb_j.get('serverMemo')
                    return self.email
        except Exception:
            pass
        return None

    def poll_otp(self, timeout: int = 75) -> str | None:
        if not self.app_fingerprint or not self.app_server_memo:
            return None
        lw_headers = {
            'Content-Type': 'application/json',
            'X-CSRF-TOKEN': self.csrf_token,
            'X-Livewire': 'true',
            'Origin': 'https://temp-mail.club',
            'Referer': 'https://temp-mail.club/mailbox',
            'Accept': 'text/html, application/xhtml+xml'
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
                    html = res_j.get('effects', {}).get('html', '') or ''
                    msgs = res_j.get('serverMemo', {}).get('data', {}).get('messages', [])
                    for m_item in msgs:
                        content = m_item.get('content', '') or m_item.get('subject', '')
                        m = re.search(r'\b(\d{6})\b', content)
                        if m:
                            return m.group(1)
                    if 'verification code' in html.lower():
                        m = re.search(r'\b(\d{6})\b', html)
                        if m:
                            return m.group(1)
            except Exception:
                pass
        return None


def register_single_syntx_account(cfg: Config, verbose: bool = True) -> tuple[str | None, str | None, str | None]:
    """تسجيل حساب مفرد واستخراج (token, email, provider) عبر مزود TempMailClub"""
    tmc = TempMailClubProvider()
    email = tmc.create_email()
    provider_name = tmc.PROVIDER_NAME

    if not email:
        if verbose:
            print(f"{Fore.RED}❌ تعذر الحصول على إيميل من مزود TempMailClub.{Style.RESET_ALL}")
        return None, None, None
        
    if verbose:
        print(f"{Fore.GREEN}📧 تم توليد الإيميل: {Fore.CYAN}{email} ({provider_name}){Style.RESET_ALL}")
    
    # 1. إرسال كود OTP
    headers_syntx = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    payload_send = {"email": email, "ref_uuid": None, "utm": ""}
    
    try:
        r_send = cffi.post(f"{cfg.base_api_url}/auth/email/send-otp", json=payload_send, headers=headers_syntx, timeout=15)
        if r_send.status_code != 200 or not r_send.json().get("success"):
            if verbose:
                print(f"{Fore.RED}❌ فشل إرسال كود OTP: {r_send.text}{Style.RESET_ALL}")
            return None, None, None
    except Exception as e:
        if verbose:
            print(f"{Fore.RED}❌ خطأ اتصال أثناء إرسال OTP: {e}{Style.RESET_ALL}")
        return None, None, None

    if verbose:
        print(f"{Fore.YELLOW}⏳ تم إرسال كود التحقق — بانتظار استلام الـ OTP...{Style.RESET_ALL}")
    
    # 2. استخراج OTP
    otp_code = tmc.poll_otp(timeout=cfg.otp_timeout)

    if not otp_code:
        if verbose:
            print(f"{Fore.RED}❌ لم يتم استلام كود OTP خلال المهلة.{Style.RESET_ALL}")
        return None, None, None
        
    if verbose:
        print(f"{Fore.GREEN}🎉 تم استلام كود التحقق: {Fore.YELLOW}{otp_code}{Style.RESET_ALL}")
    
    # 3. توثيق OTP
    payload_verify = {"email": email, "otp_code": otp_code, "ref_uuid": None, "utm": ""}
    try:
        r_ver = cffi.post(f"{cfg.base_api_url}/auth/email/verify-otp", json=payload_verify, headers=headers_syntx, timeout=15)
        if r_ver.status_code == 200 and r_ver.json().get("success"):
            token = r_ver.json().get("token")
            return token, email, provider_name
    except Exception:
        pass
        
    return None, None, None


def create_grok_chat(token: str, cfg: Config) -> str | None:
    """إنشاء شات جديد على السيرفر واستخراج chat_uuid"""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    payload = {"title": "Syntx Grok Master Chat", "scope": "text"}
    try:
        r = cffi.post(f"{cfg.base_api_url}/chats", json=payload, headers=headers, timeout=15)
        if r.status_code in [200, 201]:
            return r.json().get("uuid")
    except Exception:
        pass
    return None


# ======================================================================
# 🔄 خيط التوليد الاستباقي في الخلفية (Background Daemon Worker)
# ======================================================================
def _background_pool_refill_worker(cfg: Config):
    """خيط خلفي دائم يفحص خزان الحسابات ويعيد ملئه تلقائياً حتى 5 حسابات"""
    while True:
        try:
            accounts = load_accounts_pool(cfg)
            active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
            needed = cfg.min_pool_size - active_count
            
            if needed > 0:
                token, email, prov = register_single_syntx_account(cfg, verbose=False)
                if token and email:
                    chat_uuid = create_grok_chat(token, cfg)
                    add_account_to_pool(email, token, prov, chat_uuid, cfg)
            
            time.sleep(cfg.background_check_interval)
        except Exception:
            time.sleep(15)

def start_background_account_worker(cfg: Config):
    """بدء تشغيل الخيط الخلفي كـ Daemon Thread"""
    if cfg.auto_refill_background:
        t = threading.Thread(target=_background_pool_refill_worker, args=(cfg,), daemon=True, name="SyntxPoolRefillThread")
        t.start()


# ======================================================================
# 🚀 محرك الشات والتوليد والإحصائيات
# ======================================================================
def print_banner(cfg: Config):
    """طباعة بانر نيون يوضح الموديلات وحالة الخزان"""
    accounts = load_accounts_pool(cfg)
    active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))

    print(f"\n{Fore.GREEN}╔{'═'*74}╗")
    print(f"║  🟢 Syntx AI Master Hub (Grok Hub) — Flagship AI Engine                  ║")
    print(f"║  🚀 تشغيل فوري (0.01s) + خزان خلفي جاهز في {cfg.accounts_file:<27}║")
    print(f"╚{'═'*74}╝{Style.RESET_ALL}")
    
    print(f"{Fore.CYAN}📋 قائمة موديلات Grok المعتمدة في السكربت:")
    for idx, (m_id, m_desc) in enumerate(cfg.available_models.items(), 1):
        active_mark = f"{Fore.GREEN} ◄ [النشط الحالي]" if m_id == cfg.model else ""
        print(f"   {Fore.YELLOW}{idx:2d}. {Fore.WHITE}{m_id:<15} {Fore.LIGHTBLACK_EX}→ {m_desc}{active_mark}{Style.RESET_ALL}")
    
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}🎯 الموديل النشط الحالي : {Fore.YELLOW}{cfg.model}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}🔋 الحسابات الجاهزة بالخزان: {Fore.GREEN}{active_count} / {cfg.min_pool_size} حساب نشط ⚡{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}📂 ملف الإدخال          : {Fore.WHITE}{cfg.input_file}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}💾 ملف الإخراج          : {Fore.WHITE}{cfg.output_file}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}\n")


def read_input_content(cfg: Config) -> tuple[str, str]:
    """قراءة نص الإدخال من ملف chat_send.txt"""
    target_path = BASE_DIR / cfg.input_file
    if target_path.exists():
        try:
            raw_text = target_path.read_text(encoding="utf-8").strip()
            if raw_text:
                lines = raw_text.splitlines()
                if cfg.max_lines and len(lines) > cfg.max_lines:
                    filtered_text = "\n".join(lines[:cfg.max_lines])
                    label = f"ملف ({cfg.input_file}) [تم تحديد أول {cfg.max_lines} سطر]"
                else:
                    filtered_text = raw_text
                    label = f"ملف ({cfg.input_file}) [كامل بدون ليمت]"

                if cfg.max_chars and len(filtered_text) > cfg.max_chars:
                    filtered_text = filtered_text[:cfg.max_chars]
                    label += f" [محدد بـ {cfg.max_chars} حرف]"

                return filtered_text, label
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ تعذر قراءة ملف {cfg.input_file}: {e}{Style.RESET_ALL}")
    return "", ""


def acquire_session_token(cfg: Config) -> tuple[str | None, str | None]:
    """الحصول على توكن نشط: من الخزان فوراً (0.01s) أو إنشاء جديد"""
    # 1. لو تم تمرير توكن يدوياً في CLI
    if cfg.auth_token:
        chat_uuid = cfg.chat_uuid or create_grok_chat(cfg.auth_token, cfg)
        return cfg.auth_token, chat_uuid

    # 2. سحب حساب جاهز من خزان الحسابات
    acc = get_active_account(cfg)
    if acc:
        token = acc["token"]
        chat_uuid = acc.get("chat_uuid") or create_grok_chat(token, cfg)
        return token, chat_uuid

    # 3. لو الخزان فارغ: توليد حساب فوري
    token, email, prov = register_single_syntx_account(cfg, verbose=True)
    if token and email:
        chat_uuid = create_grok_chat(token, cfg)
        add_account_to_pool(email, token, prov, chat_uuid, cfg)
        return token, chat_uuid

    return None, None


def send_grok_message(prompt_text: str, cfg: Config, source_label: str = "مباشر", image_urls: list[str] | None = None) -> str | None:
    """إرسال السؤال إلى سيرفر Syntx AI واستقبال الرد الكامل مع حساب الإحصائيات"""
    token, chat_uuid = acquire_session_token(cfg)
    if not token or not chat_uuid:
        print(f"{Fore.RED}❌ فشل توفير جلسة شات صالحة لـ Syntx AI.{Style.RESET_ALL}")
        return None

    char_count = len(prompt_text)
    line_count = len(prompt_text.splitlines())
    word_count = len(prompt_text.split())
    approx_tokens = int(char_count / 3.5)

    print(f"{Fore.MAGENTA}┌─── 📊 إحصائيات السؤال ({source_label}) ────────────────────────┐")
    print(f"│ 🤖 الموديل     : {Fore.YELLOW}{cfg.model}{Fore.MAGENTA}")
    print(f"│ 📝 عدد الحروف : {Fore.YELLOW}{char_count:,}{Fore.MAGENTA} حرف (بدون ليمت)")
    print(f"│ 📄 عدد الأسطر  : {Fore.YELLOW}{line_count:,}{Fore.MAGENTA} سطر")
    print(f"│ 🔤 عدد الكلمات : {Fore.YELLOW}{word_count:,}{Fore.MAGENTA} كلمة")
    print(f"│ 🪙 Tokens تقريبي: {Fore.YELLOW}~{approx_tokens:,}{Fore.MAGENTA}")
    print(f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

    print(f"{Fore.YELLOW}⏳ جاري إرسال الطلب لـ [{cfg.model}] واستقبال الرد...{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}🤖 الرد المباشر ({cfg.model}):{Style.RESET_ALL}\n" + f"{Fore.CYAN}{'─'*74}{Style.RESET_ALL}")

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }

    objects = []
    if cfg.system_prompt.strip():
        objects.append({"object_type": "text", "object_url": None, "object_text": cfg.system_prompt, "model_type": cfg.model})
    if prompt_text.strip():
        objects.append({"object_type": "text", "object_url": None, "object_text": prompt_text, "model_type": cfg.model})

    if image_urls:
        for img_u in image_urls:
            try:
                r_img = cffi.get(img_u, timeout=15)
                if r_img.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_f:
                        tmp_f.write(r_img.content)
                        tmp_path = tmp_f.name
                    files_payload = {'files': (os.path.basename(tmp_path), open(tmp_path, 'rb'), 'application/octet-stream')}
                    data_payload = {'check_duplicates': 'true', 'chat_uuid': chat_uuid}
                    r_up = cffi.post(f"{cfg.base_api_url}/chats/upload-files", data=data_payload, files=files_payload, headers={"Authorization": f"Bearer {token}"})
                    if r_up.status_code == 200 and r_up.json().get('successful', 0) > 0:
                        uploaded_url = r_up.json()['files'][0]['url']
                        objects.append({"object_type": "image", "object_url": uploaded_url, "object_text": os.path.basename(tmp_path), "model_type": cfg.model})
                    os.unlink(tmp_path)
            except Exception as e:
                print(f"{Fore.RED}⚠️ خطأ أثناء رفع الصورة: {e}{Style.RESET_ALL}")

    t0 = time.time()
    try:
        r_send = cffi.post(f"{cfg.base_api_url}/chats/{chat_uuid}/messages?ai_name=grok",
                           json={"objects": objects},
                           headers=headers,
                           timeout=cfg.reply_timeout)
        if r_send.status_code != 200:
            print(f"{Fore.RED}❌ فشل إرسال الرسالة للسيرفر: {r_send.status_code} {r_send.text}{Style.RESET_ALL}")
            if r_send.status_code in [401, 403]:
                mark_account_expired(token, cfg)
            return None

        sent_msg_id = r_send.json().get("id")
        if not sent_msg_id:
            print(f"{Fore.RED}❌ تعذر استخراج معرّف الرسالة من السيرفر.{Style.RESET_ALL}")
            return None

        # 2. استعلام الرد (Polling Loop)
        bot_reply = None
        poll_start = time.time()
        while time.time() - poll_start < cfg.reply_timeout:
            time.sleep(1.2)
            r_poll = cffi.get(f"{cfg.base_api_url}/chats/{chat_uuid}/messages?page_size=20", headers=headers, timeout=15)
            if r_poll.status_code == 200:
                messages = r_poll.json().get("messages", [])
                for msg in messages:
                    if msg.get("author_id") == -1 and msg.get("id", 0) > sent_msg_id:
                        msg_obj = msg.get("message_object", [{}])[0]
                        if msg_obj and msg_obj.get("object_type") == "text" and msg_obj.get("completed"):
                            bot_reply = msg_obj.get("object_text", "")
                            break
                if bot_reply is not None:
                    break

        if bot_reply:
            elapsed = time.time() - t0
            print(f"{Fore.WHITE}{bot_reply}{Style.RESET_ALL}")
            
            out_chars = len(bot_reply)
            out_lines = len(bot_reply.splitlines())
            out_words = len(bot_reply.split())
            speed = out_chars / elapsed if elapsed > 0 else 0

            print(f"\n{Fore.CYAN}{'─'*74}{Style.RESET_ALL}")
            print(f"\n{Fore.GREEN}┌─── 🏆 إحصائيات الرد وسرعة التوليد ────────────────────────┐")
            print(f"│ ⏱️  الوقت المستغرق: {Fore.YELLOW}{elapsed:.2f} ثانية")
            print(f"│ 📝 حروف الرد     : {Fore.YELLOW}{out_chars:,}{Fore.GREEN} حرف")
            print(f"│ 📄 أسطر الرد     : {Fore.YELLOW}{out_lines:,}{Fore.GREEN} سطر")
            print(f"│ 🔤 كلمات الرد    : {Fore.YELLOW}{out_words:,}{Fore.GREEN} كلمة")
            print(f"│ ⚡ معدل التوليد  : {Fore.YELLOW}{speed:.1f}{Fore.GREEN} حرف/ثانية")
            print(f"│ 🏷️  الموديل الفعلي: {Fore.YELLOW}{cfg.model}")
            print(f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

            # حفظ الرد كاملاً في الملف المحدد
            out_path = BASE_DIR / cfg.output_file
            try:
                out_path.write_text(bot_reply, encoding="utf-8")
                print(f"{Fore.GREEN}💾 تم حفظ الرد كاملاً في: {Fore.CYAN}{cfg.output_file}{Style.RESET_ALL}\n")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ تعذر حفظ الرد في ملف: {e}{Style.RESET_ALL}\n")

            return bot_reply
        else:
            print(f"\n{Fore.RED}❌ لم يتم اكتمال توليد الرد خلال المهلة الزمنية.{Style.RESET_ALL}\n")
            return None

    except Exception as e:
        print(f"\n{Fore.RED}⚠️ فشل الاتصال: {e}{Style.RESET_ALL}\n")
        return None


def interactive_chat_mode(cfg: Config):
    """وضع الشات التفاعلي المفتوح (بدون ليمت رسائل)"""
    print(f"{Fore.YELLOW}💬 الوضع التفاعلي المفتوح جاهز (الموديل: {cfg.model}) - اكتب 'exit' للخروج:{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}💡 لإرفاق صور: اكتب نص السؤال||رابط_الصورة1,رابط_الصورة2{Style.RESET_ALL}\n")
    
    msg_count = 0
    while True:
        try:
            user_input = input(f"{Fore.WHITE}👤 أنت: {Style.RESET_ALL}").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', 'خروج', 'q']:
                print(f"{Fore.RED}👋 تم إنهاء الجلسة بنجاح!{Style.RESET_ALL}")
                break

            prompt = user_input
            image_urls = []
            if "||" in user_input:
                parts = user_input.split("||", 1)
                prompt = parts[0].strip()
                if parts[1].strip():
                    image_urls = [x.strip() for x in parts[1].split(",") if x.strip()]

            send_grok_message(prompt, cfg, f"شات تفاعلي #{msg_count+1}", image_urls)
            msg_count += 1
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.RED}⛔ تم إيقاف الجلسة.{Style.RESET_ALL}")
            break


def main():
    """نقطة الدخول الرئيسية - تدعم الـ CLI وزر Run المباشر وتشغيل الخيط الخلفي"""
    parser = argparse.ArgumentParser(description="Syntx AI Master Hub (Grok Hub) — Flagship AI Engine")
    parser.add_argument("prompt", nargs="*", help="نص السؤال مباشرة من التيرمينال")
    parser.add_argument("--model", "-m", type=str, default=None, help="تحديد الموديل (grok-4.5, grok-4.3, grok-4, grok-3)")
    parser.add_argument("--provider", "-p", type=str, default=None, help="تحديد مزود البريد (tempmailclub)")
    parser.add_argument("--token", "-t", type=str, default=None, help="تمرير توكن الجلسة يدوياً")
    parser.add_argument("--pool-size", type=int, default=None, help="تحديد عدد الحسابات الجاهزة بالخزان")
    parser.add_argument("--file", "-f", type=str, default=None, help="تحديد ملف الإدخال (الافتراضي chat_send.txt)")
    parser.add_argument("--output", "-o", type=str, default=None, help="تحديد ملف الإخراج (الافتراضي chat_reply.txt)")
    parser.add_argument("--cli", action="store_true", help="بدء الشات التفاعلي فوراً")
    args = parser.parse_args()

    cfg = Config()

    if args.provider:
        cfg.email_provider = args.provider
    if args.token:
        cfg.auth_token = args.token
    if args.model:
        cfg.model = args.model
    if args.pool_size:
        cfg.min_pool_size = args.pool_size
    if args.file:
        cfg.input_file = args.file
    if args.output:
        cfg.output_file = args.output

    # بدء تشغيل خيط توليد الحسابات مسبقاً في الخلفية
    start_background_account_worker(cfg)

    print_banner(cfg)

    # 1. لو تم إرسال برومبت مباشرة في أمر التشغيل
    if args.prompt:
        direct_prompt = " ".join(args.prompt).strip()
        send_grok_message(direct_prompt, cfg, "CLI Argument")
        return

    # 2. لو طلب وضع الشات التفاعلي صراحة
    if args.cli:
        interactive_chat_mode(cfg)
        return

    # 3. الوضع التلقائي الأساسي: قراءة ملف chat_send.txt
    content, label = read_input_content(cfg)
    if content:
        print(f"{Fore.GREEN}📂 تم العثور على نص جاهز في: {Fore.YELLOW}{cfg.input_file}{Style.RESET_ALL}")
        send_grok_message(content, cfg, label)
    else:
        print(f"{Fore.YELLOW}ℹ️ ملف {cfg.input_file} فارغ أو غير موجود. تم التحويل للوضع التفاعلي.{Style.RESET_ALL}\n")
        interactive_chat_mode(cfg)


if __name__ == "__main__":
    main()
