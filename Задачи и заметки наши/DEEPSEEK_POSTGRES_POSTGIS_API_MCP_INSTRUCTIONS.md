# Инструкция для DeepSeek: PostgreSQL, PostGIS, API и MCP
## Проект «ГИС Красноярье»

> Назначение: использовать этот файл как техническое задание для DeepSeek в VS Code. Цель — создать безопасное аналитическое ядро для AI‑ассистента, не предоставляя нейросети прямой полный доступ к базе данных.

---

## 1. Главная концепция

DeepSeek — не база данных и не GIS‑движок. Модель должна:

1. понять вопрос пользователя;
2. выбрать разрешённый инструмент;
3. передать инструменту проверенные параметры;
4. получить факты из PostgreSQL/PostGIS, NextGIS или документов;
5. объяснить найденные факты человеку;
6. показать источники, полноту и ограничения анализа.

Правильный поток:

```text
Telegram / WebApp
        ↓
FastAPI
        ↓
AI Orchestrator
        ↓
Контроллер разрешённых инструментов
        ↓
Python Services
        ↓
PostgreSQL + PostGIS / NextGIS / документы
        ↓
Evidence Pack
        ↓
DeepSeek
        ↓
Структурированный ответ пользователю
```

DeepSeek запрещено предоставлять произвольный SQL, пароли от БД и административный доступ.

---

## 2. Роли компонентов

### PostgreSQL

Использовать для хранения:

- пользователей;
- подписок и платежей;
- участков и их атрибутов;
- документов и поисковых фрагментов;
- истории обновлений;
- заданий анализа;
- AI‑сессий и обратной связи;
- версий и дат актуальности источников.

### PostGIS

PostGIS — расширение PostgreSQL для геометрии. Использовать для:

- хранения точек, линий, полигонов и мультиполигонов;
- point‑in‑polygon;
- пересечений участка с ПЗЗ, ЗОУИТ и красными линиями;
- анализа буфера 50–1000 метров;
- поиска соседних объектов;
- расчёта расстояний и площадей;
- анализа выделенной пользователем области;
- сравнения геометрии между версиями;
- формирования пространственных агрегатов для AI.

### NextGIS

NextGIS оставить как источник и/или сервис публикации карты. При необходимости синхронизировать векторные данные из NextGIS в PostGIS. Не считать TMS изображение полноценным источником векторной аналитики.

### DeepSeek

Использовать для:

- распознавания намерения пользователя;
- извлечения кадастрового номера, координат и условий;
- выбора разрешённого инструмента;
- объяснения результатов;
- сравнения уже рассчитанных фактов;
- подготовки понятных рекомендаций и чек‑листов.

DeepSeek не должен самостоятельно рассчитывать площади, пересечения и координаты.

---

## 3. Не создавать сразу систему независимых агентов

На первом этапе создать одного `AI Orchestrator` с набором специализированных инструментов:

```text
AI Orchestrator
├── get_parcel
├── find_pzz_zone
├── find_intersections
├── analyze_buffer
├── analyze_selected_area
├── search_documents
├── compare_parcels
├── explain_changes
└── generate_report_data
```

Для пользователя это один ассистент. Внутри каждый инструмент реализован отдельным Python‑сервисом.

В будущем сервисы можно представить как специализированных агентов:

- Parcel Agent;
- Spatial Analysis Agent;
- Document Agent;
- Comparison Agent;
- Monitoring Agent;
- Report Agent.

Но они должны использовать общие проверенные сервисы и не обращаться к таблицам произвольным SQL.

---

## 4. Безопасность доступа к БД

### Запрещено

- передавать DeepSeek строку подключения PostgreSQL;
- позволять модели генерировать и исполнять произвольный SQL;
- использовать суперпользователя PostgreSQL;
- разрешать AI доступ к паролям, токенам и платёжным данным;
- выполнять SQL из ответа модели через `eval`, `exec` или конкатенацию строк;
- разрешать записи в основные таблицы через аналитические инструменты;
- возвращать полные тексты внутренних исключений пользователю.

### Обязательно

1. Создать отдельную роль БД для аналитического сервиса.
2. На первом этапе предоставить ей только `SELECT` для разрешённых представлений.
3. Скрыть чувствительные таблицы за PostgreSQL views.
4. Использовать параметризованные запросы SQLAlchemy.
5. Ограничить `statement_timeout`.
6. Ограничить число возвращаемых строк.
7. Вести аудит вызовов инструментов.
8. Валидировать параметры через Pydantic.
9. Использовать whitelist инструментов, слоёв, полей и операторов.
10. Хранить секреты только в `.env` или secret manager.

Пример роли только для чтения:

```sql
CREATE ROLE gis_ai_reader LOGIN PASSWORD 'REPLACE_IN_SECRET_MANAGER';

REVOKE ALL ON SCHEMA public FROM gis_ai_reader;
GRANT USAGE ON SCHEMA gis_public TO gis_ai_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gis_public TO gis_ai_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA gis_public
GRANT SELECT ON TABLES TO gis_ai_reader;

ALTER ROLE gis_ai_reader SET statement_timeout = '5s';
ALTER ROLE gis_ai_reader SET default_transaction_read_only = on;
```

Пароль из примера не добавлять в Git и не использовать буквально.

---

## 5. Предлагаемая структура БД

Не создавай таблицы без проверки существующих SQLAlchemy models и миграций.

### Схемы

```text
public       — существующие бизнес-таблицы
geo          — исходные и нормализованные геоданные
documents    — документы и поисковые фрагменты
analytics    — snapshots, результаты и изменения
gis_public   — безопасные views для аналитических инструментов
```

### Основные геотаблицы

```text
geo.parcels
geo.pzz_zones
geo.red_lines
geo.zouit
geo.master_plan_zones
geo.municipalities
```

Предлагаемые общие поля:

```text
id
source_id
external_id
name/code
properties JSONB
geometry geometry(..., 4326)
source_url
source_revision
data_date
loaded_at
checksum
is_current
```

Реальные названия и типы определить после анализа существующих GeoJSON и NextGIS. Не выдумывать свойства.

### Индексы

Для каждой крупной геотаблицы создать GiST‑индекс:

```sql
CREATE INDEX IF NOT EXISTS ix_parcels_geometry
ON geo.parcels USING GIST (geometry);
```

Для кадастрового номера — обычный уникальный или B‑tree индекс:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS ix_parcels_cadnum
ON geo.parcels (cadastral_number);
```

Перед созданием индекса проверить дубликаты и формат данных.

---

## 6. Координатные системы

1. Хранить исходный SRID каждого слоя в метаданных.
2. Для обмена с WebApp обычно использовать EPSG:4326.
3. Не рассчитывать площадь напрямую в градусах EPSG:4326.
4. Для расстояний можно использовать `geography` или подходящую метрическую CRS.
5. Перед импортом проверять и исправлять геометрию.

Пример безопасного расстояния в метрах:

```sql
ST_DWithin(
  a.geometry::geography,
  b.geometry::geography,
  :radius_m
)
```

Пример площади:

```sql
ST_Area(geometry::geography)
```

Если слой очень большой, оценить производительность cast в `geography` и при необходимости хранить отдельное поле/проекцию.

---

## 7. Валидация геоданных при импорте

При загрузке GeoJSON/NextGIS:

1. определить CRS;
2. проверить обязательные свойства;
3. привести кадастровые номера к единому формату;
4. проверить `ST_IsValid`;
5. исправлять только контролируемым способом через `ST_MakeValid`;
6. не терять исходную геометрию и исходные properties;
7. считать checksum;
8. сохранять дату источника и дату загрузки;
9. импортировать в staging‑таблицу;
10. после проверки переключать новую версию в `is_current=true`.

Не заменять действующий слой напрямую до прохождения проверок.

---

## 8. SpatialAnalysisService

Создать отдельный сервис. Он выполняет только заранее определённые операции.

```python
class SpatialAnalysisService:
    async def get_parcel(self, cadastral_number: str): ...
    async def find_pzz_zone(self, parcel_id: str): ...
    async def find_intersections(self, parcel_id: str, layer: str): ...
    async def analyze_buffer(self, parcel_id: str, radius_m: float): ...
    async def analyze_geometry(self, geometry_geojson: dict): ...
    async def compare_parcels(self, parcel_ids: list[str]): ...
```

Параметр `layer` проверять по whitelist:

```python
ALLOWED_INTERSECTION_LAYERS = {
    "pzz": "gis_public.pzz_zones",
    "zouit": "gis_public.zouit",
    "red_lines": "gis_public.red_lines",
    "master_plan": "gis_public.master_plan_zones",
}
```

Не подставлять произвольное имя таблицы, полученное от пользователя или DeepSeek.

---

## 9. Пример безопасного анализа пересечений

```python
from sqlalchemy import text

async def find_zouit_intersections(session, parcel_id: str):
    query = text("""
        SELECT
            z.id,
            z.name,
            z.source_id,
            z.data_date,
            ST_Area(
                ST_Intersection(z.geometry, p.geometry)::geography
            ) AS intersection_area_m2
        FROM gis_public.zouit AS z
        JOIN gis_public.parcels AS p
          ON p.id = :parcel_id
        WHERE ST_Intersects(z.geometry, p.geometry)
        ORDER BY intersection_area_m2 DESC
        LIMIT 100
    """)

    result = await session.execute(query, {"parcel_id": parcel_id})
    return result.mappings().all()
```

Перед использованием проверить совместимость геометрий, SRID и реальные поля views.

---

## 10. Evidence Pack

DeepSeek должен получать не строки из таблиц, а нормализованный пакет фактов.

```json
{
  "request_id": "uuid",
  "subject": {
    "type": "parcel",
    "cadastral_number": "24:11:0330102:814"
  },
  "facts": {
    "area_m2": 1200,
    "pzz_zone": {
      "code": "Ж-1",
      "name": "Жилая зона"
    },
    "red_line_intersection": false,
    "zouit_intersections": []
  },
  "completeness": {
    "checked": ["pzz", "red_lines"],
    "not_checked": ["zouit_documents"],
    "score": 0.67
  },
  "sources": [
    {
      "source_id": "pzz_krsk_2026",
      "source_type": "postgis_layer",
      "data_date": "2026-05-14",
      "source_url": "https://..."
    }
  ],
  "warnings": [
    "ЗОУИТ не проверены аналитически"
  ]
}
```

DeepSeek обязан отделять `checked` от `not_checked`. Отсутствие найденного пересечения не означает отсутствие ограничения, если источник не проверен.

---

## 11. Tool Calling для DeepSeek

Разрешённые инструменты описать JSON‑схемами. Пример:

```json
{
  "name": "analyze_parcel_buffer",
  "description": "Находит объекты в заданном радиусе от участка",
  "parameters": {
    "type": "object",
    "properties": {
      "cadastral_number": {"type": "string"},
      "radius_m": {"type": "number", "minimum": 10, "maximum": 5000},
      "layers": {
        "type": "array",
        "items": {"enum": ["pzz", "zouit", "red_lines", "master_plan"]}
      }
    },
    "required": ["cadastral_number", "radius_m", "layers"]
  }
}
```

Backend должен:

1. проверить имя инструмента;
2. провалидировать аргументы;
3. проверить тариф и rate limit;
4. выполнить сервис;
5. ограничить результат;
6. сформировать Evidence Pack;
7. только затем снова вызвать DeepSeek для объяснения.

Не выполнять более 3–5 tool calls на один пользовательский запрос без дополнительного контроля.

---

## 12. Собственный FastAPI

Основным интерфейсом системы сделать собственный API:

```text
POST /api/ai/chat
POST /api/gis/parcel/analyze
POST /api/gis/area/analyze
POST /api/gis/parcels/compare
POST /api/documents/search
GET  /api/jobs/{job_id}
```

### Пример запроса

```json
{
  "question": "Какие ограничения найдены рядом с участком?",
  "context": {
    "cadastral_number": "24:11:0330102:814",
    "radius_m": 100
  }
}
```

### Пример ответа

```json
{
  "request_id": "uuid",
  "answer": "...",
  "facts": [],
  "sources": [],
  "confidence": 0.71,
  "completeness": 0.67,
  "missing_information": [],
  "disclaimer": "Предварительный информационный анализ"
}
```

WebApp и Telegram используют один и тот же backend API.

---

## 13. MCP

MCP добавить после создания устойчивых Python‑сервисов и API.

MCP не должен напрямую предоставлять общую SQL‑консоль. Он должен публиковать только безопасные инструменты:

```text
get_parcel
analyze_parcel
analyze_area
find_layer_intersections
search_documents
compare_parcels
get_layer_freshness
```

Архитектура:

```text
SpatialAnalysisService ─┬─ FastAPI для WebApp и Telegram
DocumentSearchService ──┤
ComparisonService ──────┴─ MCP server для внешних AI-клиентов
```

MCP — дополнительный адаптер над теми же сервисами, а не отдельная реализация логики.

### Когда MCP полезен

- подключение DeepSeek/Claude из IDE;
- административный AI‑ассистент;
- интеграция с другими агентами;
- предоставление GIS‑инструментов корпоративным клиентам.

### Когда MCP пока не нужен

- обычная работа Telegram‑бота;
- WebApp;
- единственный backend;
- первая версия AI‑анализа.

Для первой версии достаточно FastAPI tool layer.

---

## 14. Документы и pgvector

PostgreSQL может хранить документы и фрагменты. Начинать с полнотекстового поиска. Затем добавить `pgvector` для поиска по смыслу.

```text
documents.documents
documents.document_chunks
documents.document_versions
```

Пример полей чанка:

```text
id
document_id
page
section
text
search_vector
embedding
municipality
zone_codes
revision_date
source_url
```

Рекомендуемый поиск:

```text
фильтр территории и редакции
        ↓
PostgreSQL FTS
        +
pgvector semantic search
        ↓
объединение результатов
        ↓
rerank
        ↓
5–8 фрагментов для DeepSeek
```

DeepSeek обязан ссылаться на существующий `chunk_id`, страницу и документ.

---

## 15. Кэш и фоновые задачи

Redis использовать для:

- rate limits;
- кэша одинаковых запросов;
- состояния короткой AI‑сессии;
- очереди ARQ;
- прогресса продолжительного анализа.

В ARQ выносить:

- импорт крупных GeoJSON;
- построение embeddings;
- анализ больших областей;
- сравнение версий слоёв;
- пакетную проверку участков;
- генерацию больших PDF.

Не использовать `asyncio.create_task` для критичных заданий, которые должны пережить рестарт процесса.

---

## 16. Этапы внедрения

### Этап 1 — аудит

- изучить существующие models, migrations и сервисы;
- проверить фактические поля GeoJSON/NextGIS;
- составить карту источников;
- определить CRS;
- найти чувствительные таблицы.

### Этап 2 — PostGIS MVP

- включить расширение PostGIS;
- создать staging и geo schemas;
- импортировать один небольшой слой ПЗЗ;
- импортировать тестовые участки;
- создать индексы;
- проверить point‑in‑polygon и intersection.

### Этап 3 — безопасный сервис

- создать `SpatialAnalysisService`;
- отдельную read‑only роль;
- безопасные views;
- Pydantic‑схемы;
- unit/integration tests.

### Этап 4 — DeepSeek tools

- зарегистрировать 3 инструмента: `get_parcel`, `find_intersections`, `analyze_buffer`;
- добавить Evidence Pack;
- структурированный ответ;
- fallback без AI.

### Этап 5 — расширение

- анализ выделенной области;
- сравнение участков;
- документы и pgvector;
- мониторинг изменений;
- MCP‑адаптер.

---

## 17. Первая инструкция DeepSeek: только анализ

```text
Изучи существующий проект «ГИС Красноярье» перед внедрением PostgreSQL/PostGIS.
Пока ничего не изменяй.

Найди и опиши:
1. Текущие SQLAlchemy models и миграции.
2. Версию PostgreSQL и используемые extensions.
3. Как создаётся async engine/session.
4. Какие данные сейчас хранятся в PostgreSQL, SQLite и JSON-файлах.
5. Где находятся GeoJSON и их размеры.
6. Реальные geometry types, CRS и properties каждого слоя.
7. Какие данные поступают из NextGIS API, а какие существуют только как TMS.
8. Какие сервисы можно переиспользовать.
9. Где DeepSeek сейчас вызывается и какие данные получает.
10. Какие секреты или чувствительные данные необходимо изолировать.

Выдай:
- карту существующей архитектуры;
- таблицу источников данных;
- предложение схем PostGIS;
- план миграций без потери данных;
- список безопасных views;
- список инструментов для AI Orchestrator;
- тест-план;
- риски и rollback-план.

Не выдумывай свойства, CRS, ID ресурсов и API.
Не создавай таблицы и не меняй код до подтверждения.
После отчёта остановись.
```

---

## 18. Вторая инструкция DeepSeek: PostGIS MVP

Использовать только после утверждения аудита:

```text
Реализуй минимальный PostGIS MVP без изменения существующего пользовательского интерфейса.

Требования:
1. Добавить PostGIS в docker-compose и миграции.
2. Создать схемы geo и gis_public.
3. Импортировать один подтверждённый слой ПЗЗ и небольшой набор участков.
4. Сохранить source metadata, revision, data_date и checksum.
5. Создать GiST и B-tree индексы.
6. Создать read-only views без чувствительных данных.
7. Реализовать SpatialAnalysisService:
   - get_parcel;
   - find_pzz_zone;
   - find_intersections;
   - analyze_buffer.
8. Все запросы должны быть параметризованными.
9. Добавить ограничения radius, layers, rows и statement timeout.
10. Добавить integration tests на тестовой БД.
11. Добавить команду импорта и rollback-инструкцию.
12. Не подключать DeepSeek к строке БД и не разрешать произвольный SQL.

Сначала покажи точный diff-план по файлам и миграциям.
Не изменяй код до подтверждения.
```

---

## 19. Третья инструкция DeepSeek: безопасные AI tools

```text
Подключи DeepSeek к готовому SpatialAnalysisService через безопасный tool layer.

Реализуй только три инструмента:
1. get_parcel;
2. find_intersections;
3. analyze_buffer.

Требования:
- whitelist инструментов, слоёв и аргументов;
- Pydantic validation;
- никаких SQL-строк от модели;
- максимум 3 tool calls на запрос;
- Evidence Pack;
- проверка источников;
- structured output;
- timeout и fallback;
- аудит вызовов без секретов;
- unit tests с mock DeepSeek;
- integration tests SpatialAnalysisService;
- сохранение существующих лимитов тарифов.

Сначала покажи sequence diagram и diff-план. После этого остановись.
```

---

## 20. Критерии готовности

Система готова, если:

- DeepSeek не имеет прямых реквизитов БД;
- произвольный SQL невозможен;
- GIS‑расчёты выполняет PostGIS;
- инструменты работают через whitelist;
- чувствительные таблицы недоступны аналитической роли;
- каждый факт имеет источник и дату;
- непроверенные источники явно отмечаются;
- запросы ограничены по времени и объёму;
- есть тестовая БД, миграции и rollback;
- при недоступности DeepSeek пользователь получает факты без объяснения;
- FastAPI и MCP используют одни и те же сервисы;
- MCP не дублирует бизнес‑логику и не предоставляет SQL‑консоль.

---

## Итог

Правильная модель взаимодействия:

> **DeepSeek понимает задачу → выбирает разрешённый инструмент → Python обращается к PostGIS → PostGIS рассчитывает факты → DeepSeek объясняет результат.**

PostGIS является аналитическим ядром, FastAPI — безопасным интерфейсом, MCP — дополнительным адаптером для внешних AI‑клиентов, а DeepSeek — оркестратором и объясняющим слоем.
