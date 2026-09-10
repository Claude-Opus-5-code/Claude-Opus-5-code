# 🏛️ وثيقة المواصفات المعمارية الشاملة والبرومبت المرجعي (Master Spec & Prompt v5.0)
## دليل التكامل التشغيلي المعتمد لمزود Syntx AI داخل Gateway Service بنظام خزان الاعتمادات الموزع والمحصن (Enterprise Platform Credential Pool)

> **📌 المراجع الدستورية ومصادر الحقيقة:**
> 1. **عقد البوابة الرسمي:** `__gateway-service/docs/CONTRACT.md` و `gateway/contracts.py` (الحاكم الأول للواجهة البرمجية).
> 2. **ملفات الـ HAR الحية للشبكة (Ground Truth):** `syntx.ai....har` (8.3 MB) و `syntx.ai...har` (2.0 MB) في مجلد `har/`.
> 3. **الكود الفعلي المعتمد في بيئة العمل:** `01_syntx_master_hub.py` (776 سطر).
> 4. **دستور بولا الهندسي v1.2:** القانون 8 (الإسناد الحرفي)، القانون 10 (العزل المعماري)، والقانون 6 و 9 (بوابة الاعتماد `[GO]`).

---

## 0. المراجع وسلّم الأولوية عند التعارض (Precedence Rules)

عند حدوث أي اختلاف في التفسير أثناء التنفيذ، يُطبق سلم الأولوية الإلزامي:
1. **المرتبة الأولى (حاكم مطلق):** كود العقد `gateway/contracts.py` ووثيقته التوأم `docs/CONTRACT.md`.
2. **المرتبة الثانية (الواقع الحرفي للشبكة):** وقائع ملفات الـ HAR الحية المثبتة لشبكة Syntx AI.
3. **المرتبة الثالثة (الكود التشغيلي المجرب):** سكربت `01_syntx_master_hub.py` وخبرة استطلاع الرسائل باللاب.
4. **المرتبة الرابعة (التحسينات الجمالية والأسلوب):** تأتي أخيراً ولا تملك حق تعطيل ما قبلها.

---

## 1. الحدود والـ Non-goals (ما لا يضمنه المزود)

1. **انقطاع خوادم Syntx كلياً (Complete Outage):** إذا كان السيرفر الخارجي معطلاً أو أرجع 5xx، أو فرغ الخزان، يُرجع المزود فوراً `ErrorCategory.PROVIDER_UNAVAILABLE` أو `ErrorCategory.RATE_LIMITED` بأمان ودون تعليق السيرفر.
2. **صفر تجهيز اعتمادات في مسار الطلب الحرج (Zero Critical Path Provisioning):** يُحظر حظراً باتاً محاولة توليد أو استخراج اعتمادات أثناء معالجة طلب `generate_text`. إدارة الاعتمادات وظيفة حصرية لمحرك مستقل يعمل خارج مسار الخدمة (Out-of-Band).
3. **حصر النطاق في توليد النصوص (Scope Restriction):** يدعم المزود في هذا الإصدار حصراً عملية `GatewayOperation.GENERATE_TEXT`؛ أي عمليات أخرى تُرفض كـ `UNSUPPORTED_CAPABILITY`.
4. **لا ندعم تدفق SSE المباشر للعميل الخارجي (No Direct External SSE):** الاتصال الداخلي يجمع الرد عبر استطلاع الرسائل المكتملة (`Polling`) ويرجع رداً نهائياً موحداً ومغلقاً للـ Gateway.

---

## 2. العقد الموحد (نسخة حرفية من `gateway/contracts.py`)

### أ. كائنات الواجهة البرمجية (Layer 2 Boundary):
```python
class ProviderContext(ContractModel):
    operation: GatewayOperation          # حصراً GatewayOperation.GENERATE_TEXT
    model: str                          # اسم الموديل المطلوب
    request_id: str                     # معرف التتبع الموحد
    tenant_id: str                      # معرف المستأجر (للتدقيق فقط)
    credential_mode: CredentialMode     # CredentialMode.PLATFORM
    credential_value: str | None = None # دائماً None في وضع platform
    payload: dict[str, Any]             # {"messages": [...], "temperature": float, "max_tokens": int}
    timeout_ms: int                     # المهلة الكلية المحددة من البوابة

class FacadeResult(ContractModel):
    succeeded: bool
    output: dict[str, Any] | None = None  # {"text": str, "finish_reason": "stop"|"length"|"filter"}
    usage: Usage | None = None            # Usage(input_tokens=int, output_tokens=int, units=1)
    error: GatewayError | None = None     # في حالة الفشل فقط

class Usage(ContractModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    units: int = 1
```

### ب. قائمة الأخطاء الـ 12 المعتمدة حصراً في العقد (`ErrorCategory`):
```python
class ErrorCategory(StrEnum):
    AUTH_EXPIRED = "auth_expired"                     # توكن البوابة منتهٍ
    INVALID_CREDENTIAL = "invalid_credential"         # اعتماد Syntx ملغى أو غير صالح (401/403)
    RATE_LIMITED = "rate_limited"                     # حظر معدل مؤقت (429) مع retry_after_ms
    QUOTA_EXCEEDED = "quota_exceeded"                 # نفاد رصيد الحساب نهائياً
    MODEL_UNAVAILABLE = "model_unavailable"           # موديل غير موجود upstream (404)
    PROVIDER_UNAVAILABLE = "provider_unavailable"     # السيرفر واقع أو الخزان فارغ تماماً
    UNSUPPORTED_CAPABILITY = "unsupported_capability" # طلب عملية غير مدعومة
    BAD_REQUEST = "bad_request"                       # خطأ في الـ Payload المرسل
    CONTENT_REJECTED = "content_rejected"             # رفض المحتوى لانتهاك السياسات
    TIMEOUT = "timeout"                               # انتهاء مهلة الاتصال أو الرد
    RETRYABLE_SERVER_ERROR = "retryable_server_error" # خطأ عابر 5xx من السيرفر
    NON_RETRYABLE_ERROR = "non_retryable_error"       # استجابة مشوهة أو خطأ دائم
```

---

## 3. بيئة التشغيل وآلية القفل (Concurrency & Locking)

- **بيئة التشغيل:** Multi-Worker (Uvicorn `--workers 4`) و Multi-Container (Docker).
- **آلية القفل الإلزامية:** استخدام قفل نظامي عبر مكتبة `filelock`:
  ```python
  from filelock import FileLock
  pool_lock = FileLock("accounts_syntx.json.lock", timeout=10.0)
  ```
- **الحفظ الذري (Atomic Persistence):**
  الكتابة تتم دائماً لملف مؤقت `accounts_syntx.json.tmp` متبوعة بـ `os.replace` داخل نطاق القفل.
- **سياسة الحجز الحصري (Exclusive Lease Pattern):**
  عند بدء الطلب، يُحجز الاعتماد ويُوسم كـ `busy` مع تسجيل `last_used_at` وتدوير المؤشر (Round-Robin)، مع منع اشتراك طلبين في نفس الاعتماد في ذات اللحظة لمنع تضارب جلسات الشات.

---

## 4. دورة حياة الاعتماد (State Machine & Transitions)

```
                 ┌─────────────┐
                 │   active    │◄─────────────────┐
                 └──────┬──────┘                  │
                        │                         │
     سحب للطلب (Lease)  │                         │ انتهاء مدة الـ Cooldown
                        ▼                         │ (now >= cooldown_until)
                 ┌─────────────┐                  │
                 │    busy     │                  │
                 └──┬───────┬──┘                  │
                    │       │                     │
           اكتمال   │       │ تلقي 429            │
           الطلب    │       ▼                     │
           بنجاح    │   ┌──────────────┐          │
                    │   │   cooldown   ├──────────┘
                    │   └──────────────┘
                    │
                    │ تلقي 401 / 403 (Invalid/Revoked)
                    ▼
             ┌──────────────┐
             │   expired    │ (استبعاد نهائي)
             └──────────────┘
```

---

## 5. سياسة الأعطال والمحاولات (Fault Policy & Retry Matrix)

| كود الرد / الحالة | فئة الخطأ في العقد | التصرف الداخلي في المزود | هل يُعاد الطلب داخلياً؟ | الحد الأقصى للمحاولات | المهلة المسموحة |
|---|---|---|:---:|:---:|:---:|
| **200 OK (اكتمال الرد)** | لا يوجد (نجاح) | استخراج النص وحساب Usage | ❌ لا | 1 | $\le 90\text{s}$ |
| **401 / 403** | `INVALID_CREDENTIAL` | وسم الاعتماد كـ `expired` فوراً | ✅ نعم (باعتماد بديل) | 1 محاولة فقط | $\le 30\text{s}$ |
| **429 Rate Limit** | `RATE_LIMITED` | وسم الاعتماد كـ `cooldown` لـ 6 ساعات | ✅ نعم (باعتماد بديل) | 1 محاولة فقط | $\le 30\text{s}$ |
| **خلو الخزان من الاعتمادات** | `PROVIDER_UNAVAILABLE` | إرجاع الخطأ فوراً بدون تعليق | ❌ لا | 0 | $\le 10\text{ms}$ |
| **404 Not Found** | `MODEL_UNAVAILABLE` | إرجاع خطأ عدم وجود الموديل | ❌ لا | 0 | $\le 10\text{s}$ |
| **400 مع `grok-4.6`** | `BAD_REQUEST` | تراجع فوري وتلقائي لـ `grok-4.5` | ✅ نعم (بنفس الاعتماد) | 1 محاولة فقط | $\le 30\text{s}$ |
| **400 عادي / 422** | `BAD_REQUEST` | فحص محتوى الخطأ للتحقق من السياسة | ❌ لا | 0 | $\le 10\text{s}$ |
| **انتهاك السياسات** | `CONTENT_REJECTED` | إرجاع خطأ رفض المحتوى | ❌ لا | 0 | $\le 10\text{s}$ |
| **500 / 502 / 503 / 504** | `RETRYABLE_SERVER_ERROR` | تسجيل عطل المزود الخارجي | ❌ لا (أو 1 باعتماد بديل) | 1 | $\le 30\text{s}$ |
| **Timeout (انقطاع مهلة)** | `TIMEOUT` | إرجاع خطأ مهلة الاستجابة | ❌ لا | 0 | $30\text{s} / 90\text{s}$ |
| **شبكة مقطوعة (Network)** | `PROVIDER_UNAVAILABLE` | خوادم Syntx غير قابلة للوصول | ❌ لا | 0 | $\le 10\text{s}$ |
| **JSON تالف (Malformed)** | `NON_RETRYABLE_ERROR` | استجابة غير مفهومة من المزود | ❌ لا | 0 | $\le 10\text{s}$ |

---

## 6. ميزانية المهل ومقاييس الأداء (Latency Budgets)

1. **زمن سحب الاعتماد محلياً ($t_{select}$):** $\le 10\text{ms}$ (p99) من الذاكرة/الملف المحلي.
2. **مهلة قبول وظيفة التوليد الشبكية ($t_{accept}$):** $\le 30\text{s}$ عبر اتصال الـ HTTP.
3. **المهلة الإجمالية لاكتمال الإجابة ($t_{total}$):** $\le 90\text{s}$ (تشمل الإطلاق + استطلاع الرسائل بفاصل $1.2\text{s}$).

---

## 7. منع التوليد المكرر وحماية الحصص (Idempotency)

- لكل اعتماد يتم إنشاء وربط `chat_uuid` مستقل مسبقاً.
- في حال انقطاع الاتصال بعد إرسال POST `/api/v1/llm/generate`، يُحظر إرسال POST جديد فوراً؛ بل يقوم الـ Upstream بعمل Polling على مسار `/chats/{chat_uuid}/messages`. إذا وُجدت الإجابة تُسحب فوراً لمنع تكرار التوليد وهدر الموارد.

---

## 8. إدارة الخزان المستقل (Credential Pool Health Manager)

- **النمط:** Singleton Daemon محمي بـ `worker.lock`.
- **الحجم المستهدف:** خزان متزن من **10 إلى 20 اعتماداً نشطاً** في `accounts_syntx.json`.
- **قاطع الدائرة (Circuit Breaker):** عند فشل تحديث أو فحص الاعتمادات 3 مرات متتالية، يدخل الـ Worker في وضع راحة تدريجي (5 إلى 15 دقيقة) لمنع إرهاق الشبكة.

---

## 9. الموديلات الـ 4 المعتمدة (The Elite 4)

| اسم الموديل في البوابة (`name`) | المعامل المطلوب في Syntx (`ai_name`) | سياق الذاكرة (`context_window`) | المصدر والدليل من الـ HAR |
|---|---|:---:|---|
| **`claude-opus-4-8`** | `claude` | 200,000 | مثبت في استجابة `/api/v1/llm/models` في الـ HAR |
| **`gpt-5.6-terra`** | `chatgpt` | 128,000 | مثبت في استجابة `/api/v1/llm/models` في الـ HAR |
| **`claude-sonnet-5`** | `claude` | 200,000 | مثبت في استجابة `/api/v1/llm/models` في الـ HAR |
| **`grok-4.6`** | `grok` | 131,072 | مثبت في استجابة `/api/v1/llm/models` في الـ HAR |

- **سياسة التراجع لموديل Grok:** لو أرجع السيرفر 400 لـ `grok-4.6`، يتراجع الـ Upstream تلقائياً لـ `grok-4.5` ويدوّن ذلك في سجلات التشغيل.

---

## 10. الاختبارات المعزولة (Hermetic Testing Suite)

- **Zero Network:** استخدام `httpx.MockTransport` عبر منفذ الحقن `_default_transport`.
- **fixtures حقيقية منزوعة الأسرار:** مقتبسة نصاً من الـ HAR لتغطية النجاح، الـ 429، الـ 401، والـ Timeout.
- **زمن التنفيذ:** إنهاء الحزمة بالكامل في أقل من ثانيتين.

---

## 11. المراقبة وحماية الأسرار (Observability & Zero Leak)

- تسجيل إحصائيات الخزان: `active_count`, `cooldown_count`, `latency_ms`.
- حظر طباعة التوكنات أو الاعتمادات أو نصوص المستخدم الحساسة في السجلات.
- إدراج `accounts_syntx.json` وملفات الأقفال في `.gitignore`.

---

## 12. بوابة الاعتماد والتنفيذ (Approval Gate)

الكود التنفيذي ينتظر كلمة الاعتماد الدستورية الرسمية:
### **`[GO]`**

---

---

## 🧩 الملاحق الفنية الستة الإلزامية (The 6 Technical Appendices)

### ملحق 1: JSON Schema الكامل لخزان الاعتمادات (`accounts_syntx.json`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SyntxCredentialPool",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["id", "token", "chat_uuid", "status", "created_at"],
    "properties": {
      "id": {"type": "string"},
      "token": {"type": "string"},
      "chat_uuid": {"type": "string"},
      "status": {"type": "string", "enum": ["active", "busy", "cooldown", "expired"]},
      "cooldown_until": {"type": ["string", "null"], "format": "date-time"},
      "last_used_at": {"type": ["string", "null"], "format": "date-time"},
      "failure_count": {"type": "integer", "default": 0},
      "created_at": {"type": "string", "format": "date-time"}
    }
  }
}
```
**مثال واقعي منزوع الأسرار:**
```json
[
  {
    "id": "acc_syntx_01",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "chat_uuid": "07d713b3-d876-465e-8d8c-970ec1ef3cdb",
    "status": "active",
    "cooldown_until": null,
    "last_used_at": "2026-09-08T02:00:00Z",
    "failure_count": 0,
    "created_at": "2026-09-08T01:00:00Z"
  }
]
```

### ملحق 2: جدول الأخطاء الـ 12 المعتمدة كاملاً من كود العقد
| فئة الخطأ في العقد (`ErrorCategory`) | هل هو Retryable؟ | متى يُطلق في مزود Syntx؟ |
|---|:---:|---|
| `auth_expired` | ⚠️ نعم | توكن البوابة انتهى (تحديث واستئناف تلقائي) |
| `invalid_credential` | ❌ لا | رد 401 أو 403 من خوادم Syntx (توكن ملغى) |
| `rate_limited` | ⚠️ نعم | رد 429 من Syntx مع تمرير `retry_after_ms` |
| `quota_exceeded` | ❌ لا | نفاد الحصة المالية للحساب نهائياً |
| `model_unavailable` | ❌ لا | طلب موديل خارج النخبة الـ 4 أو رد 404 للموديل |
| `provider_unavailable` | ⚠️ نعم | خلو الخزان من الاعتمادات أو انقطاع شبكة Syntx |
| `unsupported_capability` | ❌ لا | طلب عملية بخلاف `generate_text` |
| `bad_request` | ❌ لا | حمولة طلب مشوهة أو عناصر غير مطابقة للشروط |
| `content_rejected` | ❌ لا | رفض محتوى الطلب من فلتر الأمان |
| `timeout` | ⚠️ نعم | تجاوز مهلة الـ 30 ثانية للاتصال أو 90 ثانية للرد |
| `retryable_server_error` | ⚠️ نعم | رد 500 أو 502 أو 503 أو 504 من سيرفر المزود |
| `non_retryable_error` | ❌ لا | استجابة مشوهة لا يمكن فك شفرتها برمجياً |

### ملحق 3: شجرة ملفات حزمة المزود (`providers/syntx/`)
```
__gateway-service/providers/syntx/
├── __init__.py           # تعريف الحزمة وتسجيل المزود
├── definition.py         # إعلان العقد الصادق والقدرات والموديلات (الطبقة 3)
├── _upstream.py          # إدارة خزان الاعتمادات وقفل الملفات والاتصال الشبكي (الطبقة 1)
└── adapter.py            # فحص الحمولة وترجمة الردود للأخطاء الـ 12 (الطبقة 2)
```

### ملحق 4: جدول ميزانية المهل وإعادة المحاولات (Timeouts & Retry Budget)
| المرحلة / العملية | القيمة المعيارية | الإجراء عند التجاوز |
|---|:---:|---|
| سحب الاعتماد ($t_{select}$) | $\le 10\text{ms}$ (p99) | استرجاع الاعتماد الجاهز التالي |
| مهلة اتصال الـ HTTP ($t_{connect}$) | $5\text{s}$ | إرجاع `PROVIDER_UNAVAILABLE` |
| مهلة قبول الوظيفة ($t_{accept}$) | $30\text{s}$ | إرجاع `TIMEOUT` أو محاولة بديلة |
| فاصل الاستطلاع (Poll Interval) | $1.2\text{s}$ | فحص رسائل الشات |
| المهلة الإجمالية للطلب ($t_{total}$) | $90\text{s}$ | إرجاع `TIMEOUT` فوري |
| سقف المحاولات البديلة (Max Failover) | 1 محاولة فقط | منع تكرار الحسابات وإجهاد السيرفر |

### ملحق 5: جدول الإعدادات المركزية (Configuration Map)
| الإعداد | القيمة الافتراضية | الوصف |
|---|:---:|---|
| `ACCOUNTS_FILE` | `accounts_syntx.json` | مسار ملف الخزان المحلي |
| `LOCK_FILE` | `accounts_syntx.json.lock` | مسار قفل التزامن متعدد العمليات |
| `TARGET_POOL_SIZE` | 15 | الحجم المستهدف للاعتمادات النشطة (10–20) |
| `COOLDOWN_DEFAULT_SECONDS` | 21526 (6 ساعات) | مدة الكولداون عند غياب `Retry-After` |
| `MAX_FAILOVER_ATTEMPTS` | 1 | الحد الأقصى للمحاولات البديلة لكل طلب |
| `POLL_INTERVAL_SECONDS` | 1.2 | زمن الانتظار بين كل طلب استطلاع |

### ملحق 6: التوقيع البرمجي المعتمد لـ `generate_text`
```python
async def generate_text(context: ProviderContext) -> FacadeResult:
    """الواجهة غير المتزامنة الرسمية للـ Gateway — لا تكسر الـ Event Loop."""
    ...
```
*(تم تأكيد أن الدالة `async` وتعتمد على `httpx.AsyncClient` و `asyncio.sleep` لضمان عدم حجز خيوط السيرفر).*

---

## 📋 الإجابات الحاسمة على استفسارات المجموعات الـ 8

1. **الـ Schema وحالات الحساب:** محددة بنسبة 100% في الملحق 1 والملحق 3، والحالات هي (`active`, `busy`, `cooldown`, `expired`).
2. **التزامن والـ Multi-Worker:** القفل عبر `FileLock` مع الحفظ الذري `Atomic Write` يحمي العمليات المتعددة بالكامل.
3. **طبيعة الـ 429:** مثبت كـ Cooldown لمدة 6 ساعات بالدليل من الـ HAR؛ الحساب لا يموت بل يستريح مؤقتاً.
4. **الأخطاء الـ 12:** مدرجة كاملة بالأسماء الرسمية في الملحق 2.
5. **البروتوكول واستطلاع الرد:** مسار التوليد هو `POST /api/v1/llm/generate?ai_name={ai_name}`، واستطلاع الرد هو `GET /api/v1/chats/{chat_uuid}/messages`، وعلامة الاكتمال هي `author_id == -1` و `completed == true`.
6. **Async vs Sync:** الدالة غير متزامنة بالكامل `async def generate_text` مع `httpx.AsyncClient`.
7. **عزل التجهيز:** حزمة البوابة `providers/syntx/` معزولة تماماً ولا تعرف شيئاً عن كيفية ملء الخزان، بل تستهلك الاعتمادات الجاهزة فقط.
8. **الأمان والمراقبة:** استبعاد `accounts_syntx.json` بـ `.gitignore` وحظر طباعة التوكنات في أي Log.
