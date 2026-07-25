# 🚀 Как запустить бота (инструкция по итогам аудита)

## ⚠️ Главная ошибка прошлого запуска

Архив был распакован **без сохранения папок** — все файлы оказались в одной куче,
появились дубликаты вида `__init__ (1).py`. Так бот работать не будет: коду нужна
структура `app/core/...`, `app/bot/...` и т.д.

**Как распаковывать правильно (Windows):**
1. Кликните по zip **правой кнопкой → «Извлечь всё…» → Извлечь**.
2. НЕ выделяйте файлы внутри архива мышкой и не перетаскивайте их — так теряются папки.
3. После распаковки внутри должна быть структура:

```
giskrsk_bot/
├── app/            ← пакеты python (core, bot, db, services, integrations)
├── alembic/
├── tools/
├── webapp/
├── shop_files/
├── clip_files/
├── requirements.txt
├── .env.example
├── start.bat
└── docker-compose.yml
```

Если у вас уже есть папка со «сломанной» распаковкой — просто удалите её целиком
и распакуйте заново.

---

## Шаг 1. Python

1. Скачайте Python 3.11+ с https://www.python.org/downloads/
2. При установке ОБЯЗАТЕЛЬНО поставьте галочку **«Add python.exe to PATH»**.
3. Проверка: откройте новый терминал (Win+R → cmd) и введите `python --version`.

## Шаг 2. Настройки (.env)

1. Скопируйте `.env.example` в файл с именем `.env` (именно так, с точкой в начале).
2. Заполните минимум: `BOT_TOKEN`, `POSTGRES_PASSWORD` (любой), данные NextGIS,
   ключи YooKassa (или тестовые), `ADMIN_IDS`, `DEEPSEEK_API_KEY`.
3. Для быстрого теста без PostgreSQL поставьте `USE_SQLITE=true`.

## Шаг 3. Запуск — два варианта

### Вариант А: Docker (проще всего, всё поднимается само)

1. Установите Docker Desktop: https://www.docker.com/products/docker-desktop/
2. В папке проекта: `docker compose up -d --build`
3. Готово: поднимутся PostgreSQL, Redis и бот. Логи: `docker compose logs -f app`

### Вариант Б: вручную (без Docker)

1. Дважды кликните **start.bat** — он сам создаст виртуальное окружение,
   установит зависимости и запустит бота.
2. Либо руками в терминале:
   ```bat
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   alembic upgrade head
   python -m app.main
   ```
3. ⚠️ Для лимитов запросов и кэша нужен **Redis**. Без Docker на Windows его
   проще всего запустить так: `docker run -d -p 6379:6379 redis:7-alpine`
   (или установить Memurai — Redis для Windows).
4. Если `USE_SQLITE=false` — нужен и PostgreSQL (проще через Docker, см. Вариант А).

## Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `ModuleNotFoundError: app.core` | распаковка без папок | распакуйте заново (см. выше) |
| `python не является командой` | Python не в PATH | переустановите Python с галочкой PATH |
| падает при старте с ошибкой про переменную | нет `.env` или не заполнено поле | скопируйте `.env.example` → `.env`, заполните |
| `ConnectionRefusedError 6379` | не запущен Redis | `docker run -d -p 6379:6379 redis:7-alpine` |
| `ConnectionRefusedError 5432` | не запущен PostgreSQL | `docker compose up -d postgres` или `USE_SQLITE=true` |

## Что нового в v11

- ✅ Добавлен `aiosqlite` в requirements.txt (нужен для режима USE_SQLITE=true)
- ✅ Обновлён `.env.example` — теперь в нём ВСЕ переменные конфига с пояснениями
- ✅ Новый `start.bat` — сам создаёт venv, ставит зависимости и запускает (вместо старого с зашитым путём)
- ✅ Файлы с битыми кириллическими именами переименованы: `ARCHITECTURE.md`, `PROJECT_OVERVIEW.md` (они ломали распаковку на Windows)
- ✅ Эта инструкция
