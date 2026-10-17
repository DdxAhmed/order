# OrderTrofy — Automated Steam Code & Inventory Delivery

نظام متكامل وآمن لإدارة وتسليم أكواد التحقق (Steam Guard OTP) وحسابات الألعاب للعملاء تلقائيًا، مع فصل تام بين بوابة العملاء ولوحة تحكم المشرفين.

---

## 1. الهيكلية المعمارية (Architecture Overview)

- **الواجهة الخلفية (Backend API):**
  - **FastAPI** على Python 3.12 مع خادم **Uvicorn** على المنفذ `8000`.
  - قاعدة بيانات **PostgreSQL 18** مع بروتوكول `asyncpg` للعمليات غير المتزامنة و `psycopg v3` للترحيلات.
  - تشفير متقدم لكلمات المرور باستخدام **Argon2id** وتشفير متناظر للبيانات الحساسة وأكواد التحقق باستخدام **Fernet AES-128-CBC**.
  - ترحيلات آلية متسلسلة عبر **Alembic** (10 ترحيلات متكاملة).
  - توثيق تفاعلي فوري لجميع نقاط النهاية عبر Swagger: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs).

- **الواجهة الأمامية (Frontend SPA):**
  - مبنية بواسطة **React 19** و **Vite** مع مكتبة **Lucide Icons** وتصميم Dark Mode زجاجي (Glassmorphism).
  - دعم كامل للغة العربية (RTL) مع زر تحويل فوري للإنجليزية (LTR).
  - **فصل كامل للمسارات والواجهات:**
    - **بوابة العميل (`/`):** واجهة مخصصة بالكامل للعميل لإدخال رقم الطلب واسم المستخدم واستلام كود الدخول ونسخه بضغطة زر. **لا تحتوي على أي روابط أو عناصر تخص لوحة الإدارة.**
    - **تسجيل دخول المشرفين (`/admin/login`):** صفحة دخول معزولة للمسؤولين.
    - **لوحة تحكم المشرفين (`/admin`):** واجهة محمية بحواجز برمجية (`Route Guards`) وتفويض خادم صارم تشمل إدارة المخزون، الطلبات، العملاء، صناديق البريد، استيراد CSV، وسجلات التدقيق.

---

## 2. تشغيل المشروع محلياً على ويندوز (Local Windows Setup)

### 2.1 تشغيل قاعدة البيانات (PostgreSQL 18)
تأكد من تشغيل PostgreSQL على المنفذ المحلي **`5433`**:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\postgres.exe" -D "$env:LOCALAPPDATA\ordertrofy_pgdata"
```

### 2.2 تشغيل خادم الباك إند (FastAPI)
من المجلد الرئيسي للمشروع:
```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
سيعمل الخادم على: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 2.3 تشغيل خادم الفرونت إند (Vite Dev Server)
من مجلد `frontend`:
```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
سيعمل تطبيق React على: [http://127.0.0.1:5173](http://127.0.0.1:5173)

### 2.4 تشغيل معالج المهام الخلفية (Worker)
```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe -m app.worker
```

---

## 3. إدارة حسابات المشرفين (Admin Management CLI)

### إنشاء مشرف جديد
```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe -m app.cli create-admin --email admin@ordertrofy.store --password "YourStrongPassword!"
```

### تغيير كلمة مرور مسؤول حالي بأمان
```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe -m app.cli change-password --email admin@ordertrofy.store --password "NewSecurePassword!"
```

---

## 4. تشغيل الاختبارات الآلية (Automated Tests)

المشروع يحتوي على **22 اختباراً آلياً متكاملاً** تغطي الأمان، التشفير، المصادقة، العزل، فحص الرسائل، حدود المعدلات والتزامن:

```powershell
$env:PYTHONUTF8=1
.\.venv\Scripts\python.exe -m pytest -v tests
```

---

## 5. التشغيل عبر Docker Compose

### التشغيل في بيئة التطوير المحلية
```powershell
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
```

### إيقاف الخدمات
```powershell
docker compose down
```

---

## 6. وثائق النظام المفصلة
- 📐 [الهندسة المعمارية للنظام (ARCHITECTURE.md)](ARCHITECTURE.md)
- 🔒 [دليل الأمان والحماية (SECURITY.md)](SECURITY.md)
- 🗄️ [قاعدة البيانات والترحيلات (DATABASE.md)](DATABASE.md)
- 🐳 [دليل الحاويات و Docker (DOCKER.md)](DOCKER.md)
- 🧪 [دليل الاختبارات الآلية (TESTING.md)](TESTING.md)
