# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════════
🟢 Syntx AI Master Hub — The Elite 4 AI Models (GPT 5.6, Claude, Grok 4.6)
══════════════════════════════════════════════════════════════════════
- كلاس كونفج موحد وشامل (SSOT) في أول السكربت يتحكم في كل المتغيرات.
- النخبة المعتمدة من الموديلات:
    1. 🌟 GPT 5.6 Terra    (gpt-5.6-terra  - OpenAI Flagship)
    2. 🌟 Claude Opus 4.8  (claude-opus-4-8 - Anthropic Elite Architecture)
    3. 🌟 Claude Sonnet 5  (claude-sonnet-5 - Anthropic Ultra-Fast Logic)
    4. 🌟 Grok 4.6         (grok-4.6       - xAI Latest Flagship)
- تفعيل افتراضي دائم لأقوى القدرات:
    • Thinking Mode ON  (التفكير المتسلسل العميق Chain-of-Thought)
    • Planning Mode ON  (التخطيط المنهجي وتتبع خطوات المهام)
    • Web Search / Deep Research ON (البحث الحي على الويب والأدوات البرمجية)
- خزان حسابات استباقي (Account Pool) في ملف accounts_syntx.json:
    • سحب فوري للحسابات الجاهزة في 0.01 ثانية (Zero Startup Latency).
    • خيط خلفي ذكي (Background Daemon Thread) يولد 5 حسابات تلقائياً.
    • حماية ذرية للملفات (Atomic Write & Thread-Safe Locking).
- محرك بريد متطور:
    • 🌟 Temp-Mail.club (Livewire + rc.mailings.live / msp.mailings.live).
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
    # 🤖 الموديل الافتراضي المستخدم (Claude Opus 4.8)
    model: str = "claude-opus-4-8"
    
    # 📋 قائمة النخبة المعتمدة حصرياً في السكربت (4 موديلات فقط)
    available_models: dict = field(default_factory=lambda: {
        "gpt-5.6-terra":   {"label": "🌟 GPT 5.6 Terra",   "ai_name": "chatgpt", "desc": "الجيل الجديد الخارق من OpenAI للاستنتاج والبرمجة"},
        "claude-opus-4-8": {"label": "🌟 Claude Opus 4.8", "ai_name": "claude",  "desc": "أقوى وأعمق موديل في Anthropic للهندسة المعمارية"},
        "claude-sonnet-5": {"label": "🌟 Claude Sonnet 5", "ai_name": "claude",  "desc": "الجيل الخامس فائق السرعة والدقة من Sonnet"},
        "grok-4.6":        {"label": "🌟 Grok 4.6",        "ai_name": "grok",    "desc": "أحدث وأقوى إصدارات جروك من xAI للاستدلال المنطقي"},
    })
    
    # 🧠 قدرات التفكير والتخطيط والبحث المتقدمة (مفعّلة دائماً وافتراضياً)
    thinking: bool = True               # تفعيل التفكير العميق (Chain-of-Thought) - مفعّل دائماً
    plan: bool = True                   # تفعيل وضع التخطيط المنهجي (Planning Mode) - مفعّل دائماً
    deep_research: bool = True          # تفعيل البحث العميق والبحث على الويب - مفعّل دائماً
    enable_tools: bool = True           # تفعيل أدوات البحث والأكواد (search, code, shell, files) - مفعّل دائماً
    
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
    
    # 🎭 البرومبت العام للنظام
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
    """تحديد الحساب كـ Expired في حالة انتهاء صلاحيته أو الرصيد"""
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
    accounts = [a for a in accounts if a.get("email") != email]
    accounts.append(new_acc)
    save_accounts_pool(accounts, cfg)


# ======================================================================
# 🛠️ محرك الإيميلات والتسجيل التلقائي (Email Providers Engine)
# ======================================================================
class TempMailClubProvider:
    """عميل temp-mail.club الرسمي المتطابق مع Livewire لدومينات rc.mailings.live مع تدوير IP"""
    def __init__(self):
        self.PROVIDER_NAME = "tempmailclub"
        self.session = cffi.Session(impersonate="chrome124")
        self.fake_ip = f"{random.randint(11, 190)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'X-Forwarded-For': self.fake_ip,
            'X-Real-IP': self.fake_ip,
            'Client-IP': self.fake_ip,
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


def create_syntx_chat(token: str, cfg: Config) -> str | None:
    """إنشاء شات جديد على السيرفر واستخراج chat_uuid"""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    payload = {"title": "Syntx Master Chat", "scope": "text"}
    try:
        r = cffi.post(f"{cfg.base_api_url}/chats", json=payload, headers=headers, timeout=15)
        if r.status_code in [200, 201]:
            return r.json().get("uuid")
    except Exception:
        pass
    return None


def refill_accounts_pool(cfg: Config, target_size: int | None = None, verbose: bool = True):
    """ملء خزان الحسابات إلى العدد المستهدف مع طباعة التقدم"""
    target = target_size or cfg.min_pool_size
    accounts = load_accounts_pool(cfg)
    active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
    
    if verbose:
        print(f"\n{Fore.CYAN}🔋 فحص خزان الحسابات: {Fore.YELLOW}{active_count} / {target} حساب نشط.{Style.RESET_ALL}")
    
    while active_count < target:
        if verbose:
            print(f"{Fore.YELLOW}⏳ جاري تسجيل حساب نشط جديد ({active_count + 1} من {target})...{Style.RESET_ALL}")
        token, email, prov = register_single_syntx_account(cfg, verbose=verbose)
        if token and email:
            chat_uuid = create_syntx_chat(token, cfg)
            add_account_to_pool(email, token, prov, chat_uuid, cfg)
            if verbose:
                print(f"{Fore.GREEN}✅ تم تفعيل وتثبيت الحساب في الخزان: {Fore.WHITE}{email}{Style.RESET_ALL}\n")
        else:
            if verbose:
                print(f"{Fore.RED}⚠️ فشل تسجيل الحساب، جاري إعادة المحاولة...{Style.RESET_ALL}\n")
            time.sleep(3)
            
        accounts = load_accounts_pool(cfg)
        active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))

    if verbose:
        print(f"{Fore.GREEN}🎉 اكتمل ملء خزان الحسابات بنجاح! الإجمالي: {Fore.YELLOW}{active_count} حساب نشط ⚡{Style.RESET_ALL}\n")


def _background_pool_refill_worker(cfg: Config):
    """خيط خلفي دائم يفحص خزان الحسابات ويعيد ملئه تلقائياً حتى 5 حسابات بدون توقف"""
    while True:
        try:
            accounts = load_accounts_pool(cfg)
            active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
            
            while active_count < cfg.min_pool_size:
                token, email, prov = register_single_syntx_account(cfg, verbose=False)
                if token and email:
                    chat_uuid = create_syntx_chat(token, cfg)
                    add_account_to_pool(email, token, prov, chat_uuid, cfg)
                else:
                    time.sleep(3)
                accounts = load_accounts_pool(cfg)
                active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
            
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
    """طباعة بانر نيون يوضح النخبة المختارة وحالة التفكير والخزان"""
    accounts = load_accounts_pool(cfg)
    active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))

    print(f"\n{Fore.GREEN}╔{'═'*74}╗")
    print(f"║  🟢 Syntx AI Master Hub — The Elite 4 AI Models (GPT 5.6, Claude, Grok 4.6)  ║")
    print(f"║  🚀 تشغيل فوري (0.01s) + خزان خلفي جاهز في {cfg.accounts_file:<27}║")
    print(f"╚{'═'*74}╝{Style.RESET_ALL}")
    
    print(f"{Fore.CYAN}📋 قائمة النخبة المعتمدة (اختر بالرقم أو الاسم):")
    for idx, (m_id, m_info) in enumerate(cfg.available_models.items(), 1):
        active_mark = f"{Fore.GREEN} ◄ [النشط الحالي]" if m_id == cfg.model else ""
        print(f"   {Fore.YELLOW}{idx}. {Fore.WHITE}{m_info['label']:<18} {Fore.LIGHTBLACK_EX}({m_id}) → {m_info['desc']}{active_mark}{Style.RESET_ALL}")
    
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}")
    current_info = cfg.available_models.get(cfg.model, {"label": cfg.model, "ai_name": "auto"})
    th_status = f"{Fore.GREEN}مفعّل دائماً ✅" if cfg.thinking else f"{Fore.RED}معطّل ❌"
    pl_status = f"{Fore.GREEN}مفعّل دائماً ✅" if cfg.plan else f"{Fore.RED}معطّل ❌"
    sr_status = f"{Fore.GREEN}مفعّل دائماً ✅" if cfg.deep_research else f"{Fore.RED}معطّل ❌"
    
    print(f"{Fore.MAGENTA}🎯 الموديل النشط الحالي : {Fore.YELLOW}{current_info['label']} ({cfg.model}){Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}🧠 التفكير (Thinking) : {th_status} {Fore.MAGENTA}| 📋 التخطيط (Planning): {pl_status}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}🌐 بحث الويب (Search)  : {sr_status} {Fore.MAGENTA}| 🛠️ أدوات البرمجة: {Fore.GREEN}مفعّلة ✅{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}🔋 الحسابات بالخزان     : {Fore.GREEN}{active_count} / {cfg.min_pool_size} حساب نشط ⚡{Style.RESET_ALL}")
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
    if cfg.auth_token:
        chat_uuid = cfg.chat_uuid or create_syntx_chat(cfg.auth_token, cfg)
        return cfg.auth_token, chat_uuid

    acc = get_active_account(cfg)
    if acc:
        token = acc["token"]
        chat_uuid = acc.get("chat_uuid") or create_syntx_chat(token, cfg)
        return token, chat_uuid

    token, email, prov = register_single_syntx_account(cfg, verbose=True)
    if token and email:
        chat_uuid = create_syntx_chat(token, cfg)
        add_account_to_pool(email, token, prov, chat_uuid, cfg)
        return token, chat_uuid

    return None, None


def send_syntx_message(prompt_text: str, cfg: Config, source_label: str = "مباشر", image_urls: list[str] | None = None) -> str | None:
    """إرسال السؤال واستقبال الرد عبر المحرك الرسمي الشامل لـ Syntx AI"""
    token, chat_uuid = acquire_session_token(cfg)
    if not token or not chat_uuid:
        print(f"{Fore.RED}❌ فشل توفير جلسة شات صالحة لـ Syntx AI.{Style.RESET_ALL}")
        return None

    m_info = cfg.available_models.get(cfg.model, {"label": cfg.model, "ai_name": "chatgpt"})
    ai_name = m_info["ai_name"]

    char_count = len(prompt_text)
    line_count = len(prompt_text.splitlines())
    word_count = len(prompt_text.split())
    approx_tokens = int(char_count / 3.5)

    print(f"{Fore.MAGENTA}┌─── 📊 إحصائيات السؤال ({source_label}) ────────────────────────┐")
    print(f"│ 🤖 الموديل     : {Fore.YELLOW}{m_info['label']} ({cfg.model}){Fore.MAGENTA}")
    print(f"│ 🧠 التفكير     : {Fore.YELLOW}{'ON (عميق)' if cfg.thinking else 'OFF'}{Fore.MAGENTA} | 📋 التخطيط: {Fore.YELLOW}{'ON' if cfg.plan else 'OFF'}{Fore.MAGENTA} | 🌐 البحث: {Fore.YELLOW}{'ON' if cfg.deep_research else 'OFF'}{Fore.MAGENTA}")
    print(f"│ 📝 عدد الحروف : {Fore.YELLOW}{char_count:,}{Fore.MAGENTA} حرف (بدون ليمت)")
    print(f"│ 📄 عدد الأسطر  : {Fore.YELLOW}{line_count:,}{Fore.MAGENTA} سطر")
    print(f"│ 🔤 عدد الكلمات : {Fore.YELLOW}{word_count:,}{Fore.MAGENTA} كلمة")
    print(f"│ 🪙 Tokens تقريبي: {Fore.YELLOW}~{approx_tokens:,}{Fore.MAGENTA}")
    print(f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

    print(f"{Fore.YELLOW}⏳ جاري إرسال الطلب لـ [{m_info['label']}] واستقبال الرد...{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}🤖 الرد المباشر ({m_info['label']}):{Style.RESET_ALL}\n" + f"{Fore.CYAN}{'─'*74}{Style.RESET_ALL}")

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }

    backend_model = cfg.model
    tools_list = ["search", "code", "shell", "files", "charts"] if cfg.enable_tools else []
    payload = {
        "chat_uuid": chat_uuid,
        "text": prompt_text,
        "model": backend_model,
        "thinking": cfg.thinking,
        "plan": cfg.plan,
        "deep_research": cfg.deep_research,
        "tools": tools_list
    }

    t0 = time.time()
    try:
        r_gen = cffi.post(f"{cfg.base_api_url}/llm/generate?ai_name={ai_name}", json=payload, headers=headers, timeout=cfg.reply_timeout)
        
        if r_gen.status_code == 400 and backend_model == "grok-4.6":
            payload["model"] = "grok-4.5"
            r_gen = cffi.post(f"{cfg.base_api_url}/llm/generate?ai_name={ai_name}", json=payload, headers=headers, timeout=cfg.reply_timeout)

        if r_gen.status_code in [429, 401, 403]:
            print(f"{Fore.YELLOW}⚠️ انتهى رصيد الجلسة الحالية. جاري التبديل لحساب نشط آخر من الخزان...{Style.RESET_ALL}")
            mark_account_expired(token, cfg)
            return send_syntx_message(prompt_text, cfg, source_label, image_urls)

        bot_reply = None
        if r_gen.status_code == 200:
            poll_start = time.time()
            while time.time() - poll_start < cfg.reply_timeout:
                time.sleep(1.2)
                r_poll = cffi.get(f"{cfg.base_api_url}/chats/{chat_uuid}/messages?page_size=20", headers=headers, timeout=15)
                if r_poll.status_code == 200:
                    messages = r_poll.json().get("messages", [])
                    # قراءة الرسائل من الأحدث إلى الأقدم لضمان التقاط رد السؤال الحالي
                    for msg in reversed(messages):
                        if msg.get("author_id") == -1:
                            m_objs = msg.get("message_object", [])
                            for obj in m_objs:
                                if obj.get("object_type") == "text" and obj.get("completed"):
                                    bot_reply = obj.get("object_text", "")
                                    break
                        if bot_reply:
                            break
                if bot_reply:
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
            print(f"│ 🏷️  الموديل الفعلي: {Fore.YELLOW}{m_info['label']}")
            print(f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

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
    """وضع الشات التفاعلي مع إمكانية تبديل الموديلات والتفكير والبحث فوراً"""
    print(f"{Fore.YELLOW}💬 الوضع التفاعلي المفتوح جاهز - اكتب 'exit' للخروج{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}💡 أوامر التبديل السريع: اكتب '1' لـ GPT 5.6، '2' لـ Opus 4.8، '3' لـ Sonnet 5، '4' لـ Grok 4.6{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}💡 أوامر القدرات: 'th on/off' (تفكير) | 'pl on/off' (تخطيط) | 'sr on/off' (بحث ويب){Style.RESET_ALL}\n")
    
    msg_count = 0
    while True:
        try:
            m_label = cfg.available_models.get(cfg.model, {}).get("label", cfg.model)
            user_input = input(f"{Fore.WHITE}👤 أنت [{Fore.YELLOW}{m_label}{Fore.WHITE}]: {Style.RESET_ALL}").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', 'خروج', 'q']:
                print(f"{Fore.RED}👋 تم إنهاء الجلسة بنجاح!{Style.RESET_ALL}")
                break

            if user_input.lower() in ['m1', '1', 'gpt']:
                cfg.model = "gpt-5.6-terra"
                print(f"{Fore.GREEN}🔄 تم التحويل للموديل: {cfg.available_models[cfg.model]['label']}{Style.RESET_ALL}\n")
                continue
            elif user_input.lower() in ['m2', '2', 'opus']:
                cfg.model = "claude-opus-4-8"
                print(f"{Fore.GREEN}🔄 تم التحويل للموديل: {cfg.available_models[cfg.model]['label']}{Style.RESET_ALL}\n")
                continue
            elif user_input.lower() in ['m3', '3', 'sonnet']:
                cfg.model = "claude-sonnet-5"
                print(f"{Fore.GREEN}🔄 تم التحويل للموديل: {cfg.available_models[cfg.model]['label']}{Style.RESET_ALL}\n")
                continue
            elif user_input.lower() in ['m4', '4', 'grok']:
                cfg.model = "grok-4.6"
                print(f"{Fore.GREEN}🔄 تم التحويل للموديل: {cfg.available_models[cfg.model]['label']}{Style.RESET_ALL}\n")
                continue
            elif user_input.lower() == 'th on':
                cfg.thinking = True
                print(f"{Fore.GREEN}🧠 تم تفعيل وضع التفكير العميق (Thinking: ON){Style.RESET_ALL}\n")
                continue
            elif user_input.lower() == 'th off':
                cfg.thinking = False
                print(f"{Fore.YELLOW}🧠 تم تعطيل وضع التفكير العميق (Thinking: OFF){Style.RESET_ALL}\n")
                continue
            elif user_input.lower() == 'pl on':
                cfg.plan = True
                print(f"{Fore.GREEN}📋 تم تفعيل وضع التخطيط المنهجي (Planning: ON){Style.RESET_ALL}\n")
                continue
            elif user_input.lower() == 'pl off':
                cfg.plan = False
                print(f"{Fore.YELLOW}📋 تم تعطيل وضع التخطيط المنهجي (Planning: OFF){Style.RESET_ALL}\n")
                continue
            elif user_input.lower() in ['sr on', 'search on']:
                cfg.deep_research = True
                print(f"{Fore.GREEN}🌐 تم تفعيل بحث الويب العميق (Search: ON){Style.RESET_ALL}\n")
                continue
            elif user_input.lower() in ['sr off', 'search off']:
                cfg.deep_research = False
                print(f"{Fore.YELLOW}🌐 تم تعطيل بحث الويب (Search: OFF){Style.RESET_ALL}\n")
                continue

            send_syntx_message(user_input, cfg, f"شات تفاعلي #{msg_count+1}")
            msg_count += 1
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.RED}⛔ تم إيقاف الجلسة.{Style.RESET_ALL}")
            break


def main():
    """نقطة الدخول الرئيسية - تدعم الـ CLI واختيار الموديلات والتفكير والبحث"""
    parser = argparse.ArgumentParser(description="Syntx AI Master Hub — The Elite 4 AI Models")
    parser.add_argument("prompt", nargs="*", help="نص السؤال مباشرة من التيرمينال")
    parser.add_argument("--model", "-m", type=str, default=None, help="تحديد الموديل: 1 (gpt-5.6), 2 (opus-4.8), 3 (sonnet-5), 4 (grok-4.6)")
    parser.add_argument("--no-thinking", action="store_true", help="تعطيل وضع التفكير العميق")
    parser.add_argument("--no-plan", action="store_true", help="تعطيل وضع التخطيط المنهجي")
    parser.add_argument("--no-search", action="store_true", help="تعطيل بحث الويب والأدوات")
    parser.add_argument("--refill", action="store_true", help="ملء خزان الحسابات إلى 5 حسابات فوراً مع طباعة التقدم")
    parser.add_argument("--count", "-c", action="store_true", help="عرض عدد الحسابات النشطة في الخزان فقط")
    parser.add_argument("--pool-size", type=int, default=None, help="تحديد عدد الحسابات الجاهزة بالخزان")
    parser.add_argument("--file", "-f", type=str, default=None, help="تحديد ملف الإدخال (الافتراضي chat_send.txt)")
    parser.add_argument("--output", "-o", type=str, default=None, help="تحديد ملف الإخراج (الافتراضي chat_reply.txt)")
    parser.add_argument("--cli", action="store_true", help="بدء الشات التفاعلي فوراً")
    args = parser.parse_args()

    cfg = Config()

    model_num_map = {
        "1": "gpt-5.6-terra",
        "2": "claude-opus-4-8",
        "3": "claude-sonnet-5",
        "4": "grok-4.6"
    }

    if args.model:
        selected = model_num_map.get(args.model, args.model)
        if selected in cfg.available_models:
            cfg.model = selected
    if args.no_thinking:
        cfg.thinking = False
    if args.no_plan:
        cfg.plan = False
    if args.no_search:
        cfg.deep_research = False
        cfg.enable_tools = False
    if args.pool_size:
        cfg.min_pool_size = args.pool_size
    if args.file:
        cfg.input_file = args.file
    if args.output:
        cfg.output_file = args.output

    # لو تم طلب عرض عدد الحسابات فقط
    if args.count:
        accounts = load_accounts_pool(cfg)
        active = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
        print(f"\n{Fore.CYAN}📊 إجمالي الحسابات النشطة في الخزان: {Fore.GREEN}{active}{Style.RESET_ALL} حساب جاهز.\n")
        return

    # لو تم طلب ملء الخزان فورياً
    if args.refill:
        refill_accounts_pool(cfg, target_size=cfg.min_pool_size, verbose=True)
        return

    # ضمان وجود 5 حسابات جاهزة بالخزان عند تشغيل الشات
    accounts = load_accounts_pool(cfg)
    active_count = sum(1 for a in accounts if a.get("status") == "active" and a.get("token"))
    if active_count < cfg.min_pool_size:
        refill_accounts_pool(cfg, target_size=cfg.min_pool_size, verbose=True)

    start_background_account_worker(cfg)

    print_banner(cfg)

    if args.prompt:
        direct_prompt = " ".join(args.prompt).strip()
        send_syntx_message(direct_prompt, cfg, "CLI Argument")
        return

    if args.cli:
        interactive_chat_mode(cfg)
        return

    content, label = read_input_content(cfg)
    if content:
        print(f"{Fore.GREEN}📂 تم العثور على نص جاهز في: {Fore.YELLOW}{cfg.input_file}{Style.RESET_ALL}")
        send_syntx_message(content, cfg, label)
    else:
        print(f"{Fore.YELLOW}ℹ️ ملف {cfg.input_file} فارغ أو غير موجود. تم التحويل للوضع التفاعلي.{Style.RESET_ALL}\n")
        interactive_chat_mode(cfg)


if __name__ == "__main__":
    main()
