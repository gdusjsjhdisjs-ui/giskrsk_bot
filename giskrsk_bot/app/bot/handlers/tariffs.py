"""Хендлер тарифов: оплата ПЕРЕВОДОМ ПО НОМЕРУ КАРТЫ + автовыдача доступа.

Сценарий:
1. Клиент выбирает тариф → «Оплатить переводом на карту».
2. Бот показывает номер карты и код заказа.
3. Клиент переводит деньги и жмёт «✅ Я оплатил».
4. Админ получает уведомление с кнопкой «Выдать доступ».
5. По кнопке бот АВТОМАТИЧЕСКИ:
   - активирует подписку в БД (SubscriptionService);
   - создаёт аккаунт в NextGIS Web (AccountManager);
   - отправляет клиенту логин, пароль и ссылку на карту.

Если NextGIS недоступен — клиент получает подтверждение оплаты,
а админ — инструкцию выдать доступ вручную (грейсфол без потери продажи).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import tariffs_keyboard
from app.bot.keyboards_data import SubAdminAction, SubPayAction, TariffSelect
from app.core.config import settings
from app.services.account_pool import AccountPool
from app.services.profile_store import ProfileStore
from app.services.referral_store import BONUS_DAYS, ReferralStore
from app.services.shop_orders import (
    STATUS_CLAIMED,
    STATUS_DELIVERED,
    STATUS_REJECTED,
    ShopOrderStore,
    fmt_amount,
)

logger = logging.getLogger(__name__)

router = Router(name="tariffs")
orders = ShopOrderStore()
account_pool = AccountPool()
profiles = ProfileStore()
referrals = ReferralStore()


# ─── Справочники тарифов ─────────────────────────────────────────

TARIFF_PRICES: dict[str, int] = {
    "basic_30d": 2990,
    "pro_30d": 4990,
    "pro_90d": 9900,
    "year": 24900,
}

TARIFF_TITLES: dict[str, str] = {
    "basic_30d": "Basic — 30 дней",
    "pro_30d": "Pro — 30 дней",
    "pro_90d": "Pro — 90 дней",
    "year": "Pro — 12 месяцев",
}

# Группа NextGIS по тарифу
TARIFF_GROUPS: dict[str, str] = {
    "basic_30d": "basic_users",
    "pro_30d": "pro_users",
    "pro_90d": "pro_users",
    "year": "pro_users",
}

TARIFF_DESCRIPTIONS = {
    "basic_30d": (
        "📦 <b>Basic</b> — 2 990 ₽/мес\n\n"
        "✅ Доступ к веб-карте ПЗЗ\n"
        "✅ До 30 проверок в день в боте\n"
        "✅ Поиск по кадастровому номеру\n"
        "✅ Просмотр зоны ПЗЗ\n"
        "✅ Базовая поддержка"
    ),
    "pro_30d": (
        "⭐ <b>Pro</b> — 4 990 ₽/мес\n\n"
        "✅ Доступ к веб-карте ПЗЗ\n"
        "✅ До 100 проверок в день в боте\n"
        "✅ Поиск по КН и геопозиции\n"
        "✅ Просмотр зоны ПЗЗ и ВРИ\n"
        "✅ Отслеживание изменений\n"
        "✅ Пакетная проверка (CSV)\n"
        "✅ Приоритетная поддержка"
    ),
    "pro_90d": (
        "⭐ <b>Pro 90 дней</b> — 9 900 ₽ (3 300 ₽/мес)\n\n"
        "✅ Все возможности Pro\n"
        "✅ Экономия 33% против помесячной"
    ),
    "year": (
        "👑 <b>Pro на год</b> — 24 900 ₽ (2 075 ₽/мес)\n\n"
        "✅ Все возможности Pro\n"
        "✅ Максимальная выгода — 58% экономии"
    ),
}

_TARIFFS_INTRO = (
    "💰 <b>Тарифы ГИС Красноярье</b>\n\n"
    "Одна подписка = доступ к веб-карте + все функции бота.\n"
    "Оплата — переводом на карту, доступ выдаётся автоматически "
    "после проверки платежа.\n\n"
    "Выберите тариф:"
)


def _fmt_price(amount: int) -> str:
    return f"{amount:,} ₽".replace(",", " ")


def tariff_card_keyboard(plan_code: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"💳 Оплатить переводом — {_fmt_price(TARIFF_PRICES[plan_code])}",
        callback_data=SubPayAction(action="buy", value=plan_code),
    )
    builder.button(
        text="↩️ Все тарифы",
        callback_data=SubPayAction(action="list"),
    )
    builder.adjust(1)
    return builder.as_markup()


def sub_paid_keyboard(order_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Я оплатил",
        callback_data=SubPayAction(action="paid", value=order_id),
    )
    builder.button(
        text="↩️ Все тарифы",
        callback_data=SubPayAction(action="list"),
    )
    builder.adjust(1)
    return builder.as_markup()


def sub_admin_keyboard(order_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Выдать доступ",
        callback_data=SubAdminAction(action="approve", order_id=order_id),
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=SubAdminAction(action="reject", order_id=order_id),
    )
    builder.adjust(2)
    return builder.as_markup()


# ─── Витрина тарифов ─────────────────────────────────────────────


@router.message(Command("tariffs"))
@router.message(F.text == "💳 Тарифы и подписка")
async def cmd_tariffs(message: Message) -> None:
    """Показать список тарифов."""
    await message.answer(_TARIFFS_INTRO, reply_markup=tariffs_keyboard())


@router.callback_query(SubPayAction.filter(F.action == "list"))
async def tariffs_list(callback: CallbackQuery) -> None:
    """Вернуться к списку тарифов."""
    await callback.message.edit_text(_TARIFFS_INTRO, reply_markup=tariffs_keyboard())
    await callback.answer()


@router.callback_query(TariffSelect.filter())
async def select_tariff(callback: CallbackQuery, callback_data: TariffSelect) -> None:
    """Карточка тарифа с кнопкой оплаты переводом."""
    plan_code = callback_data.plan_code
    if plan_code not in TARIFF_PRICES:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return
    await callback.message.edit_text(
        f"{TARIFF_DESCRIPTIONS[plan_code]}\n\n"
        f"💳 К оплате: <b>{_fmt_price(TARIFF_PRICES[plan_code])}</b>\n\n"
        f"Оплата переводом на карту. После подтверждения бот автоматически "
        f"выдаст логин и пароль от веб-карты и активирует подписку в боте.",
        reply_markup=tariff_card_keyboard(plan_code),
    )
    await callback.answer()


@router.callback_query(SubPayAction.filter(F.action == "buy"))
async def sub_buy(callback: CallbackQuery, callback_data: SubPayAction) -> None:
    """Создать заказ на подписку и показать реквизиты."""
    plan_code = callback_data.value
    if plan_code not in TARIFF_PRICES:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    # 🛡 Защита от дублей: не создаём второй заказ на тот же тариф
    if orders.has_active_order(callback.from_user.id, plan_code, kind="subscription"):
        await callback.answer(
            "⚠️ У вас уже есть неоплаченный заказ этого тарифа. Проверьте /myorders",
            show_alert=True,
        )
        return

    order = orders.create(
        item_id=plan_code,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        price=TARIFF_PRICES[plan_code],
        title=f"Подписка {TARIFF_TITLES[plan_code]}",
        kind="subscription",
    )
    await callback.message.edit_text(
        f"🧾 <b>Заказ {order['id']}</b>\n"
        f"📦 {order['title']}\n"
        f"💰 К оплате: <b>{fmt_amount(order['price'], order.get('kopecks', 0))}</b>\n\n"
        f"💳 Переведите <b>точно эту сумму</b> на карту:\n"
        f"<code>{settings.SHOP_CARD_NUMBER}</code>\n\n"
        f"❗️ Копейки в сумме — код вашего платежа, по ним мы моментально "
        f"находим перевод. Код заказа: <code>{order['id']}</code>\n\n"
        f"После перевода нажмите кнопку ниже — после проверки оплаты "
        f"бот автоматически пришлёт доступ к карте.",
        reply_markup=sub_paid_keyboard(order["id"]),
    )
    await callback.answer()


@router.callback_query(SubPayAction.filter(F.action == "paid"))
async def sub_paid(callback: CallbackQuery, callback_data: SubPayAction, bot: Bot) -> None:
    """Клиент заявил об оплате — уведомляем админов."""
    order = orders.get(callback_data.value)
    if order is None:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    if order["status"] == STATUS_DELIVERED:
        await callback.answer("Доступ уже выдан ✅", show_alert=True)
        return

    orders.set_status(order["id"], STATUS_CLAIMED)

    username = f"@{order['username']}" if order["username"] else "без username"
    admin_text = (
        f"🔔 <b>Оплата подписки!</b>\n\n"
        f"🧾 Заказ: <code>{order['id']}</code>\n"
        f"📦 {order['title']}\n"
        f"💰 Сумма: <b>{fmt_amount(order['price'], order.get('kopecks', 0))}</b> (копейки — код платежа)\n"
        f"👤 Клиент: {username} (ID: <code>{order['user_id']}</code>)\n\n"
        f"Проверьте перевод с кодом <code>{order['id']}</code> и нажмите "
        f"«Выдать доступ» — бот сам создаст аккаунт NextGIS и отправит данные клиенту."
    )
    notified = 0
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=sub_admin_keyboard(order["id"]))
            notified += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, exc)
    if notified == 0:
        logger.error("ADMIN_IDS пуст — заказ подписки %s зависнет", order["id"])

    await callback.message.edit_text(
        f"⏳ <b>Заявка принята!</b>\n\n"
        f"Заказ <code>{order['id']}</code> передан на проверку оплаты.\n"
        f"Как только перевод подтвердится — бот автоматически пришлёт "
        f"логин и пароль от карты в этот чат.\n\n"
        f"⏱ Проверка оплаты обычно занимает до 30 минут "
        f"(в рабочее время — быстрее).",
    )
    await callback.answer("Заявка отправлена ✅")


# ─── Пробный день ────────────────────────────────────────────


@router.callback_query(SubPayAction.filter(F.action == "trial"))
async def sub_trial(callback: CallbackQuery, bot: Bot) -> None:
    """Заявка на бесплатный пробный день (24 ча��а)."""
    user_id = callback.from_user.id
    profile = profiles.get(user_id) or {}
    if profile.get("trial_used"):
        await callback.answer(
            "Пробный день уже использован. Выберите тариф 😉", show_alert=True
        )
        return

    order = orders.create(
        item_id="trial_24h",
        user_id=user_id,
        username=callback.from_user.username,
        price=0,
        title="🎁 Пробный день (24 часа)",
        kind="trial",
    )
    orders.set_status(order["id"], STATUS_CLAIMED)
    profiles.upsert(user_id, trial_used=True)

    username = f"@{order['username']}" if order["username"] else "без username"
    admin_text = (
        f"🎁 <b>Запрос пробного дня!</b>\n\n"
        f"🧾 Заявка: <code>{order['id']}</code>\n"
        f"👤 Клиент: {username} (ID: <code>{order['user_id']}</code>)\n\n"
        f"Нажмите «Выдать доступ» — бот выдаст аккаунт из пула на 24 часа."
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_text, reply_markup=sub_admin_keyboard(order["id"])
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, exc)

    await callback.message.edit_text(
        "🎁 <b>Заявка на пробный день отправлена!</b>\n\n"
        "Обычно одобряем в течение 30 минут (в рабочее время — быстрее).\n"
        "Логин и пароль придут в этот чат. Доступ действует 24 часа.",
    )
    await callback.answer("Заявка отправлена ✅")


# ─── Админ: выдача доступа ───────────────────────────────────────


@router.callback_query(SubAdminAction.filter(F.action == "approve"))
async def sub_admin_approve(
    callback: CallbackQuery, callback_data: SubAdminAction, bot: Bot, **data
) -> None:
    """Админ подтвердил оплату — активируем подписку и выдаём аккаунт."""
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    order = orders.get(callback_data.order_id)
    if order is None:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    if order["status"] == STATUS_DELIVERED:
        await callback.answer("Уже выдан ✅", show_alert=True)
        return

    # 🎁 Пробный день — выдаём аккаунт из пула на 24 часа
    if order.get("kind") == "trial":
        pool_account = account_pool.acquire(order["user_id"], order["id"])
        if pool_account is None:
            from app.services.waitlist_store import WaitlistStore

            WaitlistStore().add(order["user_id"], order["username"], "trial")
            try:
                await bot.send_message(
                    order["user_id"],
                    "😔 Свободных мест сейчас нет — вы добавлены в лист "
                    "ожидания. Сообщим, как только место освободится!",
                )
            except Exception:  # noqa: BLE001
                pass
            await callback.answer(
                "❌ Пул пуст — кли��нт добавлен в лист ожидания. "
                "Добавьте аккаунт: /add_account логин пароль",
                show_alert=True,
            )
            return
        until = datetime.now(timezone.utc) + timedelta(hours=24)
        try:
            await bot.send_message(
                order["user_id"],
                f"🎁 <b>Пробный день активирован!</b>\n\n"
                f"🌍 Доступ к веб-карте (24 часа):\n"
                f"Сервер: {settings.NEXTGIS_BASE_URL}\n"
                f"👤 Логин: <code>{pool_account['login']}</code>\n"
                f"🔑 Пароль: <code>{pool_account['password']}</code>\n\n"
                f"⏰ Доступ действует до {until.strftime('%d.%m %H:%M')} (UTC).\n"
                f"Понравится — выбирайте тариф: /tariffs 😉",
            )
        except Exception as exc:  # noqa: BLE001
            account_pool.release(pool_account["login"])
            await callback.answer(
                f"❌ Не удалось написать клиенту: {exc}", show_alert=True
            )
            return
        profiles.upsert(
            order["user_id"],
            trial_used=True,
            trial_until=until.isoformat(),
            trial_closed=False,
            trial_login=pool_account["login"],
        )
        orders.set_status(order["id"], STATUS_DELIVERED)
        await callback.message.edit_text(
            callback.message.html_text
            + f"\n\n✅ <b>ПРОБНЫЙ ДОСТУП ВЫДАН</b>\n"
            f"🎫 Аккаунт: <code>{pool_account['login']}</code>. "
            f"Свободно мест: {account_pool.free_count()}.\n"
            f"⏰ Через 24 часа бот сам напомнит сменить пароль и вернёт аккаунт в пул."
        )
        await callback.answer("Пробный доступ выдан ✅")
        return

    plan_code = order["item_id"]
    services = data.get("services") or {}
    notes: list[str] = []

    # 1. Активируем подписку в БД (роль + срок)
    sub_service = services.get("subscription")
    if sub_service:
        try:
            result = await sub_service.activate(order["user_id"], plan_code)
            expires = result.get("expires_at", "")[:10]
            notes.append(f"📅 Подписка активна до: <b>{expires}</b>")
        except Exception as exc:  # noqa: BLE001
            logger.error("О��ибка активации подписки %s: %s", order["id"], exc)
            notes.append("⚠️ Подписку в БД не удалось активировать — сообщим дополнительно.")
    else:
        notes.append("⚠️ Сервис подписок недоступен (dev-режим).")

    # 1.5 Реферальный бонус: +дни пригласившему за оплату друга
    referrer_id = referrals.get_referrer(order["user_id"])
    if referrer_id and sub_service and referrals.try_reward(order["id"]):
        try:
            ref_sub = await sub_service.sub_repo.get_active(referrer_id)
            if ref_sub:
                new_expires = ref_sub.expires_at + timedelta(days=BONUS_DAYS)
                await sub_service.sub_repo.extend(ref_sub.id, new_expires)
                await bot.send_message(
                    referrer_id,
                    f"🎉 Ваш друг оплатил подписку — вам начислено "
                    f"<b>+{BONUS_DAYS} дней</b>! Спасибо, что рекомендуете нас.",
                )
                notes.append(
                    f"🤝 Рефереру <code>{referrer_id}</code> начислено +{BONUS_DAYS} дн."
                )
            else:
                await bot.send_message(
                    referrer_id,
                    f"🎉 Ваш друг оплатил подписку! Бонус +{BONUS_DAYS} дней "
                    f"применим к вашей следующей подписке — напомните при оплате: /help",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Реферальный бонус не начислен: %s", exc)

    # 2. Выдаём доступ: сначала готовый аккаунт из пула, затем NextGIS API
    credentials_block = ""
    pool_account = account_pool.acquire(order["user_id"], order["id"])
    if pool_account:
        credentials_block = (
            f"\n🌍 <b>Ваш доступ к веб-карте:</b>\n"
            f"Сервер: {settings.NEXTGIS_BASE_URL}\n"
            f"👤 Логин: <code>{pool_account['login']}</code>\n"
            f"🔑 Пароль: <code>{pool_account['password']}</code>\n\n"
            f"⚠️ Сохраните логин и пароль — они больше не покажутся."
        )
        notes.append(
            f"🎫 Выдан аккаунт из пула: <code>{pool_account['login']}</code>. "
            f"Свободно мест: {account_pool.free_count()}."
        )
    manager = services.get("account_manager")
    if not credentials_block and manager:
        login = f"tg_{order['user_id']}"
        try:
            result = await manager.create_user(
                login=login,
                display_name=order["username"] or login,
                group_keyname=TARIFF_GROUPS.get(plan_code, "basic_users"),
            )
            credentials_block = (
                f"\n🌍 <b>Ваш доступ к веб-карте:</b>\n"
                f"Сервер: {settings.NEXTGIS_BASE_URL}\n"
                f"👤 Логин: <code>{result['login']}</code>\n"
                f"🔑 Пароль: <code>{result['password']}</code>\n\n"
                f"⚠️ Сохраните логин и пароль — они больше не покажутся."
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка создания NextGIS-аккаунта %s: %s", order["id"], exc)
            notes.append(f"⚠️ NextGIS-аккаунт не создан автоматически: {exc}")
    elif not credentials_block:
        from app.services.waitlist_store import WaitlistStore

        WaitlistStore().add(order["user_id"], order["username"], plan_code)
        notes.append(
            "⚠️ Пул аккаунтов пуст и NextGIS недоступен — выдайте доступ вручную. "
            "Пополнить пул: /add_account логин пароль"
        )
        notes.append(
            "📋 Клиент добавлен в лист ожидания — получит уведомление после /add_account."
        )

    # 3. Сообщение клиенту
    if credentials_block:
        user_text = (
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"📦 {order['title']}\n"
            f"🧾 Заказ: {order['id']}\n"
            f"{credentials_block}\n\n"
            f"Функции бота по вашему тарифу уже активны. Приятной работы! 🎉"
        )
    else:
        user_text = (
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"📦 {order['title']}\n"
            f"🧾 Заказ: {order['id']}\n\n"
            f"Доступ к веб-карте выдаётся — логин и пароль придут "
            f"в этот чат в ближайшее время."
        )
    try:
        await bot.send_message(order["user_id"], user_text)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось отправить доступ клиенту %s: %s", order["user_id"], exc)
        await callback.answer(f"❌ Не удалось написать клиенту: {exc}", show_alert=True)
        return

    orders.set_status(order["id"], STATUS_DELIVERED)
    summary = "\n".join(notes) if notes else "Всё выдано автоматически."
    await callback.message.edit_text(
        callback.message.html_text + f"\n\n✅ <b>ДОСТУП ВЫДАН</b>\n{summary}"
    )
    await callback.answer("Доступ выдан ✅")


@router.callback_query(SubAdminAction.filter(F.action == "reject"))
async def sub_admin_reject(
    callback: CallbackQuery, callback_data: SubAdminAction, bot: Bot
) -> None:
    """Админ отклонил оплату подписки."""
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    order = orders.get(callback_data.order_id)
    if order is None:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    orders.set_status(order["id"], STATUS_REJECTED)
    if order.get("kind") == "trial":
        # Даём возможность запросить пробный день ещё раз
        profiles.upsert(order["user_id"], trial_used=False)
    try:
        await bot.send_message(
            order["user_id"],
            f"❌ По заказу <code>{order['id']}</code> оплата не найдена.\n"
            f"Если вы уверены, что перевод прошёл — напишите нам: /help",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось уведомить клиента %s: %s", order["user_id"], exc)

    await callback.message.edit_text(
        callback.message.html_text + "\n\n❌ <b>ОТКЛОНЕНО</b>"
    )
    await callback.answer("Заказ отклонён")
