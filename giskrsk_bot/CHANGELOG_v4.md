# Изменения v4 (пул аккаунтов + регистрация + рассылка)

Инструкция для применения: этот архив — ПОЛНЫЙ проект бота.
Просто распакуйте его ПОВЕРХ папки бота с заменой файлов
(.env не трогать, если уже настроен) и перезапустите run_bot.bat.

## Новые файлы

- `app/services/account_pool.py` — пул готовых NextGIS-аккаунтов
  (JSON-файл `account_pool.json` в корне проекта).
- `app/services/profile_store.py` — мини-CRM: имя, почта, телефон,
  согласие на рассылку (JSON-файл `user_profiles.json`).
- `app/bot/handlers/registration.py` — регистрация /register:
  имя → почта → телефон (кнопка контакта) → согласие на акции.

## Изменённые файлы

- `app/bot/handlers/tariffs.py` — выдача подписки: сначала свободный
  аккаунт из пула, потом создание через NextGIS API; текст
  «проверка до 30 минут».
- `app/bot/handlers/shop.py` — текст «проверка до 30 минут».
- `app/bot/handlers/start.py` — приглашение к регистрации при /start
  для новых пользователей.
- `app/bot/handlers/admin.py` — команда `/promo текст` (рекламная
  рассылка тем, кто дал согласие).
- `app/bot/handlers/account.py` — админ-команды пула:
  `/add_account логин пароль`, `/accounts`, `/release_account логин`.
- `app/bot/states.py` — FSM-состояния Registration.
- `app/bot/keyboards_data.py` — RegAction (+ SubPayAction/SubAdminAction из v3).
- `app/bot/handlers/__init__.py`, `app/bot/setup.py` — подключён
  registration_router.

## Как работает пул аккаунтов

1. Админ создаёт аккаунты в команде NextGIS (4 свободных места)
   и добавляет их в бота: `/add_account map_user1 пароль1` и т.д.
2. Клиент оплачивает → админ жмёт «Выдать доступ» → бот берёт
   первый свободный аккаунт и отправляет логин/пароль клиенту.
3. Подписка кончилась → админ меняет пароль в NextGIS и возвращает
   аккаунт: `/release_account map_user1`, затем
   `/add_account map_user1 новый_пароль`.
4. Если пул пуст — бот пробует создать аккаунт через NextGIS API
   (если сервис поднят), иначе просит админа выдать вручную.
