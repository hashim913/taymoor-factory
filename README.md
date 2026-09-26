# Telegram Bot Factory V7

V7 يضيف طبقة الإنتاج والتوسع فوق V6.

## الإضافات

### ⚖️ Auto Worker Allocation
عند تشغيل بوت جديد، يتم اختيار Worker لديه أقل حمل ومساحة متاحة.

### 🔒 Redis Distributed Locks
يتم استخدام lock لكل Bot lifecycle لمنع Workerين من تشغيل نفس البوت في نفس الوقت.

### 🔁 Retries + Backoff
المهام الفاشلة تعاد تلقائياً مع exponential backoff.

### ☠️ Dead-Letter Queue
بعد تجاوز عدد المحاولات المحدد، تنتقل المهمة إلى:
`factory:dead`

### 📡 Worker Heartbeats
كل Worker يسجل heartbeat في Redis. إذا انتهى TTL يختفي من قائمة العمال المتاحين.

### 📊 Prometheus
المقاييس على:
`http://WORKER:9100/`

### 🗃️ Alembic
أضيف Alembic لإدارة migrations المستقبلية. قبل ترقية قاعدة بيانات إنتاجية موجودة، أنشئ migration حقيقية للفرق بين schema الحالي والجديد؛ لا تعتمد على baseline فارغ لترقية بيانات مهمة.

### 🌐 Nginx
إعداد Reverse Proxy موجود في `nginx.conf`.

## تشغيل Docker

```bash
cp .env.example .env
# ضع الأسرار والقيم الحقيقية
docker compose -f docker-compose.prod.yml up -d --build
```

**غيّر كلمة مرور PostgreSQL قبل التشغيل العام.**

## HTTPS

الإعداد الموجود يستمع على HTTP فقط. للإنتاج العام استخدم Caddy أو Nginx + شهادة TLS، ثم اجعل:
```env
WEB_BASE_URL=https://your-domain.com
```

Telegram Webhooks تحتاج عنوان HTTPS عام.

## Redis

لا تعرض منفذ Redis للإنترنت. يجب أن يكون داخلياً فقط.

## Monitoring

Prometheus يمكنه scrape:
`http://worker-1:9100/`

مثال:
```yaml
scrape_configs:
  - job_name: bot_factory_workers
    static_configs:
      - targets: ["worker-1:9100", "worker-2:9100"]
```

## Dead-Letter Queue

لمراجعة المهام الفاشلة:
```bash
redis-cli LRANGE factory:dead 0 -1
```

لا تعيد تشغيل مهام DLQ عشوائياً؛ تحقق من سبب الفشل أولاً.

## Migration

بعد تعديل models:
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## ملاحظات مهمة

- لا تسجل Bot Tokens في logs.
- لا تشارك `.env`.
- استخدم PostgreSQL في الإنتاج.
- احتفظ بنسخ احتياطية.
- شغّل أكثر من Worker فقط عندما تكون Redis/PostgreSQL والـrouting جاهزة.
- Webhook gateway يحتاج بنية routing متوافقة مع Worker ownership. V7 يوفر registry/ownership وطبقة API، لكن deployment النهائي يجب أن يوجه Webhook إلى الـWorker المسؤول أو gateway مركزي يرسل update للـWorker الصحيح.
- الدفع الحقيقي ما زال يحتاج adapter لمزود الدفع والتحقق من signature.

## الخطوة الثامنة المقترحة

- لوحة مراقبة كاملة للـWorkers والـQueues.
- معالجة DLQ من لوحة الإدارة.
- Prometheus + Grafana جاهزان بـdocker compose.
- TLS تلقائي عبر Caddy.
- Stripe/بوابة دفع حقيقية مع webhooks موقعة.
- نظام تجديد وإيقاف الاشتراك تلقائياً.
- اختبارات automated وCI/CD.


## V8 additions
- Admin API and lightweight Arabic admin dashboard.
- Dead Letter Queue inspection, retry and delete actions.
- Stronger Redis distributed locks with ownership tokens.
- Prometheus + Grafana monitoring stack.
- Caddy reverse proxy with automatic HTTPS when `DOMAIN` points to the server.
- Fixed webhook payload format to preserve `bot_id` alongside the Telegram update.
- Pytest test suite and GitHub Actions CI.
- `docker-compose.v8.yml` provides the complete monitoring/HTTPS stack.

### Start V8
1. Copy `.env.example` to `.env` and set `MAIN_BOT_TOKEN`, `ADMIN_IDS`, `DOMAIN`, database and Redis secrets.
2. Point the DNS A/AAAA record for `DOMAIN` to the server.
3. Run:
   `docker compose -f docker-compose.v8.yml up -d --build`
4. Run migrations before production traffic:
   `alembic upgrade head`
5. Grafana is internal by default; expose it only through a protected reverse proxy if needed.

### Important
V8 improves the production topology but payment-provider integration still requires a real provider adapter and signed webhook verification. Telegram webhook routing should be tested end-to-end with the exact deployment topology before production use.


## V9 — Manual Payments & Subscriptions
- Free plan: 90 days.
- 3 months: $15.
- 1 year: $40.
- Zain Cash wallet configured as `+9647881313006`.
- Payment orders have unique IDs and manual receipt/reference review.
- Admin approval activates/extends the subscription and queues bot start.
- Expired subscriptions are stopped by a background worker.
- The architecture keeps payment provider logic isolated so ZainCash API can be enabled later without changing subscription logic.

### ZainCash API upgrade
ZainCash currently documents a merchant Payment Gateway v2 with OAuth2 credentials, transaction initialization, inquiry and webhooks. Production credentials are issued after merchant onboarding. Therefore V9 deliberately does not pretend that a personal wallet number is an API integration.


## V10 — Payment UI & Admin Review
- `/subscribe` Telegram flow for plan selection.
- Zain Cash wallet payment instructions.
- Unique payment order IDs.
- Transaction reference submission.
- Admin payment table with approve/reject actions.
- Approved payments activate/extend the bot subscription.
- Free 90-day activation helper.
- Renewal prompt components.
- Payment and subscription modules are isolated for later ZainCash API integration.


## الاشتراك الإجباري بالقنوات

يمكن إجبار المستخدم على الاشتراك في قنوات محددة قبل استخدام المصنع. ضع في `.env`:

`REQUIRED_CHANNELS=@channel1|https://t.me/channel1|القناة الأولى,@channel2|https://t.me/channel2|القناة الثانية`

يجب أن يكون البوت مشرفاً في القنوات حتى يستطيع Telegram التحقق من عضوية المستخدم. بعد الاشتراك يظهر زر «تحقّق من الاشتراك».
