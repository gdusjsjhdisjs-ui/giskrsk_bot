# ГИС Красноярье — Technical Architecture for Telegram Bot

> Version: 1.0 (2026-07-10)
> Target AI: Grok 4.5 / Any LLM coder
> Purpose: Generate production-ready code for the Telegram bot

---

## 0. KEY LINKS & REFERENCE MATERIALS

### Live Services & Tools
| Service / Tool | URL / Description | Credentials / Notes |
|---|---|---|
| **NextGIS Web (main)** | https://zimin-maplive0000.nextgis.com | Login: Yaroslav_000, Pass: Zimin0711+ |
| **Web Map (layers)** | https://zimin-maplive0000.nextgis.com/resource/127/display?panel=layers | The actual working map with PZZ zones |
| **NextGIS Connect** | Плагин QGIS для загрузки слоёв в NextGIS Web | Установлен на ПК Ярослава |
| **Telegram Bot** | https://https://https://t.me/giskrsk_bot — @giskrsk_bot | Создан у BotFather, токен готов |
| **OpenClaw (AI ассистент)** | Локальный AI-агент (исследования, контент, TTS, суб-агенты) | ПК Ярослава, порт 9878 |
| **YooKassa** | https://yookassa.ru | Не зарегистрирован |
| **VPS** | Aeza / Beget | Не куплен |

### Reference Documents (must read!)
| Document | Path / URL | Why |
|---|---|---|
| **Bot architecture (code examples)** | `obsidian/Документы/WebGIS-проект/ПЛАН_Telegram_бота.md` | **Main spec: 10 tables, all endpoints, user flows, tariff plans, payment flow** |
| **SellerGPT chat (Claude code)** | `obsidian/Документы/WebGIS-проект/бота_архитектура_от_SellerGPT.md` | **GPT-5.4 + Claude Sonnet: architecture decisions, code sketches for all services** |
| **Brainstorm (40+ ideas)** | `obsidian/Документы/WebGIS-проект/мозговой_штурм_Claude.md` | Future features: ZOUIT, parcel search, auctions |
| **Full API analysis** | `obsidian/Документы/WebGIS-проект/nextgis_api_full_analysis.md` | 670+ lines: all NextGIS endpoints with examples |
| **OpenAPI spec (readable)** | `obsidian/Документы/WebGIS-проект/nextgis_api_openapi_spec.md` | All NextGIS endpoints in human format |
| **OpenAPI raw JSON** | `obsidian/Документы/WebGIS-проект/Исследования/NextGIS_OpenAPI_raw.json` | Raw OpenAPI spec v285 |
| **Official NextGIS docs** | https://docs.nextgis.com | Official API docs |
| **NextGIS Python SDK** | https://github.com/nextgis/ngw_external_api_python | Official Python library |
| **Telegram Bot API docs** | https://core.telegram.org/bots/api | Official Telegram API docs (aiogram uses this under hood) |
| **Чат SellerGPT с кодом** | https://app.sellergpt.ru/dashboard/chats/6a48f1a3bdeabb282de8135c | **Код от Claude: 5 итераций, модели SQLAlchemy, сервисы, YooKassa, PDF, Docker** |

### 🌐 NextGIS API Endpoints used by Bot (CRITICAL for AI coder)

The bot communicates with NextGIS Web at `https://zimin-maplive0000.nextgis.com` via these REST endpoints:

| Scenario | Endpoint | Method | Purpose |
|---|---|---|---|
| **Search by cadnum** | `/api/resource/{id}/feature/?ilike=cadnum=...` | GET | Find parcel by cadastral number |
| **Search by coordinates** | `/api/feature_layer/identify` | POST | Identify PZZ zone at lat/lon point |
| **Export layer** | `/api/resource/{id}/geojson` | GET | Download full layer as GeoJSON |
| **MVT tiles (map)** | `/api/component/feature_layer/mvt` | GET | Map tiles for Mini App |
| **Check layer version** | `/api/resource/{id}/feature/version/` | GET | Get current version of PZZ data |
| **Check changes** | `/api/resource/{id}/feature/changes/check` | GET | Check if PZZ data changed since version |
| **Fetch changes** | `/api/resource/{id}/feature/changes/fetch` | GET | Get actual changed features |
| **Create user** | `/api/component/auth/register` | POST | Self-register new users (requires config) |
| **Add to group** | `/api/component/auth/group/{id}` | PUT | Assign user to tariff group |
| **Get user info** | `/api/component/auth/current_user` | GET | Verify current user's auth status |
| **LLM filter** | `/api/resource/{id}/filter/generate` | POST | AI-powered parcel filtering |
| **Print PDF** | `/api/component/{id}/webmap/print` | POST | Generate map PDF for reports |

**Auth:** Bearer token in Authorization header. Token stored in `.env` as `NEXTGIS_BEARER_TOKEN`.
**Resource IDs:** ID of parcel layer and PZZ layer go into `.env` as `NEXTGIS_PARCELS_RESOURCE_ID` and `NEXTGIS_PZZ_RESOURCE_ID`.
**Retry:** exponential backoff (1s→2s→4s→8s), max 3 attempts.

### 💳 YooKassa API (payment processing)
| Action | Endpoint | Method |
|---|---|---|
| Create payment | `https://api.yookassa.ru/v3/payments` | POST |
| Get payment info | `https://api.yookassa.ru/v3/payments/{id}` | GET |

**Auth:** Basic auth (shop_id:secret_key). **Idempotency:** `Idempotence-Key: sha256(user+plan+timestamp)` header.
**Webhook:** YooKassa POSTs to `{APP_BASE_URL}/api/webhooks/yookassa` when payment status changes.

### 📍 Telegram Bot API (aiogram)
| Action | Method | Library Call |
|---|---|---|
| Send message | `sendMessage` | `message.answer()` |
| Send document | `sendDocument` | `message.answer_document()` |
| Send inline keyboard | — | `InlineKeyboardBuilder` |
| Set webhook | `setWebhook` | aiogram setup |
| Answer callback | `answerCallbackQuery` | `callback.answer()` |

Bot name: **@giskrsk_bot** | Bot link: **https://https://https://t.me/giskrsk_bot**

### Location of this project
- **Root folder:** `C:\Users\Egor-\Desktop\ГИС Красноярск проект\`
- **Bot folder:** `C:\Users\Egor-\Desktop\ГИС Красноярск проект\Телеграм бот\`
- **Land data folder:** `C:\Users\Egor-\Desktop\земля\`
- **Obsidian vault:** `D:\Джарвис\workspace\obsidian\`
- **Workspace:** `D:\Джарвис\workspace\`

---

## 1. TECHNOLOGY STACK

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Bot framework | **aiogram** | 3.x | Commands, FSM, keyboards |
| Backend | **FastAPI** | 0.115+ | API for bot, webhooks, admin |
| Database | **PostgreSQL** | 16 | Users, payments, subscriptions, tracking |
| ORM | **SQLAlchemy** | 2.0 async | Async ORM with asyncpg |
| Migrations | **Alembic** | 1.13+ | Schema migrations |
| Cache / Queue | **Redis** | 7 | Caching, rate limits, ARQ queue |
| Background tasks | **ARQ** | 0.6+ | Batch processing, monitoring, notifications |
| HTTP client | **httpx** | 0.27+ | NextGIS API, YooKassa API |
| PDF | **WeasyPrint** | 62+ | PDF report generation |
| Templating | **Jinja2** | 3.1+ | HTML templates for PDF |
| Containerization | **Docker Compose** | 3.8+ | Deployment |
| WSGI server | **Uvicorn** | 0.30+ | Running FastAPI |
| Reverse proxy | **Nginx** | latest | SSL termination, reverse proxy |

---

## 2. PROJECT STRUCTURE

All files go to: `C:\Users\Egor-\Desktop\ГИС Красноярск проект\Телеграм бот\`

```
ГИС Красноярск проект\Телеграм бот\
├── docker-compose.yml              # PostgreSQL + Redis + app + worker
├── Dockerfile                       # Multi-stage build
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
├── .gitignore
│
├── alembic.ini                      # Alembic configuration
├── alembic/
│   ├── env.py                       # Alembic env (async)
│   └── versions/                    # Migration scripts
│       └── 001_initial.py
│
├── app/
│   ├── __init__.py
│   │
│   ├── main.py                      # Entry point: FastAPI + aiogram lifespan
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic BaseSettings (load .env)
│   │   ├── enums.py                 # All enums: PaymentStatus, SubscriptionStatus, PlanCode, BatchStatus
│   │   └── exceptions.py            # Custom exceptions
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                  # DeclarativeBase
│   │   ├── models.py                # SQLAlchemy models (10 tables)
│   │   └── session.py               # AsyncSession factory (async_sessionmaker)
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user_repo.py             # CRUD: users, rate limits
│   │   ├── payment_repo.py          # Payments + idempotency
│   │   ├── webhook_event_repo.py    # Webhook events (dedup)
│   │   ├── subscription_repo.py     # Subscription CRUD + expiry check
│   │   ├── tracked_object_repo.py   # Tracked parcels CRUD
│   │   ├── change_event_repo.py     # Change history
│   │   ├── notification_repo.py     # Notifications
│   │   ├── batch_job_repo.py        # Batch jobs
│   │   ├── batch_item_repo.py       # Batch items
│   │   └── layer_sync_repo.py       # Layer sync state
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── nextgis.py               # NextGISClient (httpx + retry)
│   │   ├── yookassa.py              # YooKassaClient (payment creation)
│   │   ├── redis_cache.py           # RedisCache (get/set/delete with TTL)
│   │   └── telegram.py              # TelegramClient (send messages, files)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── parcel_service.py        # Search parcel by cadnum/coordinates + cache
│   │   ├── payment_service.py       # Create payment, check status
│   │   ├── webhook_processor.py     # Process YooKassa webhook (idempotent)
│   │   ├── subscription_service.py  # Activate/renew/expire/check subscription
│   │   ├── batch_service.py         # Batch validation, progress, Excel generation
│   │   ├── notification_service.py  # Send pending notifications
│   │   ├── monitor_service.py       # Check PZZ changes for tracked objects
│   │   └── pdf_service.py           # Generate PDF report (WeasyPrint + Jinja2)
│   │
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── setup.py                 # Initialize bot + dispatcher
│   │   ├── states.py                # FSM states (ParcelInput, BatchUpload, etc.)
│   │   ├── keyboards.py             # All keyboard builders
│   │   ├── keyboards_data.py        # CallbackData classes
│   │   ├── filters.py               # Custom filters (is_admin, has_subscription)
│   │   │
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── start.py             # /start, main menu
│   │   │   ├── parcel.py            # Check parcel (cadnum + geo)
│   │   │   ├── tariffs.py           # Show tariffs
│   │   │   ├── payment.py           # Purchase flow
│   │   │   ├── subscription.py      # Manage subscriptions
│   │   │   ├── tracking.py          # Manage tracked objects
│   │   │   ├── batch.py             # Batch upload + results
│   │   │   ├── profile.py           # User profile
│   │   │   ├── help.py              # Help command
│   │   │   └── admin.py             # /stats, /users, /broadcast
│   │   │
│   │   └── middlewares/
│   │       ├── __init__.py
│   │       ├── services.py          # Inject services into handlers
│   │       ├── limits.py            # Rate limit check
│   │       └── logging.py           # Request logging
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhooks.py              # POST /api/webhooks/yookassa
│   │   ├── health.py                # GET /health
│   │   └── admin_api.py             # GET /admin/stats, /admin/users, etc.
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── tasks.py                 # ARQ tasks (batch_process, monitor_check, notify)
│   │   └── scheduler.py             # Background scheduler (cron)
│   │
│   └── templates/
│       ├── __init__.py
│       └── parcel_report.html       # Jinja2 template for PDF
│
├── tests/
│   ├── __init__.py
│   ├── test_parcel_service.py
│   ├── test_payment_service.py
│   ├── test_batch_service.py
│   ├── test_handlers.py
│   └── conftest.py                  # Fixtures: mock DB, mock NextGIS, mock Redis
│
├── ТЗ_ПОЛНОЕ_ОПИСАНИЕ.md           # Full project description (Russian, for human + AI)
└── ТЕХНИЧЕСКАЯ_АРХИТЕКТУРА.md      # This file (technical reference for AI coder)
```

---

## 3. DATABASE SCHEMA (10 tables)

### 3.1. users
```sql
CREATE TABLE users (
    telegram_id       BIGINT PRIMARY KEY,
    username          VARCHAR(128),
    full_name         VARCHAR(256),
    role              VARCHAR(32) DEFAULT 'free',  -- free | user | admin
    daily_requests_used INT DEFAULT 0,
    daily_requests_date DATE DEFAULT CURRENT_DATE,
    is_blocked        BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ DEFAULT NOW(),
    registered_at     TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2. payments
```sql
CREATE TABLE payments (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id       BIGINT NOT NULL REFERENCES users(telegram_id),
    provider          VARCHAR(32) NOT NULL DEFAULT 'yookassa',
    plan_code         VARCHAR(64) NOT NULL,  -- basic_30d | pro_30d | pro_90d | year
    amount            DECIMAL(12,2) NOT NULL,
    currency          VARCHAR(8) DEFAULT 'RUB',
    status            VARCHAR(32) NOT NULL DEFAULT 'pending',  -- pending | succeeded | canceled
    idempotency_key   VARCHAR(128) UNIQUE NOT NULL,
    external_payment_id VARCHAR(128) UNIQUE,
    confirmation_url  TEXT,
    provider_payload  JSONB,
    paid_at           TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_payments_telegram_id ON payments(telegram_id);
CREATE INDEX idx_payments_status ON payments(status);
```

### 3.3. payment_webhook_events
```sql
CREATE TABLE payment_webhook_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider            VARCHAR(32) NOT NULL DEFAULT 'yookassa',
    external_event_id   VARCHAR(128),
    external_payment_id VARCHAR(128),
    event_type          VARCHAR(128),       -- payment.succeeded | payment.canceled
    event_hash          VARCHAR(128) NOT NULL,  -- SHA256(raw_body)
    payload             JSONB,
    processing_status   VARCHAR(32) DEFAULT 'received',  -- received | processed | ignored | orphan | failed
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    
    UNIQUE(provider, event_hash)  -- IDEMPOTENCY: prevents duplicate processing
);

CREATE INDEX idx_webhook_events_payment_id ON payment_webhook_events(external_payment_id);
```

### 3.4. subscriptions
```sql
CREATE TABLE subscriptions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id    BIGINT NOT NULL REFERENCES users(telegram_id),
    plan_code      VARCHAR(64) NOT NULL,  -- basic_30d | pro_30d | pro_90d | year
    status         VARCHAR(32) NOT NULL DEFAULT 'active',  -- active | expired | canceled
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ NOT NULL,
    payment_id     UUID REFERENCES payments(id),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_telegram_id ON subscriptions(telegram_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_expires ON subscriptions(expires_at) WHERE status = 'active';
```

### 3.5. tracked_objects
```sql
CREATE TABLE tracked_objects (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id       BIGINT NOT NULL REFERENCES users(telegram_id),
    cadastral_number  VARCHAR(64) NOT NULL,
    active            BOOLEAN DEFAULT TRUE,
    last_snapshot_hash VARCHAR(128),     -- MD5 of key fields for change detection
    last_snapshot_payload JSONB,          -- Full last known data
    last_checked_at   TIMESTAMPTZ,
    last_notified_at  TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tracked_telegram_id ON tracked_objects(telegram_id);
CREATE INDEX idx_tracked_cadnum ON tracked_objects(cadastral_number);
CREATE UNIQUE INDEX idx_tracked_unique ON tracked_objects(telegram_id, cadastral_number) WHERE active = TRUE;
```

### 3.6. change_events
```sql
CREATE TABLE change_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracked_object_id UUID NOT NULL REFERENCES tracked_objects(id),
    event_type        VARCHAR(64) NOT NULL,  -- zone_changed | vri_changed | cad_value_changed | multiple
    old_values        JSONB,
    new_values        JSONB,
    detected_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_change_events_tracked ON change_events(tracked_object_id);
```

### 3.7. notifications
```sql
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id     BIGINT NOT NULL,
    change_event_id UUID REFERENCES change_events(id),
    status          VARCHAR(32) DEFAULT 'pending',  -- pending | sent | failed
    message_text    TEXT,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notifications_pending ON notifications(status) WHERE status = 'pending';
CREATE INDEX idx_notifications_telegram ON notifications(telegram_id);
```

### 3.8. batch_jobs
```sql
CREATE TABLE batch_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id         BIGINT NOT NULL REFERENCES users(telegram_id),
    status              VARCHAR(32) NOT NULL DEFAULT 'uploaded',  -- uploaded | queued | processing | completed | failed
    source_file_name    VARCHAR(256),
    total_rows          INT DEFAULT 0,
    processed_rows      INT DEFAULT 0,
    success_rows        INT DEFAULT 0,
    error_rows          INT DEFAULT 0,
    result_excel_path   TEXT,       -- Local path to generated Excel
    result_xlsx_bytes   BYTEA,      -- Store file in DB directly for Telegram
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ
);

CREATE INDEX idx_batch_telegram_id ON batch_jobs(telegram_id);
CREATE INDEX idx_batch_status ON batch_jobs(status);
```

### 3.9. batch_items
```sql
CREATE TABLE batch_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_job_id        UUID NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
    row_number          INT NOT NULL,
    input_value         TEXT NOT NULL,
    normalized_cadnum   VARCHAR(64),
    status              VARCHAR(32) NOT NULL,  -- ok | invalid_format | not_found | api_error
    error_message       TEXT,
    result_json         JSONB,       -- Full response from NextGIS
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_batch_items_job ON batch_items(batch_job_id);
```

### 3.10. layer_sync_state
```sql
CREATE TABLE layer_sync_state (
    layer_key           VARCHAR(128) PRIMARY KEY,  -- e.g. 'enriched_parcels', 'pzz_zones'
    ngw_resource_id     INT UNIQUE,
    last_seen_version   INT DEFAULT 0,
    last_checked_at     TIMESTAMPTZ,
    last_full_sync_at   TIMESTAMPTZ,
    status              VARCHAR(32) DEFAULT 'active',  -- active | error
    meta                JSONB
);
```

---

## 4. BACKEND SERVICES

### 4.1. ParcelService
- `search_by_cadnum(cadnum: str) -> ParcelDTO` — validates format, checks Redis cache → NextGIS → cache result
- `search_by_coordinates(lat: float, lon: float) -> list[ParcelDTO]` — identify parcels at point
- `check_limits(telegram_id: int) -> bool` — check daily request limit based on plan

### 4.2. PaymentService
- `create_payment(telegram_id, plan_code) -> dict` — POST to YooKassa, save payment with idempotency_key
- `check_payment_status(external_payment_id) -> str` — GET from YooKassa

### 4.3. WebhookProcessor
- `process_webhook(raw_body: bytes) -> dict` — parse JSON, compute event_hash=SHA256(raw_body)
- Insert into payment_webhook_events — if UNIQUE violation → return 200 (duplicate, already processed)
- If payment.succeeded: find payment by external_payment_id → set status=succeeded → create subscription
- Orphan handling: if external_payment_id not found in payments → log as orphan

### 4.4. SubscriptionService
- `activate_subscription(telegram_id, plan_code, payment_id) -> Subscription` — create active subscription
- `get_active_subscription(telegram_id) -> Subscription | None` — check if user has active sub
- `get_plan_limits(plan_code) -> PlanLimits` — return DailyLimit, BatchLimit, TrackLimit
- `check_expired_subscriptions()` — cron: find expired → set status=expired
- `get_remaining_days(subscription) -> int`

### 4.5. BatchService
- `validate_csv(content: str) -> list[str]` — parse lines, validate cadnum format
- `process_batch_job(job_id: UUID)` — ARQ task: iterate items, call NextGIS for each
- `generate_excel(job_id: UUID) -> bytes` — openpyxl: create XLSX with all results
- `get_progress(job_id: UUID) -> dict` — return processed/total/errors for polling

### 4.6. PdfService
- `generate_parcel_report(parcel_data: ParcelDTO) -> bytes` — Jinja2 template → WeasyPrint → PDF bytes
- Template uses DejaVu Sans font for Cyrillic support
- Includes: cadnum, zone code+name, VRI, area, cadastral value, restrictions, map screenshot (base64 from NextGIS print API)

### 4.7. MonitorService (change detection)
- `check_all_tracked_objects()` — ARQ cron task
- For each tracked object: get current data from NextGIS → compare hash with last_snapshot_hash
- If changed: create ChangeEvent + Notification(pending), update tracked_object
- `sync_layer(layer_key)` — check NextGIS feature versions, detect changes 

### 4.8. NotificationService
- `send_pending_notifications()` — ARQ cron task
- Fetches pending notifications → sends via Telegram bot → marks as sent
- Grouping: one user may have multiple notifications, send as single message

---

## 5. TELEGRAM BOT HANDLERS

### 5.1. Handler routing

| Handler | Trigger | State |
|---------|---------|-------|
| `start.py` | `/start`, `/help` | — |
| `parcel.py` | Button "🔍 Проверить участок" | `ParcelInput` state |
| `parcel.py` | `/check 24:...` (inline) | — |
| `parcel.py` | `Message.location` (geo) | — |
| `tariffs.py` | Button "💳 Тарифы", `/tariffs` | — |
| `payment.py` | Callback `buy_plan:basic_30d` etc. | — |
| `payment.py` | Callback `pay:{payment_id}` | — |
| `subscription.py` | Button "📋 Мои подписки", `/subscribe` | — |
| `subscription.py` | Callback `manage_tracking` | — |
| `tracking.py` | Callback `track:{cadnum}` | — |
| `tracking.py` | Callback `untrack:{track_id}` | — |
| `batch.py` | Button "📤 Пакетная проверка" | `BatchUpload` state |
| `batch.py` | Document (CSV) during BatchUpload | — |
| `batch.py` | Callback `batch_status:{job_id}` | — |
| `profile.py` | Button "👤 Профиль", `/profile` | — |
| `admin.py` | `/stats`, `/users`, `/broadcast` (admin only) | — |

### 5.2. Keyboard layouts

**Main menu (ReplyKeyboardMarkup, always present after /start):**
```
Row 1: [🔍 Проверить участок] [💳 Тарифы]
Row 2: [📋 Мои подписки] [📤 Пакетная проверка]
Row 3: [👤 Профиль] [❓ Помощь]
```
- `resize_keyboard=True`
- `input_field_placeholder="Напишите кадастровый номер или выберите действие"`

**Parcel result (InlineKeyboardMarkup):**
```
Row 1: [🗺️ Открыть на карте] (url)
Row 2: [📄 PDF-справка] (callback) — only if paid
Row 3: [🔔 Отслеживать] (callback) — only if paid
Row 4: [🔍 Ещё участок] [ ↩️ Назад] (callbacks)
```

### 5.3. FSM States

```python
class ParcelStates(StatesGroup):
    waiting_for_input = State()       # Waiting for cadnum or geo
    waiting_for_confirmation = State()

class BatchStates(StatesGroup):
    waiting_for_file = State()        # Waiting for CSV upload
    waiting_for_confirmation = State()
```

---

## 6. FASTAPI ENDPOINTS

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/webhooks/yookassa` | YooKassa payment notifications |
| GET | `/health` | Healthcheck (DB + Redis + NextGIS status) |
| GET | `/admin/stats` | DAU, MAU, revenue, users count |
| GET | `/admin/users` | User list with subscriptions |
| GET | `/admin/users/{id}` | User details |
| POST | `/admin/users/{id}/block` | Block/unblock user |

---

## 7. EXTERNAL API INTEGRATIONS

### 7.1. NextGIS Web API
- **Base URL:** `https://zimin-maplive0000.nextgis.com`
- **Auth:** Bearer token in Authorization header
- **Key endpoints:**

| Scenario | Endpoint | Method |
|----------|----------|--------|
| Search by cadnum | `/api/resource/{id}/feature/?ilike=...` | GET |
| Identify by point | `/api/feature_layer/identify` | POST |
| Export GeoJSON | `/api/resource/{id}/geojson` | GET |
| Feature versions | `/api/resource/{id}/feature/version/` | GET |
| Check changes | `/api/resource/{id}/feature/changes/check` | GET |
| Fetch changes | `/api/resource/{id}/feature/changes/fetch` | GET |
| Create user | `/api/component/auth/register` | POST |
| Add to group | `/api/component/auth/group/{id}` | PUT |

- **Retry policy:** tenacity with exponential backoff (1s→2s→4s→8s, max 3 attempts)
- **Timeouts:** connect=10s, read=30s
- **Resource IDs:** To be configured via env vars (PARCELS_RESOURCE_ID, PZZ_RESOURCE_ID)

### 7.2. YooKassa API
- **Base URL:** `https://api.yookassa.ru/v3`
- **Auth:** Basic auth (shop_id:secret_key)
- **Key endpoint:** `POST /payments` with Idempotence-Key header
- **Webhook:** YooKassa POSTs to `{APP_BASE_URL}/api/webhooks/yookassa`

**Create payment request:**
```json
{
  "amount": {"value": "2990.00", "currency": "RUB"},
  "confirmation": {
    "type": "redirect",
    "return_url": "https://https://https://t.me/giskrsk_bot"
  },
  "description": "Подписка Pro на 30 дней — ГИС Красноярье",
  "metadata": {
    "telegram_id": 1368146064,
    "plan_code": "pro_30d"
  }
}
```

### 7.3. Telegram Bot API
- **Token:** from @BotFather (configured in .env)
- **Webhook mode:** `https://api.telegram.org/bot{TOKEN}/setWebhook?url={APP_BASE_URL}/webhook`
- **Library:** aiogram 3 handles all API calls internally

---

## 8. CODE CONVENTIONS

### 8.1. Python style
- Python 3.12+ with type hints everywhere
- Async/await for all I/O operations
- F-strings for formatting
- All services use dependency injection (no global state)
- Pydantic v2 models for DTOs and validation

### 8.2. Database
- All DB operations via repositories (no raw SQL in services)
- AsyncSession from SQLAlchemy 2.0
- Session per request pattern (session factory → service → repository)
- Use selectinload for eager loading when needed

### 8.3. Error handling
- Custom `AppException` hierarchy in `core/exceptions.py`
- All service methods return typed results, not raise for expected failures
- NextGIS timeouts → cached data fallback + stale data marker
- Webhook processor: always return 200 (YooKassa retries on non-200)

### 8.4. Logging
- Use standard `logging` module with structured format
- Include request_id (UUID) in every handler call
- Log cache hits/misses for performance monitoring

---

## 9. CONFIGURATION (.env)

```ini
# Telegram
TELEGRAM_BOT_TOKEN=8768777524:AAGTJ3z1BTWVI3R0MIZHDnFdbf6IDJauaOw  # @giskrsk_bot actual token (10.07.2026)

# PostgreSQL
POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/webgis_bot

# Redis
REDIS_URL=redis://localhost:6379/0

# NextGIS
NEXTGIS_BASE_URL=https://zimin-maplive0000.nextgis.com
NEXTGIS_BEARER_TOKEN=your_token_here
NEXTGIS_PARCELS_RESOURCE_ID=51
NEXTGIS_PZZ_RESOURCE_ID=50

# YooKassa
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
YOOKASSA_RETURN_URL=https://https://https://t.me/giskrsk_bot

# App
APP_BASE_URL=http://localhost:8000
REDIS_CACHE_TTL_SEC=3600
FREE_DAILY_LIMIT=3
WEBHOOK_PATH=/api/webhooks/yookassa
```

---

## 10. DATABASE MIGRATIONS (Alembic)

```python
# alembic/env.py — async configuration
from app.db.base import DeclarativeBase
from app.db.models import *  # noqa: F401,F403 — import all models for autogenerate

target_metadata = DeclarativeBase.metadata

async def run_migrations_online():
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

Generate initial migration:
```
alembic -c alembic.ini revision --autogenerate -m "initial"
alembic -c alembic.ini upgrade head
```

---

## 11. DOCKER COMPOSE

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: webgis_bot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    restart: unless-stopped

  app:
    build: .
    env_file: .env
    depends_on: [postgres, redis]
    ports: ["8000:8000"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    restart: unless-stopped

  worker:
    build: .
    env_file: .env
    depends_on: [postgres, redis]
    command: python -m app.workers.tasks
    restart: unless-stopped

volumes:
  pg_data:
```

---

## 12. KEY FLOWS (DIAGRAMS)

### 12.1. Parcel Check Flow
```
User → /start → Main Menu → "🔍 Проверить участок"
  → Bot asks for cadnum or geo
  → User sends cadnum "24:11:0330102:814"
  → Handler validates format (regex: \d{2}:\d{2}:\d{7}:\d{1,4})
  → Check daily limit → if exceeded → suggest upgrade
  → ParcelService.search_by_cadnum(cadnum):
    → Check Redis cache (key: "parcel:{cadnum}")
    → Cache MISS → NextGIS API call (GET /resource/{id}/feature/?ilike=...)
    → Parse response → ParcelDTO
    → Store in Redis TTL=3600
  → Return result to user with inline keyboards
```

### 12.2. Payment Flow
```
User → "💳 Тарифы" → Inline: "Купить Pro"
  → PaymentService.create_payment(telegram_id, pro_30d)
  → Generate idempotency_key = sha256(f"{telegram_id}:pro_30d:{timestamp}")
  → POST to YooKassa with Idempotence-Key header
  → Save Payment(status=pending) in DB
  → Send message to user with InlineButton(url=confirmation_url) "💳 Оплатить 2990₽"
  
  → User pays → YooKassa → POST /api/webhooks/yookassa
  
Webhook flow:
  → Compute event_hash = sha256(raw_body)
  → TRY INSERT INTO payment_webhook_events (provider, event_hash, payload...)
  → IF IntegrityError (duplicate) → return 200 (already processed)
  → IF event_type = payment.succeeded:
    → Find payment by external_payment_id
    → IF not found → log as orphan → return 200
    → UPDATE payment SET status=succeeded, paid_at=NOW()
    → INSERT subscription (status=active, expires_at=NOW()+30d)
    → UPDATE webhook_event SET processing_status=processed
  → Send notification to user: "✅ Подписка Pro активирована до 10.08.2026"
  → Return 200 OK
```

### 12.3. Batch Processing Flow
```
User → "📤 Пакетная проверка"
  → Check subscription → batch limit (only paid plans)
  → FSM: BatchStates.waiting_for_file
  → User sends CSV document
  → Validate: parse lines, count rows, check limit
  → Create batch_job(status=uploaded)
  → Enqueue ARQ task: batch_process(job_id)
  → Return: "Файл принят в обработку" + progress message
  → User polls via "🔄 Статус" callback
  
ARQ worker:
  → batch_job → status=processing
  → For each line:
    → Validate format
    → If ok → ParcelService.search_by_cadnum(normalized)
    → Create batch_item with status/result
    → Update progress every 25%
  → Generate Excel via openpyxl
  → batch_job → status=completed
  → Send file to user + summary message
```

---

## 13. PDF TEMPLATE (Jinja2)

```html
<!-- app/templates/parcel_report.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @page { size: A4; margin: 2cm; }
    body { font-family: 'DejaVu Sans', sans-serif; font-size: 11pt; }
    .header { text-align: center; margin-bottom: 20px; }
    .header h1 { font-size: 18pt; color: #2d5a27; }
    .info-table { width: 100%; border-collapse: collapse; }
    .info-table td { padding: 6px 10px; border: 1px solid #ccc; }
    .info-table td:first-child { font-weight: bold; width: 40%; }
    .disclaimer { margin-top: 30px; font-size: 8pt; color: #666; }
    .map-image { text-align: center; margin: 20px 0; }
    .map-image img { max-width: 100%; max-height: 400px; }
  </style>
</head>
<body>
  <div class="header">
    <h1>ГИС Красноярье</h1>
    <p>Справка по земельному участку</p>
    <p>Дата: {{ report_date }}</p>
  </div>
  
  <table class="info-table">
    <tr><td>Кадастровый номер</td><td>{{ cadnum }}</td></tr>
    <tr><td>Зона ПЗЗ</td><td>{{ zone_code }} — {{ zone_name }}</td></tr>
    <tr><td>ВРИ</td><td>{{ vri }}</td></tr>
    <tr><td>Площадь</td><td>{{ area }} м²</td></tr>
    <tr><td>Кадастровая стоимость</td><td>{{ cad_value }} ₽</td></tr>
  </table>
  
  <div class="disclaimer">
    <p>⚠️ Данные не являются официальной выпиской из ЕГРН.</p>
    <p>Источник: ГИСОГД, НСПД. Актуально на {{ data_date }}.</p>
    <p>© ГИС Красноярье, 2026</p>
  </div>
</body>
</html>
```

---

## 14. ERROR HANDLING MATRIX

| Error | Where | Response |
|-------|-------|----------|
| Invalid cadnum format | Parcel handler | "Неверный формат. Правильный: 24:11:0330102:814" |
| Daily limit exceeded | Limits middleware | "Дневной лимит исчерпан. Купите подписку" + tariffs button |
| NextGIS timeout | ParcelService | "Сервис временно недоступен. Используются данные от ДД.ММ.ГГГГ" + cached data |
| NextGIS 401 (token expired) | NextGISClient | Log + alert admin |
| Batch file too large | Batch handler | "Файл слишком большой. Максимум 1 МБ и 1000 строк" |
| Duplicate webhook | WebhookProcessor | 200 OK (ignore) |
| Orphan webhook | WebhookProcessor | Log + alert, return 200 OK |
| No subscription | Any paid feature | "Эта функция доступна только по подписке" + tariffs |
| CSV format error | Batch service | "Ошибка в строке {n}: неверный формат. Пропускаю" |
| DB connection error | Any DB repo | Log error, return 503 |

---

## 15. FILES GENERATED BY THIS PROJECT

| File | Type | Description |
|------|------|-------------|
| `result_*.xlsx` | Excel | Batch check results (sent to user) |
| `parcel_report_*.pdf` | PDF | Parcel report (sent to user) |
| `*.csv` | CSV | User-uploaded files for batch processing |
| `/backups/pg_backup_*.sql` | SQL | Daily DB backup |

---

## 16. DEVELOPMENT ORDER (for AI coder)

### Phase 1: Core infrastructure
1. `app/core/config.py` + `app/core/enums.py` — settings and enums
2. `app/db/base.py` + `app/db/models.py` — all 10 models
3. `app/db/session.py` — async session
4. Alembic initial migration
5. `app/integrations/redis_cache.py` — cache client
6. `app/repositories/*` — all 10 repositories

### Phase 2: Backend services
7. `app/integrations/nextgis.py` — NextGIS API client
8. `app/services/parcel_service.py` — parcel search + cache
9. `app/repositories/*` — ensure all CRUD works

### Phase 3: Telegram bot core
10. `app/bot/setup.py` + `app/main.py` — FastAPI + aiogram integration
11. `app/bot/keyboards.py` — all keyboards
12. `app/bot/handlers/start.py` — /start + main menu
13. `app/bot/handlers/parcel.py` — parcel check flow
14. `app/bot/middlewares/limits.py` — rate limiting

### Phase 4: Payments
15. `app/integrations/yookassa.py` — YooKassa client
16. `app/services/payment_service.py` — payment creation
17. `app/api/webhooks.py` — webhook endpoint
18. `app/services/webhook_processor.py` — idempotent processing
19. `app/services/subscription_service.py` — subscription management
20. `app/bot/handlers/tariffs.py` + `payment.py` — tariff selection + purchase

### Phase 5: Advanced features
21. `app/services/batch_service.py` — batch processing
22. `app/workers/tasks.py` — ARQ tasks (batch, monitor)
23. `app/bot/handlers/batch.py` — batch upload handler
24. `app/services/pdf_service.py` — PDF generation
25. `app/services/monitor_service.py` — change detection
26. `app/services/notification_service.py` — notifications

### Phase 6: Admin & polish
27. `app/api/admin_api.py` — admin endpoints
28. `app/bot/handlers/admin.py` — admin commands
29. `app/api/health.py` — healthcheck
30. `Dockerfile` + `docker-compose.yml`
31. Tests

---

## 17. AI CODER INSTRUCTIONS

### Constraints
- **All files go to:** `C:\Users\Egor-\Desktop\ГИС Красноярск проект\Телеграм бот\`
- **Python 3.12+** — use modern features (match/case, type hints)
- **Async only** — no synchronous DB/HTTP calls
- **No global variables** — all state through dependency injection
- **No hardcoded config** — all via `.env` and `Config` class
- **Windows compatible** — use pathlib, not os.path
- **UTF-8 everywhere** — Russian text in responses

### Key files to look at first
1. `ТЗ_ПОЛНОЕ_ОПИСАНИЕ.md` — full project description with all UI/UX details
2. `ТЕХНИЧЕСКАЯ_АРХИТЕКТУРА.md` — this file (technical reference)
3. NextGIS OpenAPI spec at: `workspace/obsidian/Документы/WebGIS-проект/Исследования/NextGIS_OpenAPI_raw.json`

### Critical DO NOTs
- ❌ Do NOT use synchronous libraries (requests, psycopg2, redis-py sync)
- ❌ Do NOT use SQLite — only PostgreSQL 16
- ❌ Do NOT use polling for Telegram — webhook only
- ❌ Do NOT use Telegram Stars — YooKassa only
- ❌ Do NOT hardcode resource IDs — they go in .env
