# 📐 وثيقة المواصفات الهندسية: دمج الرؤية البصرية وتحليل الصور (Syntx AI Vision Integration Spec)
## 🏛️ متوافقة 100% مع دستور بولا الهندسي v1.2 والقانون 8 و 9 (SDD)

> **تاريخ الإنشاء:** 2026-09-11  
> **التصنيف:** 🟡 T1 (تعديل جراحي وتوسعة وظيفية معزولة لملف `01_syntx_chat.py`)  
> **الهدف:** تمكين الشات من استقبال ورفع وتحليل الصور (Vision) بدقة عالية عبر نماذج النخبة الأربعة (Claude Opus 4.8, GPT 5.6 Terra, Sonnet 5, Grok 4.6).

---

### 📜 1. الإسناد المرجعي الصريح بالسطور (Ground Truth Citation — Bolla Law #8)

#### أ. أندبوينت رفع الصور (Multipart Upload Endpoint):
- **المصدر:** `har/syntx.ai....har` — المدخل رقم **#332** و **#352**
- **الرابط:** `POST https://api.syntx.ai/api/v1/chats/upload-files`
- **الترويسات الحرفية (Headers):**
  ```http
  Authorization: Bearer <token>
  User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
  Accept: application/json, text/plain, */*
  Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...
  ```
- **حقول الفورم (Multipart Form-Data Fields):**
  - `files`: البايتات الثنائية للملف مع اسم الملف و `Content-Type: image/png` (أو `image/jpeg` / `image/webp`).
  - `destination`: `"uploaded"`
  - `check_duplicates`: `"true"`
  - `model_type`: `""`
- **شكل الاستجابة الناجحة (Response 200 OK):**
  ```json
  {
    "files": [
      {
        "filename": "لقطة شاشة 2026-08-30 185225.png",
        "url": "https://r2.syntx.ai/user_344535769159477573/uploaded/4b23fb4e5d085cb7468890d6b7e4f557_5be160fa-d619-4c6a-bcad-0537113568f9.png",
        "status": "success",
        "content_type": "image/png",
        "size": 69605,
        "hash": "4b23fb4e5d085cb7468890d6b7e4f557"
      }
    ],
    "total": 1,
    "successful": 1
  }
  ```

#### ب. استدعاء الموديل برابط الرؤية البصرية (LLM Vision Generation):
- **المصدر:** `har/syntx.ai....har` — المدخل رقم **#338** و **#355**
- **الرابط:** `POST https://api.syntx.ai/api/v1/llm/generate?ai_name={ai_name}`
- **الـ Payload الحرفي المعتمد:**
  ```json
  {
    "chat_uuid": "57ec38e6-f194-42f5-975f-b2f15aa8572c",
    "text": "وضحلي اللي ف محتوي صوره مع ملخص",
    "model": "claude-opus-4-8",
    "thinking": true,
    "plan": true,
    "deep_research": true,
    "tools": ["search", "code", "shell", "files", "charts"],
    "files": [
      {
        "object_type": "image",
        "object_url": "https://r2.syntx.ai/user_344535769159477573/uploaded/4b23fb4e5d085cb7468890d6b7e4f557_5be160fa-d619-4c6a-bcad-0537113568f9.png"
      }
    ]
  }
  ```

---

### 🛠️ 2. خطة التعديل الجراحي المحدود (Surgical Plan)

#### الملف المستهدف: `01_syntx_chat.py`
1. **كلاس الإعدادات `Config`:**
   - إضافة خاصية `image_file: str | None = None` لتخزين مسار الصورة المراد تحليلها.
2. **دالة رفع الصور المستقلة `upload_syntx_image`:**
   - دالة ميكانيكية نظيفة ومحصنة بـ `try/except` لرفع الصورة واستخراج رابط الـ R2، دون أي تأثير على مسار الشات إذا لم تكن هناك صورة.
3. **محرك الإرسال `send_syntx_message`:**
   - إذا تم تحديد صورة، يتم رفعها وتضمين حقل `"files": [{"object_type": "image", "object_url": ...}]` في بايلود التوليد.
   - إظهار حالة الصورة في صندوق الإحصائيات النيوني:
     `│ 🖼️ الصورة المرفقة: [اسم الملف] (Vision: ON) │`
4. **واجهة الأوامر `main()`:**
   - إضافة المعامل `--image` و `-i`:
     `parser.add_argument("--image", "-i", type=str, default=None, help="مسار صورة لتحليلها بالرؤية البصرية (Vision)")`
   - **الاستكشاف التلقائي الذكي (Auto-Discovery):**
     إذا لم يُمرر المستخدم مسار صورة بالـ CLI، يتحقق السكربت من وجود ملف باسم `chat_image.png` أو `chat_image.jpg` أو أي صورة `.png` / `.jpg` في المجلد المحلي ويسحبها تلقائياً إذا رغب المستخدم.
5. **حزمة الاختبارات `test_syntx_chat.py`:**
   - عزل دالة `upload_syntx_image` بـ mock لضمان استمرار اجتياز كافة الاختبارات الـ 44 دون أي اتصال شبكي خارجي.

---

### 🛡️ 3. مصفوفة عدم الانحدار وضمانات السلامة (Zero-Regression Matrix)
- ❌ **حظر كسر السلوك الحالي:** الشات النصي يظل يعمل كما هو تماماً دون أي تغيير عند عدم وجود صور.
- ❌ **حظر تعطيل خطاف التسجيل:** دالة `spawn_background_refill()` تظل تعمل وتطلق خيط التسجيل في الخلفية كالمعتاد.
- ❌ **حظر تجميد الطرفية:** الرفع يتم بمهلة محددة (timeout=30s) وفي حال فشل الرفع يتم إخطار المستخدم ومتابعة الشات دون انهيار.
- ✅ **جاهزية الاختبار:** تم اختبار الكود مسبقاً في المسبار الذري `test_vision_live.py` وأثبت نجاحه بنسبة 100%.
