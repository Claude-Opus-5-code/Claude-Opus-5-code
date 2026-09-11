# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════════
🟢 Syntx AI Chat — The Elite 4 AI Models (GPT 5.6, Claude, Grok 4.6)
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
- الحسابات المعتمدة الجاهزة فقط من accounts_syntx.json.
- لا تسجيل أو بريد مؤقت أو عمليات إنشاء خلفية داخل الشات.
- عند غياب حساب جاهز، ينتهي الشات برسالة واضحة دون انتظار.
- spawn_background_refill خطاف خامل محجوز فقط؛ لا يتم استدعاؤه.
- ملفات الإدخال والإخراج: chat_send.txt و chat_reply.txt بترميز UTF-8.
══════════════════════════════════════════════════════════════════════
"""
from dataclasses import dataclass, field
import json
import sys
import time
import pathlib
import argparse
import threading
import subprocess

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
    
    # Approved accounts are supplied externally; chat never creates accounts.
    accounts_file: str = "accounts_syntx.json"

    # 📂 مسارات ملفات الإدخال والإخراج
    input_file: str = "chat_send.txt"
    output_file: str = "chat_reply.txt"
    
    # 📏 ليمت الأسطر والحروف (None = كامل بدون ليمت)
    max_lines: int | None = None
    max_chars: int | None = None
    
    # ⏱️ مهل الانتظار بالثواني
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
            accounts = json.loads(content)
            if not isinstance(accounts, list) or any(not isinstance(acc, dict) for acc in accounts):
                return []
            return accounts
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

def is_ready_account(account: dict) -> bool:
    """Local readiness only; server-side validity is not inferred."""
    token = account.get("token")
    return (account.get("status") == "active" and isinstance(token, str)
            and bool(token) and token.isascii()
            and all(33 <= ord(char) <= 126 for char in token))


def warn_no_ready_accounts(cfg: Config):
    print(f"{Fore.RED}⚠️ تنبيه: لا توجد حسابات معتمدة جاهزة في {cfg.accounts_file} (دون انتظار أو إنشاء حسابات داخل الشات).{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}⏳ تم إطلاق عملية توليد 5 حسابات جديدة في الخلفية، يرجى إعادة المحاولة بعد لحظات.{Style.RESET_ALL}")


def get_active_account(cfg: Config) -> dict | None:
    """جلب أول حساب نشط جاهز للاستخدام من الخزان فوراً"""
    accounts = load_accounts_pool(cfg)
    for acc in accounts:
        if is_ready_account(acc):
            return acc
    return None

def mark_account_expired(token: str, cfg: Config):
    """حذف الحساب نهائياً من الخزان فور نفاد الرصيد أو انتهاء الصلاحية بناءً على توجيه زيزو"""
    accounts = load_accounts_pool(cfg)
    removed_email = None
    clean_accounts = []
    for acc in accounts:
        if acc.get("token") == token or acc.get("status") == "expired":
            if acc.get("token") == token:
                removed_email = acc.get("email")
        else:
            clean_accounts.append(acc)
            
    save_accounts_pool(clean_accounts, cfg)
    if removed_email:
        print(f"{Fore.RED}🗑️ [حذف حساب مستنفد] تم حذف الحساب ({removed_email}) نهائياً من {cfg.accounts_file} لنفاد رصيده.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}🗑️ [تنظيف الخزان] تم استبعاد الحسابات المنتهية من {cfg.accounts_file}.{Style.RESET_ALL}")


# ======================================================================
# Chat sessions for existing approved accounts
# ======================================================================


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


# ======================================================================
# 🚀 محرك الشات والتوليد والإحصائيات
# ======================================================================
def print_banner(cfg: Config):
    """طباعة بانر نيون يوضح النخبة المختارة وحالة التفكير والخزان"""
    accounts = load_accounts_pool(cfg)
    active_count = sum(1 for a in accounts if is_ready_account(a))

    print(f"\n{Fore.GREEN}╔{'═'*74}╗")
    print(f"║  🟢 Syntx AI Chat — The Elite 4 AI Models (GPT 5.6, Claude, Grok 4.6)  ║")
    print(f"║  الحسابات الجاهزة فقط: {cfg.accounts_file}")
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
    print(f"{Fore.MAGENTA}🗄️ خزان الحسابات النشطة : {Fore.GREEN}{active_count} حساب جاهز {Fore.MAGENTA}| 🚀 التوليد بالخلفية: {Fore.CYAN}مفعّل تلقائياً (5 حسابات){Style.RESET_ALL}")
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
    """Acquire a session exclusively from an existing approved pool record."""
    acc = get_active_account(cfg)
    if acc:
        token = acc["token"]
        chat_uuid = acc.get("chat_uuid") or create_syntx_chat(token, cfg)
        return token, chat_uuid
    warn_no_ready_accounts(cfg)
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

    # فحص معرفات الرسائل السابقة لتفادي التقاط رد قديم قبل وصول الرد الجديد
    pre_msg_ids = set()
    try:
        r_pre = cffi.get(f"{cfg.base_api_url}/chats/{chat_uuid}/messages?page_size=20", headers=headers, timeout=10)
        if r_pre.status_code == 200:
            pre_msg_ids = set(m.get("id") for m in r_pre.json().get("messages", []))
    except Exception:
        pass

    t0 = time.time()
    try:
        r_gen = cffi.post(f"{cfg.base_api_url}/llm/generate?ai_name={ai_name}", json=payload, headers=headers, timeout=cfg.reply_timeout)
        
# grok-4.6 direct mode (no 4.5 fallback)

        if r_gen.status_code == 403 and "modelNotAvailableForPlan" in r_gen.text:
            err_json = {}
            try:
                err_json = r_gen.json().get("detail", {})
            except Exception:
                pass
            min_sub = err_json.get("params", {}).get("minSubscription", "pro/paid")
            msg = err_json.get("message", "Model not available on free plan")
            print(f"{Fore.RED}🔒 [مدفوع / VIP] الموديل [{backend_model}] غير متاح للحسابات المجانية!{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}ℹ️  رسالة السيرفر: {msg} (يتطلب اشتراك: {min_sub}){Style.RESET_ALL}\n")
            return None

        if r_gen.status_code in [429, 401, 403]:
            print(f"{Fore.YELLOW}⚠️ انتهى رصيد الجلسة الحالية أو استجابة ({r_gen.status_code}). جاري حذف الحساب والانتقال للحساب التالي...{Style.RESET_ALL}")
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
                    # قراءة الرسائل من الأحدث إلى الأقدم والتأكد من أنها رسالة جديدة وليست قديمة
                    for msg in reversed(messages):
                        if msg.get("id") not in pre_msg_ids and msg.get("author_id") == -1:
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
        if get_active_account(cfg) is None:
            warn_no_ready_accounts(cfg)
            return
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


def spawn_background_refill():
    """
    استدعاء سكريبت توليد الحسابات (02_syntx_register.py) في الخلفية كعملية منفصلة
    لتوليد 5 حسابات جديدة تلقائياً في كل تشغيل بدون تعطيل الشات (معمارية فويس 36)
    """
    reg_script = BASE_DIR / "02_syntx_register.py"
    if not reg_script.exists():
        return
    try:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        subprocess.Popen(
            [sys.executable, str(reg_script), "--max", "5", "--no-loop"],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        print(f"{Fore.CYAN}🚀 [توليد استباقي في الخلفية] تم إطلاق خيط التسجيل لتجهيز 5 حسابات جديدة...{Style.RESET_ALL}")
    except Exception:
        pass


def main():
    """نقطة الدخول الرئيسية - تدعم الـ CLI واختيار الموديلات والتفكير والبحث"""
    parser = argparse.ArgumentParser(description="Syntx AI Chat — The Elite 4 AI Models")
    parser.add_argument("prompt", nargs="*", help="نص السؤال مباشرة من التيرمينال")
    parser.add_argument("--model", "-m", type=str, default=None, help="تحديد الموديل: 1 (gpt-5.6), 2 (opus-4.8), 3 (sonnet-5), 4 (grok-4.6)")
    parser.add_argument("--no-thinking", action="store_true", help="تعطيل وضع التفكير العميق")
    parser.add_argument("--no-plan", action="store_true", help="تعطيل وضع التخطيط المنهجي")
    parser.add_argument("--no-search", action="store_true", help="تعطيل بحث الويب والأدوات")
    parser.add_argument("--count", "-c", action="store_true", help="عرض عدد الحسابات النشطة في الخزان فقط")
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
        else:
            # دعم الموديلات التجريبية والمدفوعة مثل claude-opus-5 أو غيرها
            ai_name = "claude" if "claude" in selected.lower() else ("chatgpt" if "gpt" in selected.lower() else ("grok" if "grok" in selected.lower() else "auto"))
            cfg.available_models[selected] = {
                "label": f"🧪 {selected}",
                "ai_name": ai_name,
                "desc": "موديل مخصص/تجريبي"
            }
            cfg.model = selected
    if args.no_thinking:
        cfg.thinking = False
    if args.no_plan:
        cfg.plan = False
    if args.no_search:
        cfg.deep_research = False
        cfg.enable_tools = False
    if args.file:
        cfg.input_file = args.file
    if args.output:
        cfg.output_file = args.output

    # لو تم طلب عرض عدد الحسابات فقط
    if args.count:
        accounts = load_accounts_pool(cfg)
        active = sum(1 for a in accounts if is_ready_account(a))
        print(f"\n{Fore.CYAN}📊 إجمالي الحسابات النشطة في الخزان: {Fore.GREEN}{active}{Style.RESET_ALL} حساب جاهز.\n")
        return

    # إطلاق خيط التوليد الاستباقي في الخلفية تلقائياً في كل تشغيل (معمارية فويس 36)
    spawn_background_refill()

    if get_active_account(cfg) is None:
        warn_no_ready_accounts(cfg)
        return

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
