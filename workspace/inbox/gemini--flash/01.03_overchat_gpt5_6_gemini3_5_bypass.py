# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════════
🟢 Overchat Dual-Models Master Bypass Hub v01.03 (Free & Active 100%)
══════════════════════════════════════════════════════════════════════
- كلاس كونفج موحد وشامل لجميع الإعدادات والموديلات في أول السكربت.
- الموديلين المجانيين الشغالين 100% بدون أي اشتراك مدفوع (الثنائي الخارق):
    1. 🧠 gpt-5-6-luna      -> الوحش ChatGPT 5.6 Luna (Deep Reasoning & Smart Logic)
    2. ⚡ gemini-3-5-flash  -> جوجل فلاش السريع (Ultra Fast & Responsive)
- محرك SSE Streaming مزدوج متوافق مع كافة أنماط الأحداث (Event-driven deltas).
- دعم البحث المباشر في الويب عبر ميزة Web Search.
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
    persona_id: str = "gpt-5-6-luna"
    model: str = "gpt-5.6-luna"
    
    # 📋 قائمة الموديلات المجانية الشغالة 100% في البوابة (الثنائي الخارق)
    available_models: dict = field(default_factory=lambda: {
        "gpt-5-6-luna": {
            "model": "gpt-5.6-luna",
            "desc": "🧠 الوحش ChatGPT 5.6 Luna (Deep Reasoning & Smart Logic)"
        },
        "gemini-3-5-flash": {
            "model": "google/gemini-3.5-flash",
            "desc": "⚡ جوجل فلاش 3.5 (Ultra Fast Speed & Instant Response)"
        }
    })
    
    # 🌐 خيار البحث بالإنترنت المباشر
    web_search: bool = False
    
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
    print(f"║  🟢 Overchat Dual-Models Master Bypass Hub v01.03 (Free & Active 100%)  ║")
    print(f"║  🚀 تشغيل فوري بدون ليمت سطور/حروف + حفظ تلقائي في {cfg.output_file:<18}║")
    print(f"╚{'═'*74}╝{Style.RESET_ALL}")
    
    print(f"{Fore.CYAN}🕵️  بيانات التخفي والمحاكاة:")
    print(f"   📱 بصمة الموبايل الوهمي : {Fore.YELLOW}{device_id}{Style.RESET_ALL}")
    print(f"   🌍 عنوان IP التمويه     : {Fore.YELLOW}{spoofed_ip}{Style.RESET_ALL}")
    
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📋 الموديلات المجانية الشغالة 100% في السكربت (الثنائي الخارق):{Style.RESET_ALL}")
    for pid, meta in cfg.available_models.items():
        is_active = (pid == cfg.persona_id)
        mark = f"{Fore.GREEN}◄ [الموديل النشط الحالي]{Style.RESET_ALL}" if is_active else ""
        color = Fore.YELLOW if is_active else Fore.WHITE
        print(f"   • {color}{pid:<22}{Style.RESET_ALL} -> {meta['desc']} {mark}")
        
    print(f"{Fore.GREEN}{'─'*76}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}🎯 الموديل النشط الحالي : {Fore.YELLOW}{cfg.persona_id} ({cfg.model}){Style.RESET_ALL}")
    search_status = f"{Fore.GREEN}مفعل ✅{Style.RESET_ALL}" if cfg.web_search else f"{Fore.WHITE}معطل ❌{Style.RESET_ALL}"
    print(f"{Fore.MAGENTA}🔍 البحث بالإنترنت       : {search_status}")
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

def extract_stream_delta(chunk_dict: dict) -> str:
    """استخراج الدلتا بدقة سواء من نمط الأحداث الجديد أو نمط OpenAI الكلاسيكي"""
    if "data" in chunk_dict and isinstance(chunk_dict["data"], dict):
        return chunk_dict["data"].get("delta", "") or chunk_dict["data"].get("text", "") or ""
    if "choices" in chunk_dict and chunk_dict["choices"]:
        return chunk_dict["choices"][0].get("delta", {}).get("content", "") or ""
    if "delta" in chunk_dict:
        return str(chunk_dict["delta"])
    return ""

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
    print(f"│ 🔍 البحث بالإنترنت: {Fore.YELLOW}{'نعم' if cfg.web_search else 'لا'}{Fore.MAGENTA}")
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
        "top_p": 0.95,
        "webSearch": cfg.web_search
    }

    start_time = time.time()
    full_response = []
    
    try:
        res = requests.post(
            url_msg,
            data=json.dumps(payload_msg),
            headers=headers_json,
            stream=True,
            timeout=cfg.timeout_seconds
        )
        
        if res.status_code not in [200, 201]:
            print(f"{Fore.RED}❌ خطأ من الخادم ({res.status_code}): {res.text[:300]}{Style.RESET_ALL}")
            return None

        for line in res.iter_lines():
            if line:
                decoded_line = line.decode('utf-8', errors='ignore')
                if decoded_line.startswith('data: '):
                    raw_data = decoded_line[6:].strip()
                    if raw_data == '[DONE]':
                        break
                    try:
                        data_json = json.loads(raw_data)
                        delta = extract_stream_delta(data_json)
                        if delta:
                            print(delta, end="", flush=True)
                            full_response.append(delta)
                    except json.JSONDecodeError:
                        pass
        print()
    except Exception as e:
        print(f"\n{Fore.RED}⚠️ حدث خطأ أثناء استقبال البث: {e}{Style.RESET_ALL}")
        return None

    elapsed_time = time.time() - start_time
    complete_text = "".join(full_response).strip()

    # 6. إحصائيات الرد وحفظه
    if complete_text:
        resp_chars = len(complete_text)
        resp_lines = len(complete_text.splitlines())
        resp_words = len(complete_text.split())
        chars_per_sec = resp_chars / elapsed_time if elapsed_time > 0 else 0

        print(f"{Fore.CYAN}{'─'*74}{Style.RESET_ALL}")
        print(f"\n{Fore.GREEN}┌─── 🏆 إحصائيات الرد وسرعة التوليد ────────────────────────┐")
        print(f"│ ⏱️  الوقت المستغرق: {elapsed_time:.2f} ثانية")
        print(f"│ 📝 حروف الرد     : {resp_chars:,} حرف")
        print(f"│ 📄 أسطر الرد     : {resp_lines:,} سطر")
        print(f"│ 🔤 كلمات الرد    : {resp_words:,} كلمة")
        print(f"│ ⚡ معدل التوليد  : {chars_per_sec:.1f} حرف/ثانية")
        print(f"│ 🏷️  الموديل الفعلي: {cfg.persona_id}")
        print(f"└────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

        # حفظ الملف
        output_path = BASE_DIR / cfg.output_file
        try:
            output_path.write_text(complete_text, encoding="utf-8")
            print(f"{Fore.GREEN}💾 تم حفظ الرد كاملاً في: {Fore.YELLOW}{cfg.output_file}{Style.RESET_ALL}\n")
        except Exception as e:
            print(f"{Fore.RED}⚠️ فشل حفظ الرد في {cfg.output_file}: {e}{Style.RESET_ALL}")

        return complete_text
    else:
        print(f"\n{Fore.YELLOW}⚠️ لم يتم استلام أي رد من الخادم.{Style.RESET_ALL}")
        return None

def parse_cli_arguments() -> tuple[Config, str | None, bool]:
    """معالجة وسائط سطر الأوامر بمرونة عالية"""
    cfg = Config()
    parser = argparse.ArgumentParser(
        description="🟢 Overchat Dual-Models Master Bypass Hub v01.03",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("prompt", nargs="*", help="نص السؤال مباشرة من الطرفية")
    parser.add_argument("--model", "-m", choices=list(cfg.available_models.keys()), default=cfg.persona_id, help="اختيار الموديل")
    parser.add_argument("--web-search", "-w", action="store_true", help="تفعيل البحث بالإنترنت المباشر")
    parser.add_argument("--file", "-f", default=cfg.input_file, help="ملف الإدخال")
    parser.add_argument("--output", "-o", default=cfg.output_file, help="ملف حفظ الإخراج")
    parser.add_argument("--max-lines", type=int, default=None, help="تحديد أقصى عدد أسطر")
    parser.add_argument("--max-chars", type=int, default=None, help="تحديد أقصى عدد حروف")
    parser.add_argument("--list-models", "-l", action="store_true", help="عرض الموديلات المتاحة")
    parser.add_argument("--cli", action="store_true", help="بدء محادثة تفاعلية مستمرة")

    args = parser.parse_args()

    cfg.persona_id = args.model
    cfg.model = cfg.available_models[args.model]["model"]
    cfg.web_search = args.web_search
    cfg.input_file = args.file
    cfg.output_file = args.output
    cfg.max_lines = args.max_lines
    cfg.max_chars = args.max_chars

    prompt_text = " ".join(args.prompt).strip() if args.prompt else None
    return cfg, prompt_text, args.list_models, args.cli

def interactive_loop(cfg: Config):
    """جلسة محادثة تفاعلية مستمرة في التيرمينال"""
    print(f"{Fore.GREEN}💬 بدأت جلسة المحادثة التفاعلية المستمرة ({cfg.persona_id}). اكتب 'exit' أو 'q' للخروج.{Style.RESET_ALL}\n")
    while True:
        try:
            user_input = input(f"{Fore.YELLOW}أنت > {Style.RESET_ALL}").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', 'q', 'خروج']:
                print(f"{Fore.CYAN}👋 تم إنهاء الجلسة التفاعلية.{Style.RESET_ALL}")
                break
            send_chat_request(user_input, cfg, source_label="شات تفاعلي")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.CYAN}👋 تم إنهاء الجلسة.{Style.RESET_ALL}")
            break

def main():
    cfg, cli_prompt, list_models, is_cli_mode = parse_cli_arguments()
    _, device_id, spoofed_ip = build_mobile_headers()
    print_banner(cfg, device_id, spoofed_ip)

    if list_models:
        return

    if is_cli_mode:
        interactive_loop(cfg)
        return

    # 1. الأولوية للبرومبت المباشر من سطر الأوامر
    if cli_prompt:
        send_chat_request(cli_prompt, cfg, source_label="CLI Argument")
        return

    # 2. القراءة التلقائية من ملف الإدخال
    file_content, label = read_input_content(cfg)
    if file_content:
        send_chat_request(file_content, cfg, source_label=label)
        return

    # 3. في حالة عدم وجود مدخلات، إرسال سؤال اختباري ترحيبي
    default_prompt = "مرحباً! ما هي قدراتك وأفضل المهام التي يمكنك مساعدتي بها؟ أجب باختصار بالعامية المصرية."
    print(f"{Fore.YELLOW}ℹ️ لم يتم العثور على نص في {cfg.input_file}، سيتم إرسال برومبت اختباري افتراضي...{Style.RESET_ALL}\n")
    send_chat_request(default_prompt, cfg, source_label="افتراضي تلقائي")

if __name__ == "__main__":
    main()
