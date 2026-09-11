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

مرحبًا يا باشمهندس. مهمتك الحالية محددة وصريحة وشاملة:
لدينا مشروعين مستقرين في المستودع:
1. **المشروع الأول (`🟢_syntx_ai`):** وهو **المرجع الهندسي الذهبي (Golden Ground Truth)** الذي يحتوي على المنظومة الثلاثية الكاملة لمزود Syntx AI (كاملة ومجربة ميدانياً بنسبة 100%):
   - 💬 `01_syntx_chat.py`: محرك الاستدلال، دعم النماذج الـ 4 (`gpt-5.6-terra`, `claude-opus-4-8`, `claude-sonnet-5`, `grok-4.6`)، دعم الرؤية البصرية للصور (Image Vision عبر حقل `files`)، والتدوير التلقائي والحذف الذري عند الاستنفاد (429).
   - 🏭 `02_syntx_register.py`: مصنع الحسابات الذاتي، وتخطي الحمايات، مع الحذف الفوري لصندوق البريد المؤقت (`deleteEmail` عبر Livewire) وتصفير الجلسات بنظافة 100%.
   - 🔄 `03_syntx_refresh.py`: محرك فحص صحة الحسابات وتجديد التوكنات المنتهية تلقائياً.
   - 💾 `accounts_syntx.json`: خزان الحسابات النشطة (يحتوي حالياً على 17 حساباً مفعلاً).
2. **المشروع الثاني (`__gateway-service`):** خدمة البوابة الإنتاجية الموحدة (FastAPI) المبنية وفق عقد موحد (`docs/CONTRACT.md`) ودليل مهندس المزودين (`دليل_المهندس_ابدأ_من_هنا.md`).

المطلوب منك: **نقل وتسكين المنظومة الكاملة لمزود Syntx AI كـ Provider رسمي داخل `__gateway-service/providers/syntx/`** بكل قدراتها (الشات، النماذج الأربعة، الصور، استهلاك خزان الحسابات، وخطاف التعبئة/الصيانة الخلفي)، لتعمل بتناغم تام مع البوابة وتجتاز كافة اختبارات الـ Hermetic بنسبة 100%.

---

## 🛑 القواعد الحاكمة وغير القابلة للتفاوض (Non-Negotiable Rules):

1. **الخطة والتاسكات أولاً (Plan First):**
   * راجع الملفات الثلاثة (`01_syntx_chat.py` و `02_syntx_register.py` و `03_syntx_refresh.py`) بالإضافة لعقد البوابة (`docs/CONTRACT.md`) ودليل المهندس (`دليل_المهندس_ابدأ_من_هنا.md`).
   * قدّم خطة عمل تفصيلية (Implementation Plan) ومصفوفة مهام واضحة تحدد كيف ستوزع وتكيف ميزات الثلاثي بالكامل داخل مجلد `providers/syntx/` قبل كتابة أي كود.
2. **عدم إسقاط أي ميزة أو الافتراض (Zero Assumptions & No Feature Stripping):**
   * ملفات `🟢_syntx_ai` تظل ثابتة ومحمية كمرجع، وعليك نقل واستنساخ وظائفها بالكامل (الشات، النماذج، الرؤية البصرية، قفل الخزان بـ `FileLock`، وخطاف إعادة الملء).
   * ممنوع تقليص الوظائف أو حذف أي قدرة بدعوى التبسيط. إذا واجهت أي استفسار، اطرح سؤالك في الشات دون أي افتراض من عندك.
3. **العمل عبر فرع مستقل وفتح PR:**
   * افتح فرعاً جديداً: `feature/syntx-gateway-provider`.
   * ارفع التعديلات وافتح Pull Request رسمي عند الانتهاء.
4. **عدم لمس محرك البوابة المركزي (`gateway/`):**
   * التعديل محصور حصراً في إضافة حزمة المزود داخل `providers/syntx/`، تسجيل المزود بسطر واحد في `app.py`، وإضافة ملف الاختبارات `tests/providers/test_syntx.py`.

---

## 🏛️ المتطلبات البرمجية للتسليم (Required Deliverables):

أنشئ حزمة المزود داخل `__gateway-service/providers/syntx/` وفق المعمارية القياسية:

### 1. `definition.py`:
* الإعلان الصادق عن المزود:
  - `display_name = "Syntx"`
  - `credential_mode = "platform"` (التوكنات تُحل داخلياً عبر خزان الاعتمادات `accounts_syntx.json` بـ `FileLock`، المنصة لا تراها).
  - `operations = ["generate_text"]`
  - `capabilities = {"chat": True, "reasoning": True, "code": True, "vision": True}`
  - النماذج الأربعة المعتمدة:
    - `gpt-5.6-terra`
    - `claude-opus-4-8`
    - `claude-sonnet-5`
    - `grok-4.6`
  - `health_supported = False`

### 2. `_upstream.py` (الطبقة الداخلية الحرة لمنظومة Syntx):
* محرك الاتصال بـ Syntx AI الذي يدمج قدرات الثلاثي:
  - إدارة خزان الحسابات النشطة مع استخدام `FileLock` للحفظ الذري والتدوير اللحظي.
  - دعم خطاف الاستدعاء الخلفي غير الحاجب (`subprocess.Popen`) لتشغيل `02_syntx_register.py` لإعادة ملء الخزان عند الحاجة.
  - استدعاء أندبوينت التوليد: `POST https://api.syntx.ai/api/v1/llm/generate`.
  - تمرير الرسائل ودعم حقل الصور `"files": [{"object_type": "image", "object_url": "..."}]` في الـ Payload عند وجودها.
  - استخراج النص الصافي وحساب التوكنات (`Usage`).
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
