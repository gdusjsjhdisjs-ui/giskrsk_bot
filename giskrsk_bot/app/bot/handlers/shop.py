"""🛒 Магазин георесурсов внутри бота.

Сценарий:
1. Покупатель открывает магазин → выбирает товар → «Купить».
2. Бот показывает реквизиты (номер карты) и код заказа.
3. Покупатель переводит деньги и жмёт «✅ Я оплатил».
4. Админы получают уведомление с кнопками «Выдать» / «Отклонить».
5. По «Выдать» бот автоматически отправляет файл покупателю.

Оплата — перевод по номеру карты (ручная проверка админом).
После подключения YooKassa шаги 3–4 заменяются вебхуком.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.filters import IsAdmin
from app.bot.keyboards_data import ShopAction, ShopAdminAction
from app.bot.shop_catalog import SHOP_ITEMS, ShopItem, get_item
from app.core.config import settings
from app.services.shop_orders import (
    STATUS_AWAITING,
    STATUS_CLAIMED,
    STATUS_DELIVERED,
    STATUS_LABELS,
    STATUS_REJECTED,
    ShopOrderStore,
    fmt_amount,
)
from app.services.shop_photos import ShopPhotoStore

logger = logging.getLogger(__name__)

router = Router(name="shop")
orders = ShopOrderStore()
photos = ShopPhotoStore()


# ─── Клавиатуры магазина ─────────────────────────────────────────


def shop_list_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in SHOP_ITEMS:
        builder.button(
            text=f"{item.title} — {item.price:,} ₽".replace(",", " "),
            callback_data=ShopAction(action="item", value=item.id),
        )
    builder.adjust(1)
    return builder.as_markup()


def shop_item_keyboard(item: ShopItem) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"💳 Купить за {item.price:,} ₽".replace(",", " "),
        callback_data=ShopAction(action="buy", value=item.id),
    )
    builder.button(
        text="↩️ К списку товаров",
        callback_data=ShopAction(action="list"),
    )
    builder.adjust(1)
    return builder.as_markup()


def shop_paid_keyboard(order_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Я оплатил",
        callback_data=ShopAction(action="paid", value=order_id),
    )
    builder.button(
        text="↩️ К списку товаров",
        callback_data=ShopAction(action="list"),
    )
    builder.adjust(1)
    return builder.as_markup()


def shop_admin_keyboard(order_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Выдать товар",
        callback_data=ShopAdminAction(action="approve", order_id=order_id),
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=ShopAdminAction(action="reject", order_id=order_id),
    )
    builder.adjust(2)
    return builder.as_markup()


# ─── Витрина ──────────────────────────────────────────────────────

_SHOP_INTRO = (
    "🛒 <b>Магазин георесурсов</b>\n\n"
    "Готовые векторные слои ПЗЗ и QGIS-проекты.\n"
    "После оплаты файл приходит прямо в этот чат.\n\n"
    "Выберите товар:"
)


@router.message(Command("shop"))
@router.message(F.text == "🛒 Магазин")
async def cmd_shop(message: Message) -> None:
    """Открыть витрину магазина."""
    await message.answer(_SHOP_INTRO, reply_markup=shop_list_keyboard())


@router.callback_query(ShopAction.filter(F.action == "list"))
async def shop_list(callback: CallbackQuery) -> None:
    """Показать список товаров."""
    try:
        await callback.message.edit_text(_SHOP_INTRO, reply_markup=shop_list_keyboard())
    except Exception:  # noqa: BLE001 — сообщение с фото нельзя превратить в текст
        await callback.message.delete()
        await callback.message.answer(_SHOP_INTRO, reply_markup=shop_list_keyboard())
    await callback.answer()


@router.callback_query(ShopAction.filter(F.action == "item"))
async def shop_item(callback: CallbackQuery, callback_data: ShopAction) -> None:
    """Карточка товара."""
    item = get_item(callback_data.value)
    if item is None:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    price = f"{item.price:,} ₽".replace(",", " ")
    text = f"📦 <b>{item.title}</b>\n\n{item.description}\n\n💰 Цена: <b>{price}</b>"
    photo_id = photos.get(item.id)
    if photo_id:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo_id, caption=text, reply_markup=shop_item_keyboard(item)
        )
    else:
        try:
            await callback.message.edit_text(text, reply_markup=shop_item_keyboard(item))
        except Exception:  # noqa: BLE001 — предыдущее сообщение было с фото
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=shop_item_keyboard(item))
    await callback.answer()


@router.callback_query(ShopAction.filter(F.action == "buy"))
async def shop_buy(callback: CallbackQuery, callback_data: ShopAction) -> None:
    """Создать заказ и показать реквизиты."""
    item = get_item(callback_data.value)
    if item is None:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return

    # 🛡 Защита от дублей: не создаём второй заказ на тот же товар
    if orders.has_active_order(callback.from_user.id, item.id):
        await callback.answer(
            "⚠️ У вас уже есть активный заказ этого товара. Проверьте /myorders",
            show_alert=True,
        )
        return

    order = orders.create(
        item_id=item.id,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        price=item.price,
        title=item.title,
    )
    pay = fmt_amount(order["price"], order.get("kopecks", 0))
    text = (
        f"🧾 <b>Заказ {order['id']}</b>\n"
        f"📦 {item.title}\n"
        f"💰 К оплате: <b>{pay}</b>\n\n"
        f"💳 Переведите <b>точно эту сумму</b> на карту:\n"
        f"<code>{settings.SHOP_CARD_NUMBER}</code>\n\n"
        f"❗️ Копейки в сумме — код вашего платежа, по ним мы моментально "
        f"находим перевод.\n"
        f"Код заказа: <code>{order['id']}</code>\n\n"
        f"После перевода нажмите кнопку ниже — мы проверим оплату "
        f"и бот автоматически отправит вам файл."
    )
    try:
        await callback.message.edit_text(text, reply_markup=shop_paid_keyboard(order["id"]))
    except Exception:  # noqa: BLE001 — карточка товара была с фото
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=shop_paid_keyboard(order["id"]))
    await callback.answer()


async def send_purchase_offer(message: Message, item_id: str) -> bool:
    """Покупка по диплинку из мини-приложения: /start buy_<item_id>."""
    item = get_item(item_id)
    if item is None:
        return False

    # 🛡 Защита от дублей: не создаём второй заказ на тот же товар
    if orders.has_active_order(message.from_user.id, item.id):
        await message.answer(
            "⚠️ У вас уже есть активный заказ этого товара.\n"
            "Посмотреть и оплатить: /myorders"
        )
        return True

    order = orders.create(
        item_id=item.id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        price=item.price,
        title=item.title,
    )
    pay = fmt_amount(order["price"], order.get("kopecks", 0))
    text = (
        f"\U0001f9fe <b>Заказ {order['id']}</b>\n"
        f"\U0001f4e6 {item.title}\n"
        f"\U0001f4b0 К оплате: <b>{pay}</b>\n\n"
        f"\U0001f4b3 Переведите <b>точно эту сумму</b> на карту:\n"
        f"<code>{settings.SHOP_CARD_NUMBER}</code>\n\n"
        f"\u2757\ufe0f Копейки в сумме — код вашего платежа, по ним мы моментально "
        f"находим перевод.\n"
        f"Код заказа: <code>{order['id']}</code>\n\n"
        f"После перевода нажмите кнопку ниже — мы проверим оплату "
        f"и бот автоматически отправит вам файл."
    )
    await message.answer(text, reply_markup=shop_paid_keyboard(order["id"]))
    return True


@router.callback_query(ShopAction.filter(F.action == "paid"))
async def shop_paid(callback: CallbackQuery, callback_data: ShopAction, bot: Bot) -> None:
    """Покупатель заявил об оплате — уведомляем админов."""
    order = orders.get(callback_data.value)
    if order is None:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    if order["status"] == STATUS_DELIVERED:
        await callback.answer("Заказ уже выдан ✅", show_alert=True)
        return

    orders.set_status(order["id"], STATUS_CLAIMED)

    username = f"@{order['username']}" if order["username"] else "без username"
    price = fmt_amount(order["price"], order.get("kopecks", 0))
    admin_text = (
        f"🔔 <b>Новая оплата в магазине!</b>\n\n"
        f"🧾 Заказ: <code>{order['id']}</code>\n"
        f"📦 Товар: {order['title']}\n"
        f"💰 Сумма: <b>{price}</b> (копейки — код платежа)\n"
        f"👤 Покупатель: {username} (ID: <code>{order['user_id']}</code>)\n\n"
        f"Проверьте поступление перевода с кодом <code>{order['id']}</code> "
        f"и нажмите кнопку."
    )
    notified = 0
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_text, reply_markup=shop_admin_keyboard(order["id"])
            )
            notified += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось уведомить админа %s: %s", admin_id, exc)

    if notified == 0:
        logger.error("ADMIN_IDS пуст или админы недоступны — заказ %s зависнет", order["id"])

    await callback.message.edit_text(
        f"⏳ <b>Заявка принята!</b>\n\n"
        f"Заказ <code>{order['id']}</code> передан на проверку оплаты.\n"
        f"Как только перевод подтвердится — бот автоматически "
        f"отправит файл в этот чат.\n\n"
        f"⏱ Проверка оплаты обычно занимает до 30 минут "
        f"(в рабочее время — быстрее).",
    )
    await callback.answer("Заявка отправлена ✅")


# ─── Админская часть ─────────────────────────────────────────────


@router.callback_query(ShopAdminAction.filter(F.action == "approve"))
async def shop_admin_approve(
    callback: CallbackQuery, callback_data: ShopAdminAction, bot: Bot
) -> None:
    """Админ подтвердил оплату — отправляем файл покупателю."""
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

    item = get_item(order["item_id"])
    if item is None:
        await callback.answer("❌ Товар удалён из каталога", show_alert=True)
        return

    file_path = Path(item.file_path)
    if not file_path.exists():
        await callback.answer(
            f"❌ Файл не найден: {item.file_path}", show_alert=True
        )
        return

    try:
        await bot.send_document(
            order["user_id"],
            FSInputFile(file_path),
            caption=(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"📦 {item.title}\n"
                f"🧾 Заказ: {order['id']}\n\n"
                f"Спасибо за покупку! По вопросам — /help"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка отправки файла по заказу %s: %s", order["id"], exc)
        await callback.answer(f"❌ Ошибка отправки: {exc}", show_alert=True)
        return

    orders.set_status(order["id"], STATUS_DELIVERED)
    await callback.message.edit_text(
        callback.message.html_text + "\n\n✅ <b>ВЫДАНО</b>"
    )
    await callback.answer("Файл отправлен покупателю ✅")


@router.callback_query(ShopAdminAction.filter(F.action == "reject"))
async def shop_admin_reject(
    callback: CallbackQuery, callback_data: ShopAdminAction, bot: Bot
) -> None:
    """Админ отклонил заказ."""
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("⛔ Только для админов", show_alert=True)
        return

    order = orders.get(callback_data.order_id)
    if order is None:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    orders.set_status(order["id"], STATUS_REJECTED)
    try:
        await bot.send_message(
            order["user_id"],
            f"❌ По заказу <code>{order['id']}</code> оплата не найдена.\n"
            f"Если вы уверены, что перевод прошёл — напишите нам: /help",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось уведомить покупателя %s: %s", order["user_id"], exc)

    await callback.message.edit_text(
        callback.message.html_text + "\n\n❌ <b>ОТКЛОНЕНО</b>"
    )
    await callback.answer("Заказ отклонён")


@router.message(Command("orders"), IsAdmin())
async def cmd_orders(message: Message) -> None:
    """Последние заказы (для админа)."""
    recent = orders.list_recent(limit=10)
    if not recent:
        await message.answer("🛒 Заказов пока нет.")
        return
    lines = ["🛒 <b>Последние заказы:</b>\n"]
    for o in recent:
        status = STATUS_LABELS.get(o["status"], o["status"])
        username = f"@{o['username']}" if o["username"] else o["user_id"]
        price = f"{o['price']:,} ₽".replace(",", " ")
        lines.append(
            f"<code>{o['id']}</code> | {o['title']} | {price} | {username} | {status}"
        )
    await message.answer("\n".join(lines))


# ─── Админ: картинки товаров ─────────────────────────────────


@router.message(IsAdmin(), F.photo, F.caption, F.caption.startswith("/set_photo"))
async def cmd_set_photo(message: Message) -> None:
    """Прикрепить картинку: фото с подписью «/set_photo id_товара»."""
    parts = (message.caption or "").split()
    if len(parts) != 2:
        await message.answer(
            "Отправьте фото с подписью: <code>/set_photo id_товара</code>\n"
            "Список товаров и их id: /photos"
        )
        return
    item = get_item(parts[1])
    if item is None:
        await message.answer("❌ Товар с таким id не найден. Список: /photos")
        return
    photos.set(item.id, message.photo[-1].file_id)
    await message.answer(
        f"✅ Картинка прикреплена к товару «{item.title}».\n"
        f"Теперь она показывается в карточке товара в магазине."
    )


@router.message(Command("photos"), IsAdmin())
async def cmd_photos(message: Message) -> None:
    """Список товаров и их картинок (для админа)."""
    lines = ["🖼 <b>Картинки това��ов:</b>\n"]
    for item in SHOP_ITEMS:
        mark = "📷 есть" if photos.get(item.id) else "➖ нет"
        lines.append(f"{mark} | <code>{item.id}</code> — {item.title}")
    lines.append(
        "\nЧтобы добавить/заменить картинку: отправьте фото "
        "с подписью <code>/set_photo id_товара</code>"
    )
    await message.answer("\n".join(lines))
