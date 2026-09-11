# 🏛️ وثيقة تفويض الوكيل الخارجي: نقل ودمج مزود Syntx AI في Gateway Service
## Mandate & Master Prompt for External Agent (Claude Opus 5)

> **📌 المرجع الحاكم والدستوري:** دستور بولا الهندسي v1.2 وميثاق تسليم الوكلاء المتوازيين  
> **الهدف:** نقل وتسكين مزود `Syntx AI` بالكامل داخل خدمة البوابة الموحدة `__gateway-service` كـ Provider رسمي معتمد  
> **المستودع الرسمي:** `https://github.com/Claude-Opus-5-code/Claude-Opus-5-code.git`  
> **الفرع الأساسي:** `main` (العمل يتم عبر فرع جديد وفتح PR)  

---

### 📋 نص الرسالة الموجهة للوكيل الخارجي (انسخ النص بالكامل وأرسله للوكيل):

```markdown
# 🚀 MISSION MANDATE: Port & Integrate Syntx AI Provider into `__gateway-service`

مرحبًا يا باشمهندس. مهمتك الحالية محددة وصريحة بدون أي تعقيد:
لدينا مشروعين مستقرين في المستودع:
1. **المشروع الأول (`🟢_syntx_ai`):** يحتوي على عميل Syntx AI المتكامل والمجرب عملياً وميدانياً (`01_syntx_chat.py`)، مع خزان حسابات نشط (`accounts_syntx.json`)، ودعم كامل لنماذج الذكاء الاصطناعي الأربعة وللصور بالرؤية البصرية (Image Vision).
2. **المشروع الثاني (`__gateway-service`):** خدمة البوابة الإنتاجية الموحدة (FastAPI) المبنية وفق عقد موحد (`docs/CONTRACT.md`) ودليل مهندس المزودين (`دليل_المهندس_ابدأ_من_هنا.md`).

المطلوب منك: **نقل وتسكين مزود Syntx AI كـ Provider رسمي داخل `__gateway-service/providers/syntx/`** ليعمل بتناغم تام مع البوابة ويجتاز كافة الاختبارات (Hermetic Unit Tests) بنسبة 100%.

---

## 🛑 القواعد الحاكمة وغير القابلة للتفاوض (Non-Negotiable Rules):

1. **الخطة والتاسكات أولاً (Plan First):**
   * يُمنع كتابة أي كود قبل تقديم خطة عمل تفصيلية (Implementation Plan) ومصفوفة مهام واضحة تحدد ما ستقوم به خطوة بخطوة.
2. **عدم المساس بالمنطق التشغيلي أو الافتراض (Zero Assumptions & No Scope Alteration):**
   * منطق الشات، النماذج الأربعة، دعم الصور، وخزان الاعتمادات مجرب ومثبت بنسبة 100%.
   * وظيفتك هي فقط "التكييف والمواءمة" (Adapter Pattern) لتوصيل هذا المنطق بعقد البوابة، دون حذف أي ميزة أو تغيير السلوك القائم.
3. **العمل عبر فرع مستقل وفتح PR:**
   * افتح فرعاً جديداً: `feature/syntx-gateway-provider`.
   * ارفع التعديلات وافتح Pull Request رسمي عند الانتهاء.
4. **عدم لمس محرك البوابة المركزي (`gateway/`):**
   * التعديل محصور حصراً في إضافة مجلد `providers/syntx/`، تسجيل المزود بسطر واحد في `app.py`، وإضافة ملف الاختبارات `tests/providers/test_syntx.py`.

---

## 🏛️ المتطلبات البرمجية للتسليم (Required Deliverables):

أنشئ حزمة المزود داخل `__gateway-service/providers/syntx/` وفق المعمارية القياسية:

### 1. `definition.py`:
* الإعلان الصادق عن المزود:
  - `display_name = "Syntx"`
  - `credential_mode = "platform"` (المفتاح/التوكن يُحل داخلياً عبر خزان الاعتمادات `accounts_syntx.json`، المنصة لا تراه).
  - `operations = ["generate_text"]`
  - `capabilities = {"chat": True, "reasoning": True, "code": True, "vision": True}`
  - النماذج الأربعة المعتمدة:
    - `gpt-5.6-terra`
    - `claude-opus-4-8`
    - `claude-sonnet-5`
    - `grok-4.6`
  - `health_supported = False`

### 2. `_upstream.py` (الطبقة الداخلية الحرة):
* محرك الاتصال بـ Syntx AI المستوحى مباشرة من `01_syntx_chat.py`:
  - إدارة خزان الحسابات النشطة مع استخدام `FileLock` لقفل تزامن الملفات الذري.
  - استدعاء أندبوينت التوليد: `POST https://api.syntx.ai/api/v1/llm/generate`.
  - تمرير الرسائل والـ Prompt ودعم حقل الصور `"files": [{"object_type": "image", "object_url": "..."}]` في الـ Payload عند وجودها.
  - إرجاع النص المستخرج الصافي واستخدام التوكنات (`Usage`).

### 3. `adapter.py` (المترجم للطبقة 2):
* تنفيذ الدالة الرئيسية: `async def generate_text(context: ProviderContext) -> FacadeResult`.
* استخراج الـ Payload والتحقق من المدخلات.
* استدعاء الطبقة الداخلية `_upstream`.
* تحويل الأخطاء بدقة إلى مصفوفة الأخطاء الـ 12 المعتمدة في العقد (`ErrorCategory`):
  - `401/403` -> `INVALID_CREDENTIAL`
  - `404` -> `MODEL_UNAVAILABLE`
  - `429` -> `RATE_LIMITED`
  - `400/422` -> `BAD_REQUEST`
  - `5xx` -> `RETRYABLE_SERVER_ERROR`
  - `Timeout` -> `TIMEOUT`
* تسجيل المعالج في القاموس: `HANDLERS = {GatewayOperation.GENERATE_TEXT: generate_text}`.

### 4. `__init__.py`:
* تصدير `DEFINITION` و `HANDLERS`.

### 5. `app.py`:
* تسجيل المزود داخل دالة `register_live_providers` (بسطر واحد مماثل لمزود Groq).

### 6. `tests/providers/test_syntx.py`:
* كتابة اختبارات Hermetic كاملة معزولة (Zero Network Calls / Mocks):
  - اختبار نجاح التوليد النصي واستخراج الـ text والـ usage.
  - اختبار معالجة الصور ومصفوفة `files`.
  - اختبار تحويل كافة أكواد الأخطاء للأنواع المعتمدة في `ErrorCategory`.
  - اختبار عدم تسريب التوكنات أو المسارات الحساسة.
  - التأكد من اجتياز كامل اختبارات البوابة: `python -m pytest` بنجاح 100%.

---

## 🚦 خطوات البدء المطلوبة منك الآن:
1. راجع الدليل المرجعي: `__gateway-service/دليل_المهندس_ابدأ_من_هنا.md` ومثال `providers/groq/`.
2. راجع كود الشات في `🟢_syntx_ai/01_syntx_chat.py`.
3. قدّم خطتك الهندسية الشاملة ومصفوفة المهام للموافقة أولاً.
```
