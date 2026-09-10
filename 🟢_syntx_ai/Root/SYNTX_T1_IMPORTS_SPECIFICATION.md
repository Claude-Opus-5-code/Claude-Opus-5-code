# 🏛️ وثيقة مواصفات مهمة T1: إصلاح استيراد secrets و html في مسجل Syntx AI

- **الملف المستهدف:** `.AAA_GGG_iii_VIBE_CODING/🟢_syntx_ai/02_syntx_register.py`
- **التصنيف الدستوري:** **T1** (تعديل استيراد محدود $\le 10$ أسطر diff لا يمس أي منطق تنفيذي أو شبكي).
- **معرف المرساة:** `anchor_syntx_reg_pre_t1`
- **بصمة المرساة (LF SHA-256):** `dda124acb16c87bd26186542d1a601a0903c77323a9b8f76383c8af336e14b96` (499 سطر)
- **الحالة الحالية:** **Pre-edit** (الكود الأصلي مجمد في المرساة وغير ملموس).

---

## 1. 🔍 الفرضية وسند الاكتشاف (Ground Truth & Discovery)

أظهر فحص التحليل الساكن (**Gate B: pyflakes**) على الملف `02_syntx_register.py` الأخطاء التالية:
- `02_syntx_register.py:153:62: undefined name 'secrets'` (في دالة `create_email`)
- `02_syntx_register.py:161:29: undefined name 'html'` (في دالة `create_email`)
- `02_syntx_register.py:190:69: undefined name 'secrets'` (في دالة `poll_otp`)

**الأثر الميداني:**  
عند استدعاء `create_email()` أو `poll_otp()`، يتم إلقاء استثناء `NameError`، ويتم ابتلاعه بصمت داخل كتل `try/except: pass`، مما يؤدي إلى فشل توليد البريد وفشل استقبال كود التحقق OTP دون أي رسالة خطأ واضحة.

---

## 2. 👑 قانون المشرط الجراحي (Scalpel Law — BEFORE vs AFTER)

### كتلة `BEFORE` (مستخرجة ميكانيكياً من المرساة `02_syntx_register.py.anchor` السطور 19–24):
```python
import json
import random
import string
import re
import argparse
import urllib.parse
```

### كتلة `AFTER` (المقترحة للتطبيق الجراحي):
```python
import json
import random
import string
import secrets
import html
import re
import argparse
import urllib.parse
```

### الحساب الرياضي للدلتا:
- أسطر مضافة (`+`): 2 (`import secrets`, `import html`)
- أسطر محذوفة (`-`): 0
- إجمالي الـ diff: **+2 سطر** (تحت سقف الـ T1 $\le 10$ أسطر).
- عدد الأسطر المتوقع بعد التطبيق: **501 سطر**.

---

## 3. 🛡️ بوابات الجودة المطلوبة (Quality Gates A & B)

1. **Gate A (صياغة وتركيب):**  
   تشغيل `python -m py_compile "02_syntx_register.py"` $\rightarrow$ الخروج بكود 0.
2. **Gate B (تحليل ساكن محايد):**  
   تشغيل `pyflakes` والتأكد من انخفاض عدد التحذيرات وزوال خطأي `undefined name 'secrets'` و `undefined name 'html'` تماماً.

---

## 4. 🧪 البرهان الكمي وخطة التحقق (Empirical Verification)

- **معيار النجاح:**  
  اختبار دالة `create_email()` لإنشاء إيميل تجريبي صالح عبر دومين `*.mailings.live` دون رمي `NameError`.
- **معيار الفشل:**  
  ظهور أي خطأ استيراد أو استمرار إرجاع `None` بسبب غياب الموديولات.

---

## 5. 🚪 بوابة المراجعة والاعتماد (Review Gate)

- [ ] **[GO]** — الموافقة على تطبيق الـ Hunk أعلاه والتحقق من Gates.
- [ ] **[HOLD]** — إيقاف التعديل لأي ملاحظات هندسية.
- [ ] **[RETURN]** — إعادة صياغة المواصفات.
