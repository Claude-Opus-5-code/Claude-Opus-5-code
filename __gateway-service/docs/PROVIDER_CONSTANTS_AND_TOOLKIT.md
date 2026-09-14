# 🧰 PROVIDER_CONSTANTS_AND_TOOLKIT.md — عدة الشغل والقواعد الثابتة الموحدة لبناء المزودين
## Universal Provider Constants, Invariants & Scaffold Toolkit (v2.2 Complete Exhaustive Master Edition)

> **المرجع والاعتماد الدستوري:** توجيه البروفيسور زيزو والباشمهندس بولا (الفويسات #127، #128، #129، و #130) ومصادقة الوكيل المعماري.  
> **الهدف:** توحيد "عدة الشغل" البرمجية، وتثبيت أسماء الدوال في **معمل التجارب (Lab)** وفي **سيرفر البوابة (Gateway)**، وتغطية كافة أنماط **الإنشاء (Register)**، **الريفرش (Refresh)**، و**الشات (Chat)** المستخرجة من كافة مزودات المستودع (`.AAA_GGG_iii_VIBE_CODING`) دون استثناء، مع إغلاق سلم فئات الأخطاء الـ 12 بالكامل وأداة التوليد الآلي `scaffold_provider.py` واختبارات العقد الدستوري `test_provider_contract.py`.  
> **المكان:** `__gateway-service/docs/PROVIDER_CONSTANTS_AND_TOOLKIT.md`

---

## 🧭 1. الفلسفة المعمارية: إيه المتغير؟ وإيه الثابت الموحد؟

### 🔴 أولاً: المتغيرات (Variants — خاصة بكل مزود ومنصة منفردة):
1. **روابط الـ Endpoints الخاصة بالمزود:** (مثل `/api/chat/stream` أو `/v1/chat/completions` أو `/chats/{uuid}/messages`).
2. **نوع المصادقة الداخلي (Internal Auth Pattern):** (هل الموقع يعتمد على Cookie Session؟ أم Bearer JWT Token؟ أم تسجيل مؤقت بإيميل ورمز OTP؟ أم Guest Instance UUID؟ أم Org Admin API Key؟).
3. **سعة السياق والحد الأقصى للنصوص (Context Window & Token Limits):**
   > ⚠️ **تنبيه حاسم من فويس 128:** لا يوجد حد أقصى عام ثابت (مثل 6000 حرف)؛ فسعة السياق تختلف كلياً بحسب الموديل والمزود (من 8,000 توكن إلى 128,000 توكن أو 1,000,000 توكن). أي قيود تتعلق بالـ WAF أو حجم البايلود هي معالجة جراحية داخل المزود المعني فقط وليست قاعدة للنظام ككل.
4. **شكل الـ JSON Upstream:** أسماء الحقول الخاصة بالموقع (`messages` أو `prompt` أو `content` أو `text`).

---

### 🟢 ثانياً: الثوابت الموحدة (Invariants — عدة الشغل المشتركة عبر كافة المزودات):
1. **ثلاثية دوال المعمل الموحدة (The Universal Lab Trinity):**
   - `register_account()` ⬅️ دالة إنشاء الحساب / جلب الجلسة المبدئية.
   - `refresh_session()` ⬅️ دالة تجديد الكوكيز أو التوكن المنتهي أو فحص الصلاحية.
   - `execute_chat()` / `stream_chat()` ⬅️ دالة إرسال الشات واستقبال البث المتدفق.
2. **محرك الاتصال وتخطي الحمايات الموحد (TLS Impersonation Engine):**
   - استخدام `curl_cffi` حصراً ببصمة `chrome120` أو `chrome124`.
3. **نظام حقن الهوية وتدوير الـ IP (Dynamic Client Spoofing):**
   - توليد عناوين IP عشوائية وحقنها في ترويسات `X-Forwarded-For` و `X-Real-IP` لتجاوز قيود الحظر الموقعي.
4. **محرك التخزين الذري للخزانات (Atomic JSON Storage Engine):**
   - حفظ ملفات الحسابات عبر ملف وسيط `.tmp` ثم استبداله ذرياً `replace()` لمنع تلف البيانات عند الإغلاق المفاجئ.
5. **مفكك تدفق الـ SSE المقاوم لتلف الأحرف العربية (Byte-Perfect UTF-8 SSE Decoder):**
   - قراءة الـ Stream كـ `Raw Bytes` مفردة دون تفكيك مسبق، ثم فك تشفير السطر الكامل كـ `UTF-8` لحماية النصوص العربية من الـ Mojibake.
6. **فاحص صلاحية الجلسات محلياً بدون شبكة (Layer 0 Offline Token Check):**
   - فك تشفير وتدقيق حقل `exp` في الـ JWT عبر `base64` محلياً بدون إهدار وقت أو استدعاءات شبكة.
7. **كلاس الأخطاء الموحد وسلم الـ 12 فئة المكتمل (Canonical 12 Error Taxonomy):**
   - رفع `UpstreamFailure` وتعيين الفئة الدقيقة للـ Gateway (`AUTH_EXPIRED`, `RATE_LIMITED`, `OVERLOADED`...).
8. **الاستدعاء اللاحظري في سيرفر البوابة (Async Event-Loop Offloading):**
   - تشغيل دوال الـ `_core` التزامنية عبر `asyncio.to_thread` لضمان عدم حظر الـ Event Loop في FastAPI.

---

## 🔒 2. سلم فئات الأخطاء الـ 12 المعتمد كاملاً (Canonical Error Taxonomy — Closed Set)

> لا يُسمح لأي مزود بتعريف فئة خطأ خارج هذا الجدول المعتمد في دستور المنظومة (`gateway.contracts.ErrorCategory`):

| # | كود الفئة (`category`) | متى يُستخدم؟ | الإجراء التلقائي للبوابة | قابل لإعادة المحاولة |
|---|------------------------|--------------|--------------------------|:---:|
| 1 | `auth_expired` | انتهاء الكوكيز أو التوكن (401/403) | تجديد تلقائي للجلسة ثم تبديل الحساب | ✅ |
| 2 | `invalid_credential` | بيانات اعتماد فاسدة أو محذوفة من الأساس | إعدام الحساب من الخزان + تسجيل جديد | ❌ |
| 3 | `rate_limited` | تجاوز عدد الطلبات المسموح (429) | قراءة `Retry-After` + تأخير ارتدادي | ✅ |
| 4 | `quota_exceeded` | نفاد الرصيد أو الكوتة اليومية للحساب | تجميد الحساب حتى `reset_at` + تبديل | ✅ |
| 5 | `model_unavailable` | الموديل غير متاح أو يتطلب خطة مدفوعة | التحويل لموديل بديل متطابق القدرات | ✅ |
| 6 | `provider_unavailable` | خوادم المزود ساقطة أو حظر Cloudflare/WAF | تدوير البصمة والـ IP + محاولة ثانية | ✅ |
| 7 | `unsupported_capability`| طلب ميزة غير مدعومة (مثل Vision على موديل نصي) | رفض صريح فوري لمنع إهدار الشبكة | ❌ |
| 8 | `bad_request` | خطأ في بنية البايلود أو تجاوز سياق البرومبت | إرجاع رسالة واضحة للعميل لتعديل الطلب | ❌ |
| 9 | `content_rejected` | رفض المزود للمحتوى (Safety Filter / السياسات) | إرجاع الرفض للعميل بدون حرق الحساب | ❌ |
| 10 | `timeout` | انتهاء مهلة الاتصال أو القراءة مع المزود | إعادة محاولة واحدة بمهلة أطول | ✅ |
| 11 | `retryable_server_error`| استجابة تالفة من المزود أو 500/502 | إعادة المحاولة مع مهلة ارتدادية (Jitter) | ✅ |
| 12 | `non_retryable_error` | خطأ غير معروف أو عطل حرج غير قابل للتعافي | تسجيل العطل وإبلاغ العميل فوراً | ❌ |

### الكود الملزم للمترجم الموحد (`gateway/errors.py`):
```python
from gateway.contracts import ErrorCategory

def classify_http_status(status: int, body: str = "") -> ErrorCategory:
    """Canonical HTTP status to ErrorCategory mapper.
    Translates upstream HTTP response status and body diagnostics into one of the 12 categories.
    """
    low = (body or "").lower()
    if status in (401, 403):
        if "captcha" in low or "cloudflare" in low or "attention required" in low or "turnstile" in low:
            return ErrorCategory.PROVIDER_UNAVAILABLE
        if "invalid" in low or "wrong" in low or "bad credentials" in low:
            return ErrorCategory.INVALID_CREDENTIAL
        return ErrorCategory.AUTH_EXPIRED
    if status == 429:
        return ErrorCategory.QUOTA_EXCEEDED if ("quota" in low or "credit" in low or "balance" in low) else ErrorCategory.RATE_LIMITED
    if status == 404:
        return ErrorCategory.MODEL_UNAVAILABLE
    if status in (413, 422) and ("context" in low or "token" in low or "too long" in low or "length" in low):
        return ErrorCategory.BAD_REQUEST
    if status == 451 or "content_policy" in low or "safety" in low or "filtered" in low or "harmful" in low:
        return ErrorCategory.CONTENT_REJECTED
    if status == 503:
        return ErrorCategory.PROVIDER_UNAVAILABLE
    if status in (408, 504):
        return ErrorCategory.TIMEOUT
    if status in (500, 502):
        return ErrorCategory.RETRYABLE_SERVER_ERROR
    return ErrorCategory.NON_RETRYABLE_ERROR
```

---

## 🔬 3. موسوعة الأنماط المعمارية المستخرجة عبر كافة المزودين

> **بناءً على التوجيه الميداني الصارم من فويس 130، تم تفكيك كافة مزودي المستودع وحصر الأنماط الحقيقية المستخدمة في الإنشاء والريفرش والشات:**

### 🛠️ القسم (أ): أنماط الإنشاء والتسجيل (Registration & Provisioning Patterns)

#### 1. نمط البريد المؤقت + سحب الـ OTP بالتوازي (Disposable Email + Threaded OTP):
- **المزودات الشاهدة:** `🟢_syntx_ai` (TempMailClub) و `🟢_Uuncensored` (Emailnator).
- **الآلية:** توليد إيميل Gmail حقيقي (dot/plus alias) أو دومين سريع (`rc.mailings.live`)، إرسال فورم التسجيل، وفي نفس اللحظة تشغيل ثريد متوازي لانتظار كود التحقق في الـ Inbox واستخراجه عبر `re.search(r'\b(\d{6})\b', ...)`.
```python
def poll_email_otp(session, email: str, timeout: int = 45) -> str:
    """استخراج كود الـ OTP المكون من 6 أرقام من صندوق الوارد آلياً."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            res = session.post("https://www.emailnator.com/message-list", json={"email": email})
            for msg in res.json().get("messageData", []):
                match = re.search(r'\b(\d{6})\b', msg.get("subject", ""))
                if match:
                    return match.group(1)
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError("OTP reception timed out")
```

#### 2. نمط هوية الجيست العشوائية المتجددة (Dynamic Ephemeral Guest / Device UUID):
- **المزودات الشاهدة:** `🟢_overchat_ai` و `🟢_chatbox_multi_models_bypass.py` و `test_notegpt_agent_mode.py`.
- **الآلية:** عدم الحاجة لتسجيل أي حساب! توليد معرف جهاز عشوائي (`x-device-uuid`) وبصمة هاتف أندرويد مع `okhttp/4.12.0` أو جلب جلسة مجهولة فورية عبر `/v1/auth/me`.
```python
def generate_guest_device_context() -> dict:
    """توليد سياق جهاز أندرويد سامسونج وهوية زائر فورية بدون تسجيل."""
    device_uuid = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
    return {
        "User-Agent": "okhttp/4.12.0",
        "x-device-platform": "android",
        "x-device-brand": "samsung",
        "x-device-uuid": device_uuid,
        "X-Forwarded-For": f"{random.randint(11,190)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
    }
```

#### 3. نمط حصاد كوكيز الجلسات المحمية (Cookie Harvesting & Session Storage):
- **المزودات الشاهدة:** `FreebuFF` و `Ernie Baidu`.
- **الآلية:** استخراج كوكيز الجلسات المعتمدة (`__Secure-next-auth.session-token`) وتخزينها في ملف نصي معزول أو بيئة تشغيل، والتحقق المسبق من الجلسة عبر أندبوينت السيرفر.

---

### 🔄 القسم (ب): أنماط التجديد وفحص الصلاحية (Refresh & Health Audit Patterns)

#### 1. النمط الهرمي ثلاثي الطبقات (The 3-Layer Hierarchical Refresh):
- **المزود الشاهد:** `🟢_Uuncensored/refresh.py`.
- **الآلية:**
  - **Layer 0 (فوري ~0s):** فحص تاريخ انتهاء الـ JWT محلياً بدون شبكة (`_decode_jwt_exp`).
  - **Layer 1 (سريع ~1s):** تسجيل دخول مباشر عبر الـ API بالـ email + password وتجديد التوكن.
  - **Layer 2 (احتياطي ~30s):** تشغيل متصفح خفي فقط في حال فرض Cloudflare Turnstile.

#### 2. نمط فحص الرصيد ونوافذ الاستهلاك (Balance & Window Quota Auditing):
- **المزود الشاهد:** `🔵_syntx_ai/03_syntx_refresh.py`.
- **الآلية:** فحص استهلاك الحساب عبر أندبوينت `/user/balance` ونوافذ الاستهلاك (`window_6h`, `window_7d`). لو رصيد 6 ساعات = 0% ⬅️ يتم تمييز الحساب كـ `dead` واستبعاده تلقائياً؛ لو 7 أيام منتهية ⬅️ يُصنف كـ `limited` ولا يُحذف.

#### 3. نمط التبديل الفوري عند الخطأ (Zero-Downtime Instant Failover):
- **المزودات الشاهدة:** `🟢_chatbox_multi_models_bypass.py` و `🟢_syntx_ai`.
- **الآلية:** عند استقبال كود 401 أو 403 أو 429، يتم إعدام التوكن الحالي من مصفوفة الذاكرة والانتقال للتوكن التالي في الخزان في **0.01 ثانية** وإعادة تنفيذ نفس الريكويست دون أن يشعر المستخدم بأي انقطاع!

---

### 💬 القسم (ج): أنماط الشات والبث والوسائط (Chat, Stream & Vision Patterns)

#### 1. سياق المحادثة متعدد الأدوار (Multi-Turn History Sync):
- **المزودات الشاهدة:** `FreebuFF`, `Overchat`, `NoteGPT`.
- **الآلية:** الحفاظ على معرف المحادثة (`chat_uuid` أو `threadId`)، وإرسال مصفوفة الرسائل السابقة بالترتيب القياسي: `[{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]`.

#### 2. رفع المرفقات والصور السحابي (Multi-Modal Cloud Ingestion):
- **المزودات الشاهدة:** `Syntx` (Cloudflare R2) و `Overchat` (AWS S3) و `Cohere` (Base64 Inline).
```python
def upload_file_to_storage(session, file_path: Path, upload_url: str, token: str) -> str:
    """رفع صورة أو كود لسحابة المزود واستخراج رابط الرؤية البصرية المعتمد."""
    ext = file_path.suffix.lower()
    mime = "image/png" if ext == ".png" else "application/octet-stream"
    with open(file_path, "rb") as f:
        r = session.post(upload_url, headers={"Authorization": f"Bearer {token}"}, files={"file": (file_path.name, f, mime)})
    return r.json().get("url")
```

#### 3. مفكك بث الـ SSE الموحد الحامي للأحرف العربية (Byte-Perfect UTF-8 Stream Unpacker):
- **المزودات الشاهدة:** كل السكربتات المعتمدة.
- **الآلية:** قراءة الـ Stream كـ Raw Bytes ثم فك تشفير السطر كـ UTF-8، واستخراج الـ Delta من مختلف هياكل الـ JSON (OpenAI format, event-driven delta, text format).

---

## 🏗️ 4. مولّد الهيكل التلقائي (Scaffold Generator CLI)

أداة رسمية موجودة في `__gateway-service/tools/scaffold_provider.py`، تُنشئ هيكل أي مزود جديد بضغطة زر واحدة ومطابقة للدستور بنسبة 100%:

### أمر التشغيل:
```bash
python tools/scaffold_provider.py blackbox --display "BlackBox AI" --lab
```

### المخرجات التلقائية:
```
__gateway-service/providers/blackbox/
├── __init__.py           ← تصدير DEFINITION
├── _core.py              ← ثلاثية الدوال الموحدة (register, refresh, execute_chat)
├── adapter.py            ← واجهة generate_text ومترجم الأخطاء الـ 12
├── definition.py         ← بطاقة إمكانيات وموديلات المزود الرسمية
└── models_metadata.json  ← بيانات السياق والنماذج المعتمدة
.AAA_GGG_iii_VIBE_CODING/blackbox/blackbox_lab.py  ← سكريبت المعمل المستقل
```

---

## 🧪 5. حارس العقد الدستوري التلقائي (Contract Compliance Test)

ملف الاختبار الرسمي في `__gateway-service/tests/test_provider_contract.py`، يفحص كافة المزودات في بيئة الـ CI ويمنع دمج أي مزود يخالف المعايير:
- ✅ وجود الملفات الأربعة الأساسية + `__init__.py`.
- ✅ صحة واكتمال `models_metadata.json`.
- ✅ مطابقة مواصفات `DEFINITION` مع بروتوكول البوابة.
- ✅ تنفيذ ثلاثية الدوال في `_core.py` وتنفيذ `generate_text` في `adapter.py`.

### أمر التحقق:
```bash
py -3.13 -m pytest tests/test_provider_contract.py -v
```

---
```
[EXHAUSTIVE MASTER COMPLIANCE — SIGNED BY ZIZO & BOLLA — ZERO AMBIGUITY]
```
