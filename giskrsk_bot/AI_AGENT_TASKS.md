# 🎯 Задачи для AI-агентов (GPT/Opus из Notion)

> Создано: 2026-07-25
> Назначение: инструкция для агентов, работающих через Notion

---

## 1. 🔑 DeepSeek API Key

Ключ уже установлен в `.env` (не пушится в git — безопасность).
Для работы AI-консультанта в боте ключ активен.
Модель: `deepseek-chat`

---

## 2. 🗺 Стилизация карты — главная задача

**Цель:** Сделать стиль карты в Telegram WebApp (`webapp/index.html`) 
**максимально похожим на NextGIS Web Map.**

### Что сейчас
Карта использует MapLibre GL JS с кастомными стилями:
- Градиентные кнопки, glassmorphism
- Тёмная тема
- Слои ПЗЗ с прозрачностью 55%
- Базовая подложка: OpenStreetMap / светлая / тёмная / спутник / 2ГИС

### Что должно стать
Скопировать визуальный стиль NextGIS Web:
- **Цветовая схема:** как в NextGIS (тёмный header, панели, цвета кнопок)
- **Стиль слоёв ПЗЗ:** цвета зон должны соответствовать NextGIS (не просто случайные цвета, а те же самые hex-коды)
- **Панель слоёв:** как в NextGIS — чекбоксы, прозрачность, порядок
- **Подложка:** Light/Dark CARTO как в NextGIS
- **Информационная панель:** при клике на участок — стиль как в NextGIS
- **Кнопки навигации:** +/-, compass, fullscreen — стилизовать как в NextGIS

### Как посмотреть референс
NextGIS Web Map: **https://zimin-maplive0000.nextgis.com/resource/127/display?panel=layers**
(логин: Yaroslav_000)

### Файлы для правки
- `webapp/index.html` — основной файл карты (MapLibre GL JS)
- `webapp/server.js` — Node.js сервер (не менять без необходимости)

---

## 3. 🌐 WEBAPP_URL

`WEBAPP_URL` в `.env` пустой. Для работы карты внутри Telegram Mini App
нужен HTTPS-адрес. 

**Варианты:**
1. Опубликовать `webapp/` на GitHub Pages
2. Использовать VPS с Nginx + SSL
3. Cloudflare Tunnel / ngrok для разработки

---

## 4. 📋 Прочие известные проблемы (из AUDIT_v14.md)

| # | Проблема | Приоритет |
|---|----------|-----------|
| 6 | Batch-обработка синхронная (блокирует бот) | 🔴 |
| 8 | NextGIS bearer_token = placeholder | 🟡 |
| 13 | Реальные ПЗЗ не развёрнуты в webapp/data/ | 🔴 |

---

## 5. 📁 Структура для агентов

```
giskrsk_bot/
├── app/               # Python backend (aiogram + FastAPI)
│   ├── bot/           # Telegram bot handlers
│   ├── services/      # Business logic
│   ├── api/           # FastAPI endpoints
│   └── ...
├── webapp/            # Map frontend (MapLibre GL JS)
│   ├── index.html     # ⬅️ ГЛАВНЫЙ ФАЙЛ ДЛЯ ПРАВКИ
│   ├── server.js      # Node.js dev server
│   └── data/          # GeoJSON слои
├── tools/             # Утилиты
└── shop_files/        # Магазин геоданных
```
