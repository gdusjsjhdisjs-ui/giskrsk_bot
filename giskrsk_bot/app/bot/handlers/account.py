"""Handler: create/manage NextGIS Web accounts via bot."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.bot.filters import IsAdmin
from app.services.account_manager import AccountManager
from app.services.account_pool import AccountPool

router = Router(name="account")
pool = AccountPool()


@router.message(Command("get_access"))
@router.message(F.text == "🔑 Получить доступ")
async def cmd_get_access(message: Message, **data) -> None:
    """Создать аккаунт в NextGIS Web."""
    manager: AccountManager | None = (data.get("services") or {}).get("account_manager")
    if not manager:
        await message.answer("❌ Сервис создания аккаунтов временно недоступен.")
        return

    tg_user = message.from_user
    login = f"tg_{tg_user.id}"
    display = tg_user.full_name or tg_user.username or f"User {tg_user.id}"

    await message.answer("🔑 Создаю аккаунт в NextGIS Web...")

    try:
        result = await manager.create_user(
            login=login,
            display_name=display,
            group_keyname="basic_users",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка создания аккаунта: {e}")
        return

    await message.answer(
        f"✅ <b>Аккаунт создан!</b>\n\n"
        f"🌍 <b>Сервер:</b> https://zimin-maplive0000.nextgis.com\n"
        f"👤 <b>Логин:</b> <code>{result['login']}</code>\n"
        f"🔑 <b>Пароль:</b> <code>{result['password']}</code>\n\n"
        f"📦 <b>Тариф:</b> Пробный (basic)\n\n"
        f"⚠️ Сохраните логин и пароль! Они больше не покажутся.\n\n"
        f"💡 Для полного доступа оформите подписку: /tariffs",
    )


@router.message(Command("my_account"))
async def cmd_my_account(message: Message, **data) -> None:
    """Показать информацию о моём аккаунте NextGIS."""
    manager: AccountManager | None = (data.get("services") or {}).get("account_manager")
    if not manager:
        await message.answer("❌ Сервис недоступен.")
        return

    login = f"tg_{message.from_user.id}"

    # Поищем пользователя через API
    client = manager.nextgis.client
    await manager.nextgis.login()

    try:
        r = await client.get("/api/component/auth/user/", params={"brief": True})
        if r.status_code == 200:
            users = r.json()
            for u in users:
                if u.get("keyname") == login:
                    status = "🚫 Заблокирован" if u.get("disabled") else "✅ Активен"
                    await message.answer(
                        f"👤 <b>Мой аккаунт NextGIS</b>\n\n"
                        f"🔑 Логин: <code>{login}</code>\n"
                        f"📊 Статус: {status}\n"
                        f"🆔 ID: {u['id']}\n"
                        f"📌 Сервер: zimin-maplive0000.nextgis.com",
                    )
                    return
            await message.answer("❌ Аккаунт не найден. Создайте: /get_access")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


# ─── Админ: пул готовых аккаунтов (командные места NextGIS) ─────


@router.message(Command("add_account"), IsAdmin())
async def cmd_add_account(message: Message) -> None:
    """Добавить готовый аккаунт в пул: /add_account логин пароль."""
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: <code>/add_account логин пароль</code>")
        return
    acc_login, acc_password = parts[1], parts[2]

    # 🔐 Проверяем, что логин/пароль реально принимаются NextGIS,
    # чтобы в пул не попадали нерабочие аккаунты
    checking = await message.answer("⏳ Проверяю логин и пароль в NextGIS…")
    import httpx

    from app.core.config import settings

    try:
        async with httpx.AsyncClient(
            base_url=settings.NEXTGIS_BASE_URL, timeout=15,
        ) as client:
            resp = await client.post(
                "/api/component/auth/login",
                json={"login": acc_login, "password": acc_password},
            )
        credentials_ok = resp.status_code == 200
    except Exception:  # noqa: BLE001 — сеть/таймаут: не блокируем добавление
        credentials_ok = None

    if credentials_ok is False:
        await checking.edit_text(
            f"❌ NextGIS не принял логин <code>{acc_login}</code> с этим паролем.\n"
            "Аккаунт <b>не добавлен</b> в пул. Проверьте данные и попробуйте снова."
        )
        return

    account = pool.add(acc_login, acc_password)
    warn = "" if credentials_ok else "\n⚠️ NextGIS недоступен, логин добавлен без проверки."
    await checking.edit_text(
        f"✅ Аккаунт <code>{account['login']}</code> добавлен в пул.\n"
        f"🎫 Свободных аккаунтов: {pool.free_count()}.{warn}"
    )

    # 📋 Лист ожидания: сообщаем клиентам, что место освободилось
    from app.services.waitlist_store import WaitlistStore

    entries = WaitlistStore().pop_all()
    notified = 0
    for entry in entries:
        try:
            await message.bot.send_message(
                entry["user_id"],
                "🎉 <b>Появилось свободное место!</b>\n\n"
                "Вы были в листе ожидания. Успейте оформить доступ:\n"
                "💳 Тарифы и пробный день: /tariffs",
            )
            notified += 1
        except Exception:  # noqa: BLE001
            continue
    if entries:
        await message.answer(f"📣 Уведомлено из листа ожидания: {notified}.")


@router.message(Command("accounts"), IsAdmin())
async def cmd_accounts(message: Message) -> None:
    """Показать пул аккаунтов."""
    accounts = pool.list_all()
    if not accounts:
        await message.answer(
            "Пул пуст. Добавьте готовые аккаунты:\n"
            "<code>/add_account логин пароль</code>"
        )
        return
    lines = ["🎫 <b>Пул аккаунтов NextGIS:</b>\n"]
    for a in accounts:
        if a["status"] == "free":
            lines.append(f"🟢 <code>{a['login']}</code> — свободен")
        elif a["status"] == "expired":
            lines.append(
                f"🟠 <code>{a['login']}</code> — истёк: смените пароль в NextGIS и "
                f"верните: <code>/add_account {a['login']} новый_пароль</code>"
            )
        else:
            lines.append(
                f"🔴 <code>{a['login']}</code> — занят "
                f"(клиент <code>{a['user_id']}</code>, заказ {a['order_id']})"
            )
    lines.append("\nВернуть в пул: <code>/release_account логин</code>")
    await message.answer("\n".join(lines))


@router.message(Command("release_account"), IsAdmin())
async def cmd_release_account(message: Message) -> None:
    """Вернуть аккаунт в пул (после смены пароля в NextGIS!)."""
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer(
            "Использование: <code>/release_account логин</code>\n"
            "⚠️ Перед этим смените пароль аккаунта в NextGIS, "
            "затем обновите его: <code>/add_account логин новый_пароль</code>"
        )
        return
    if pool.release(parts[1]):
        await message.answer(
            f"🟢 Аккаунт <code>{parts[1]}</code> снова свободен.\n"
            f"⚠️ Не забудьте сменить его пароль в NextGIS и обновить в пуле:\n"
            f"<code>/add_account {parts[1]} новый_пароль</code>"
        )
    else:
        await message.answer("❌ Такого аккаунта нет в пуле. Список: /accounts")
