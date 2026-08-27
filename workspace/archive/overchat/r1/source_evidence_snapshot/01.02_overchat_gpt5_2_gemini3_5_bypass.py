# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════════
🟢 Overchat Dual-Models Master Bypass Hub (Free & Active 100%)
══════════════════════════════════════════════════════════════════════
- كلاس كونفج موحد وشامل لجميع الإعدادات والموديلات في أول السكربت.
- الموديلات المجانية الشغالة 100% بدون أي اشتراك مدفوع:
    1. 🧠 gpt-5-2           -> الوحش ChatGPT 5.2 (Deep Reasoning & Logic)
    2. ⚡ gemini-3-5-flash  -> جوجل فلاش السريع (Ultra Fast & Responsive)
    3. 🚀 free-chat-gpt     -> شات جي بي تي نانو (Free Landing Model)
- محاكاة تطبيق Overchat Android بهيدرات OkHttp وجهاز أندرويد وهمي وتوليد هوية و IP جديد لكل جلسة.
- إرسال أي عدد من السطور والحروف بدون أي ليمت نهائياً (Unlimited).
- تشغيل فوري بنقرة واحدة بزر Run من الـ IDE أو من التيرمينال.
- قراءة تلقائية من chat_send.txt وحفظ الرد بالكامل في chat_reply.txt.
- إحصائيات دقيقة وفورية لحجم المدخلات، المخرجات، والسرعة (حرف/ثانية).
══════════════════════════════════════════════════════════════════════
"""
from dataclasses import dataclass, field
import requests
import json
import os
import sys
import time
import uuid
import random
import string
import pathlib
import argparse

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


# ======================================================================
# ⚙️ كلاس الإعدادات الموحد (Config) - مرونة كاملة لكل الخيارات
# ======================================================================
@dataclass
class Config:
    # 🤖 الموديل الافتراضي المستخدم (شغال مجاني وسريع جداً 100%)
    persona_id: str = "gemini-3-5-flash"
    model: str = "google/gemini-3.5-flash"
    
    # 📋 قائمة الموديلات المجانية الشغالة 100% في البوابة
    available_models: dict = field(default_factory=lambda: {
        "gpt-5-2": {
            "model": "gpt-5.2-2025-12-11",
            "desc": "🧠 الوحش ChatGPT 5.2 (Deep Reasoning & Smart Logic)"
        },
        "gemini-3-5-flash": {
            "model": "google/gemini-3.5-flash",
            "desc": "⚡ جوجل فلاش 3.5 (Ultra Fast Speed & Instant Response)"
        },
        "free-chat-gpt-landing": {
            "model": "openai/gpt-4.1-nano",
            "desc": "🚀 شات جي بي تي نانو (Lightweight & Free Landing Model)"
        }
    })
    
    # 📂 مسارات ملفات الإدخال والإخراج
    input_file: str = "chat_send.txt"
    output_file: str = "chat_reply.txt"
    
    # 📏 ليمت الأسطر والحروف (None = بدون ليمت نهائياً - يقرأ كل شيء)
    max_lines: int | None = None
    max_chars: int | None = None
    
    # 🌐 رابط البوابة الأساسي
    base_url: str = "https://api.overchat.ai"
    
    # ⏱️ مهلة الانتظار بالثواني
    timeout_seconds: int = 120
    
    # 🎭 البرومبت العام للنظام
    system_prompt: str = (
        "You are an expert AI assistant. "
        "Provide accurate, structured, and well-reasoned responses. "
        "Reply in Egyptian Arabic when requested or appropriate."
    )


# ======================================================================
# 🛠️ أدوات توليد الهوية والـ Spoofing
# ======================================================================
BASE_DIR = pathlib.Path(__file__).resolve().parent

def generate_fake_ip() -> str:
    """توليد عنوان IP وهمي للتمويه في الهيدرات"""
    return f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"

def build_mobile_headers() -> tuple[dict, str, str]:
    """توليد هيدرات موبايل أندرويد وبصمة جهاز وهمية بالكامل"""
    fake_ip = generate_fake_ip()
    random_device_uuid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
    
    headers = {
        'User-Agent': "okhttp/4.12.0",
        'Accept': "application/json, text/plain, */*",
        'Accept-Encoding': "gzip",
        'X-Forwarded-For': fake_ip,
        'X-Real-IP': fake_ip,
        'Client-IP': fake_ip,
        'x-device-platform': "android",
        'x-device-version': "12",
        'x-device-brand': "samsung",
        'x-device-id': "exynos9611",
        'x-device-uuid': random_device_uuid, 
        'x-app-build-number': "80",
        'x-app-version': "1.0",
        'x-app-default-lang': "ar"
    }
    return headers, random_device_uuid, fake_ip

def print_banner(cfg: Config, device_id: str, spoofed_ip: str):
    """طباعة بانر نيون فخم يوضح الموديل والهوية والملفات النشطة"""
    print(f"\n{Fore.GREEN}╔{'═'*74}╗")
    print(f"║  🟢 Overchat Dual-Models Master Bypass Hub (Free & Active 100%)        ║")
    print(f"║  🚀 تشغيل فوري بدون ليمت سطور/حروف + حفظ تلقائي في {cfg.output_file:<18}║")
    print(f"╚{'═'*74}╝{Style.RESET_ALL}")
    
    print(f"{Fore.CYAN}🕵️  بيانات التخفي والمحاكاة:")
    print(f"   📱 بصمة الموبايل الوهمي : {Fore.YELLOW}{device_id}{Style.RESET_ALL}")
    print(f"   🌍 عنوان IP التمويه     : {Fore.YELLOW}{spoofed_ip}{Style.RESET_ALL}")
    
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📋 الموديلات المجانية الشغالة 100% في السكربت:{Style.RESET_ALL}")
    for pid, meta in cfg.available_models.items():
        is_active = (pid == cfg.persona_id)
        mark = f"{Fore.GREEN}◄ [الموديل النشط الحالي]{Style.RESET_ALL}" if is_active else ""
        color = Fore.YELLOW if is_active else Fore.WHITE
        print(f"   • {color}{pid:<22}{Style.RESET_ALL} -> {meta['desc']} {mark}")
        
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}🎯 الموديل النشط الحالي : {Fore.YELLOW}{cfg.persona_id} ({cfg.model}){Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}📂 ملف الإدخال          : {Fore.WHITE}{cfg.input_file}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}💾 ملف الإخراج          : {Fore.WHITE}{cfg.output_file}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}\n")

def read_input_content(cfg: Config) -> tuple[str, str]:
    """قراءة نص الإدخال مع تطبيق الفلترة (بدون ليمت افتراضياً)"""
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

def send_chat_request(prompt_text: str, cfg: Config, source_label: str = "مباشر") -> str | None:
    """تنفيذ دورة المحادثة الكاملة (Auth -> Title -> Init -> SSE Stream) مع قياس الإحصائيات"""
    char_count = len(prompt_text)
    line_count = len(prompt_text.splitlines())
    word_count = len(prompt_text.split())
    approx_tokens = int(char_count / 3.5)

    print(f"{Fore.MAGENTA}┌─── 📊 إحصائيات السؤال ({source_label}) ────────────────────────┐")
    print(f"│ 🤖 الموديل     : {Fore.YELLOW}{cfg.persona_id} ({cfg.model}){Fore.MAGENTA}")
    print(f"│ 📝 عدد الحروف : {Fore.YELLOW}{char_count:,}{Fore.MAGENTA} حرف (بدون ليمت)")
    print(f"│ 📄 عدد الأسطر  : {Fore.YELLOW}{line_count:,}{Fore.MAGENTA} سطر")
    print(f"│ 🔤 عدد الكلمات : {Fore.YELLOW}{word_count:,}{Fore.MAGENTA} كلمة")
    print(f"│ 🪙 Tokens تقريبي: {Fore.YELLOW}~{approx_tokens:,}{Fore.MAGENTA}")
    print(f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

    base_headers, device_id, spoofed_ip = build_mobile_headers()
    
    # 2. جلب User ID
    try:
        url_auth = f"{cfg.base_url}/v1/auth/me"
        res_auth = requests.get(url_auth, headers=base_headers, timeout=15)
        if res_auth.status_code not in [200, 201]:
            print(f"{Fore.RED}❌ فشل جلب معرف المستخدم ({res_auth.status_code}): {res_auth.text[:150]}{Style.RESET_ALL}")
            return None
        user_id = res_auth.json().get("id")
    except Exception as e:
        print(f"{Fore.RED}⚠️ خطأ في الاتصال بالبوابة (Auth): {e}{Style.RESET_ALL}")
        return None

    chat_uuid = str(uuid.uuid4())
    msg_id_1 = str(uuid.uuid4())
    msg_id_2 = str(uuid.uuid4())

    headers_json = base_headers.copy()
    headers_json['Content-Type'] = "application/json"

    # 3. إنشاء عنوان المحادثة
    try:
        url_title = f"{cfg.base_url}/v1/chat/{user_id}/{chat_uuid}/generateChatTitle"
        payload_title = {
            "userPrompt": prompt_text[:300],
            "systemPrompt": cfg.system_prompt,
            "personaType": "text",
            "personaModel": cfg.model
        }
        requests.patch(url_title, data=json.dumps(payload_title), headers=headers_json, timeout=15)
    except Exception:
        pass

    # 4. تهيئة جلسة المحادثة
    try:
        url_create = f"{cfg.base_url}/v1/chat/{user_id}"
        payload_create = {
            "personaId": cfg.persona_id,
            "firstBotMessageHidden": True,
            "chatUuid": chat_uuid
        }
        requests.post(url_create, data=json.dumps(payload_create), headers=headers_json, timeout=15)
    except Exception:
        pass

    # 5. إرسال الرسالة واستقبال الرد عبر تدفق SSE
    print(f"{Fore.YELLOW}⏳ جاري إرسال السؤال لـ [{cfg.persona_id}] واستقبال الرد...{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}🤖 الرد المباشر ({cfg.persona_id}):{Style.RESET_ALL}\n" + f"{Fore.CYAN}{'─'*74}{Style.RESET_ALL}")

    url_msg = f"{cfg.base_url}/v2/chat/responses"
    payload_msg = {
        "messages": [
            {"role": "user", "content": prompt_text, "id": msg_id_1},
            {"id": msg_id_2, "role": "system", "content": ""}
        ],
        "model": cfg.model,
        "personaId": cfg.persona_id,
        "chatId": chat_uuid,
        "frequency_penalty": 0,
        "max_tokens": 4000,
        "presence_penalty": 0,
        "stream": True,
        "temperature": 0.5,
        "top_p": 0.95
    }

    headers_stream = base_headers.copy()
    headers_stream['Accept'] = "text/event-stream"
    headers_stream['Content-Type'] = "application/json"
    headers_stream['cache-control'] = "no-cache"
    headers_stream['x-requested-with'] = "XMLHttpRequest"
    headers_stream['authorization'] = "undefined"

    t0 = time.time()
    bot_full_reply = ""

    try:
        res_msg = requests.post(url_msg, data=json.dumps(payload_msg), headers=headers_stream, stream=True, timeout=cfg.timeout_seconds)

        if res_msg.status_code in [200, 201]:
            for line in res_msg.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8', errors='replace')
                    if decoded_line.startswith("data:"):
                        json_str = decoded_line.replace("data: ", "", 1).strip()
                        if json_str == "[DONE]":
                            break
                        try:
                            data = json.loads(json_str)
                            if data.get("event") == "response.output_text.delta":
                                delta = data["data"].get("delta", "")
                                if delta:
                                    sys.stdout.write(f"{Fore.WHITE}{delta}{Style.RESET_ALL}")
                                    sys.stdout.flush()
                                    bot_full_reply += delta
                            elif data.get("event") == "error":
                                print(f"\n{Fore.RED}⚠️ خطأ من السيرفر أثناء التدفق: {data['data'].get('message')}{Style.RESET_ALL}")
                        except Exception:
                            pass

            elapsed = time.time() - t0
            out_chars = len(bot_full_reply)
            out_lines = len(bot_full_reply.splitlines())
            out_words = len(bot_full_reply.split())
            speed = out_chars / elapsed if elapsed > 0 else 0

            print(f"\n{Fore.CYAN}{'─'*74}{Style.RESET_ALL}")
            print(f"\n{Fore.GREEN}┌─── 🏆 إحصائيات الرد وسرعة التوليد ────────────────────────┐")
            print(f"│ ⏱️  الوقت المستغرق: {Fore.YELLOW}{elapsed:.2f} ثانية")
            print(f"│ 📝 حروف الرد     : {Fore.YELLOW}{out_chars:,}{Fore.GREEN} حرف")
            print(f"│ 📄 أسطر الرد     : {Fore.YELLOW}{out_lines:,}{Fore.GREEN} سطر")
            print(f"│ 🔤 كلمات الرد    : {Fore.YELLOW}{out_words:,}{Fore.GREEN} كلمة")
            print(f"│ ⚡ معدل التوليد  : {Fore.YELLOW}{speed:.1f}{Fore.GREEN} حرف/ثانية")
            print(f"│ 🏷️  الموديل الفعلي: {Fore.YELLOW}{cfg.persona_id}")
            print(f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

            # حفظ الرد كاملاً في الملف المحدد
            out_path = BASE_DIR / cfg.output_file
            try:
                out_path.write_text(bot_full_reply, encoding="utf-8")
                print(f"{Fore.GREEN}💾 تم حفظ الرد كاملاً في: {Fore.CYAN}{cfg.output_file}{Style.RESET_ALL}\n")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ تعذر حفظ الرد في ملف: {e}{Style.RESET_ALL}\n")

            return bot_full_reply

        else:
            print(f"\n{Fore.RED}❌ فشل الطلب ({res_msg.status_code}): {res_msg.text[:250]}{Style.RESET_ALL}\n")
            return None

    except Exception as e:
        print(f"\n{Fore.RED}⚠️ فشل الاتصال بالبوابة: {e}{Style.RESET_ALL}\n")
        return None

def interactive_chat_mode(cfg: Config):
    """وضع الشات التفاعلي المباشر سطر بسطر"""
    print(f"{Fore.YELLOW}💬 الوضع التفاعلي جاهز (الموديل: {cfg.persona_id}) - اكتب 'exit' للخروج:{Style.RESET_ALL}\n")
    while True:
        try:
            user_text = input(f"{Fore.WHITE}👤 أنت: {Style.RESET_ALL}").strip()
            if not user_text:
                continue
            if user_text.lower() in ['exit', 'quit', 'خروج', 'q']:
                print(f"{Fore.RED}👋 سلام يا ريس!{Style.RESET_ALL}")
                break
            send_chat_request(user_text, cfg, "شات تفاعلي")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.RED}⛔ تم إيقاف الجلسة.{Style.RESET_ALL}")
            break

def main():
    """نقطة الدخول الرئيسية - تدعم زر Run المباشر والـ CLI"""
    parser = argparse.ArgumentParser(description="Overchat Dual-Models Master ByPass Hub")
    parser.add_argument("prompt", nargs="*", help="نص السؤال مباشرة من التيرمينال")
    parser.add_argument("--model", "-m", type=str, default=None, help="اختيار الموديل (مثل gpt-5-2 أو gemini-3-5-flash)")
    parser.add_argument("--file", "-f", type=str, default=None, help="تحديد ملف الإدخال (الافتراضي chat_send.txt)")
    parser.add_argument("--output", "-o", type=str, default=None, help="تحديد ملف الإخراج (الافتراضي chat_reply.txt)")
    parser.add_argument("--max-lines", "-l", type=int, default=None, help="تحديد حد أقصى للأسطر")
    parser.add_argument("--max-chars", "-c", type=int, default=None, help="تحديد حد أقصى للحروف")
    parser.add_argument("--list-models", action="store_true", help="عرض جميع الموديلات المتاحة في السكربت")
    parser.add_argument("--cli", action="store_true", help="بدء الشات التفاعلي فوراً")
    args = parser.parse_args()

    cfg = Config()

    if args.list_models:
        print(f"\n{Fore.CYAN}📋 قائمة الموديلات المجانية المتاحة في السكربت:{Style.RESET_ALL}")
        for pid, meta in cfg.available_models.items():
            print(f"  • {Fore.YELLOW}{pid:<22}{Style.RESET_ALL} ({meta['model']}) -> {meta['desc']}")
        print()
        return

    if args.model:
        if args.model in cfg.available_models:
            cfg.persona_id = args.model
            cfg.model = cfg.available_models[args.model]["model"]
        else:
            cfg.persona_id = args.model
            cfg.model = args.model

    if args.file:
        cfg.input_file = args.file
    if args.output:
        cfg.output_file = args.output
    if args.max_lines:
        cfg.max_lines = args.max_lines
    if args.max_chars:
        cfg.max_chars = args.max_chars

    _, dev_id, sp_ip = build_mobile_headers()
    print_banner(cfg, dev_id, sp_ip)

    if args.prompt:
        direct_prompt = " ".join(args.prompt).strip()
        send_chat_request(direct_prompt, cfg, "CLI Argument")
        return

    if args.cli:
        interactive_chat_mode(cfg)
        return

    # الوضع التلقائي بزر Run
    content, label = read_input_content(cfg)
    if content:
        print(f"{Fore.GREEN}📂 تم العثور على نص جاهز في: {Fore.YELLOW}{cfg.input_file}{Style.RESET_ALL}")
        send_chat_request(content, cfg, label)
    else:
        print(f"{Fore.YELLOW}ℹ️ ملف {cfg.input_file} فارغ أو غير موجود. تم التحويل للوضع التفاعلي.{Style.RESET_ALL}\n")
        interactive_chat_mode(cfg)

if __name__ == "__main__":
    main()
