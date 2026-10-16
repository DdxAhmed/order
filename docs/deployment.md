# النشر والاستعادة

يتطلب الإنتاج VPS محدثًا، Docker Compose، دومين يشير إلى الخادم، المنافذ 80 و443، وملف `.env` محمي بصلاحيات مالك الخدمة. لا تعرض PostgreSQL على الإنترنت.

## نطاق اختبار قبل DNS النهائي

تم تجهيز نطاق اختبار مؤقت يشير إلى الخادم: `https://109-71-252-240.sslip.io`. يستخدم هذا النطاق للتحقق من HTTPS، صفحة العميل، وتسجيل دخول الإدارة قبل تحويل `ordertrofy.store`. لا تعتمد عليه كعنوان إنتاج دائم؛ بعد تحديث DNS النهائي اضبط `CADDY_DOMAIN=ordertrofy.store www.ordertrofy.store` و`PUBLIC_BASE_URL=https://ordertrofy.store` في `.env` ثم أعد تشغيل `web` و`worker` و`caddy`.


## DNS قبل HTTPS

للنطاق `ordertrofy.store` يجب أن يكون سجل `A` للجذر (`@`) هو `109.71.252.240`، وأن يزال أي سجل `AAAA` لا يشير إلى IPv6 هذا السيرفر. يمكن جعل `www` سجل `CNAME` إلى الجذر. بعد انتشار DNS، يعيد Caddy إصدار الشهادة تلقائيًا عبر HTTP-01/TLS-ALPN-01. إذا ظهرت صفحة Hostinger Parked أو بقيت سجلات Cloudflare تشير إلى الاستضافة القديمة، فلن ينجح إصدار الشهادة.

1. انسخ السورس وملف `.env` إلى مسار مخصص للخدمة.
2. نفذ migrations يدويًا قبل تشغيل نسخة جديدة: `docker compose run --rm web alembic upgrade head`.
3. شغّل الخدمات عبر `docker compose up -d web worker caddy` وتحقق من `/health/ready` من داخل البيئة الموثوقة.
4. نفذ `python -m app.cli configure-mailbox` داخل خدمة `web` إذا كانت متغيرات `IMAP_*` موجودة في `.env`، ثم `python -m app.cli test-mailbox --label primary-imap`.
5. نفذ `python -m app.cli set-webhook` داخل خدمة `web` فقط إذا رغبت في Telegram الاختياري وبعد نجاح HTTPS.
5. راقب سجلات `web` و`worker` دون نسخ مخرجات تحمل أسرارًا.

بعد نجاح DNS يجب أن يفتح العنوانان `https://ordertrofy.store` و`https://www.ordertrofy.store` بشهادة صالحة. لا تغيّر سجلات MX أو TXT الخاصة بالبريد أثناء نقل الويب.

## Salla قبل الإنتاج

أضف متغيرات `SALLA_CLIENT_ID`, `SALLA_CLIENT_SECRET`, `SALLA_WEBHOOK_SECRET`, و`SALLA_APP_ID` إلى البيئة السرية في الخادم، ثم نفذ تثبيت التطبيق من رابط Salla الرسمي. اضبط Webhook HTTPS إلى `/api/integrations/salla/webhook` مع استراتيجية Signature، وفعل أحداث `app.store.authorize` وتحديثات الطلب المطلوبة من Partner Portal. تحقق من `/health/ready` ثم نفذ طلبًا تجريبيًا مصرحًا. إذا لم تتوفر هذه القيم أو التاجر لم يثبت التطبيق، تبقى الميزة غير متصلة ولا يجب إعلانها حية.

## إشعارات Salla عبر البريد

هذا المسار لا يحتاج تفعيل API Salla المباشر: اترك `SALLA_API_VERIFICATION_ENABLED=false` حتى تكتمل مراجعة التطبيق. قبل تشغيله حيًا، أنشئ صندوقًا ومجلدًا مخصصين لإشعارات الطلبات فقط، ثم أضفه من لوحة الإدارة كـ«إشعارات Salla فقط» واضبط قواعد الثقة من رسالة مصرح بها. لا تستخدم بريد مخزون أو بريدًا شخصيًا ولا تضف كلمات مرور أو توكنات إلى `.env` أو السجلات.

لبريد Outlook، سجل تطبيق Microsoft واحدًا يدعم الحسابات الشخصية واستخدم authority `consumers` وRedirect URI `/admin/mailboxes/oauth/callback`. خزّن `MICROSOFT_OAUTH_CLIENT_ID` و`MICROSOFT_OAUTH_CLIENT_SECRET` في `.env` المحمي، ثم نفذ الربط من لوحة الإدارة. لا تغيّر أو تستبدل أي قيمة سرية في الخادم إلا بعد حفظ القيمة المطابقة في بوابة Microsoft؛ أعد تشغيل `web` و`worker` بعد التغيير وتحقق من `/health/ready` وفحص اتصال صندوق البريد.

## نسخ احتياطي

اضبط `BACKUP_DIR` لمسار خارج المستودع ومشفر على مستوى التخزين ثم نفذ `deploy/backup-postgres.sh`. احتفظ بالملف و`.sha256` معًا. جرّب `restore-postgres.sh` على قاعدة اختبار جديدة فقط، ثم تحقق من readiness وسجل غير حساس قبل اعتماد النسخة.

## تراجع

احتفظ بصورة Docker السابقة ونسخة قاعدة حديثة. عند فشل الإصدار، أوقف web/worker الجديدين فقط، أعد الصورة السابقة، ولا تستعد قاعدة البيانات إلا إذا كانت migration قابلة للعكس وتم اختبار استعادتها على بيئة اختبار.
