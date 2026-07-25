"""Клип-заказы: покупка GeoJSON по выделенной области карты.

Поток:
  1. Пользователь рисует bbox в мини-приложении
  2. Webapp отправляет web_app_data в бот
  3. Бот показывает область + цену + кнопку Оплатить
  4. После админа — бот клипает и отправляет файл
"""

from __future__ import annotations

import json
import logging

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery, FSInputFile, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

from app.core.config import settings
from app.services.clip_service import (
    CLIP_LAYERS, calculate_clip_price, do_clip,
    format_price_msg, get_clip_output_path,
)
from app.services.shop_orders import (
    STATUS_CLAIMED, STATUS_DELIVERED, ShopOrderStore, fmt_amount,
)

logger = logging.getLogger(__name__)
router = Router(name="clip_order")
_store = ShopOrderStore()


# ─── Получение bbox из мини-приложения ───────────────────────

@router.message(F.web_app_data)
async def handle_webapp_data(message: Message) -> None:
    """Обрабатывает данные из мини-приложения."""
    raw = getattr(message.web_app_data, "data", None)
    if not raw:
        return
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return

    if data.get("action") == "clip_order":
        await _handle_clip_request(message, data)


async def _handle_clip_request(message: Message, data: dict) -> None:
    bbox_raw = data.get("bbox")
    layer_id = data.get("layer", "pzz_krsk")

    if not bbox_raw or len(bbox_raw) != 4:
        await message.answer("⚠️ Некорректная область. Выделите прямоугольник снова.")
        return
    if layer_id not in CLIP_LAYERS:
        await message.answer("⚠️ Неизвестный слой. Выберите слой на карте.")
        return

    try:
        bbox = tuple(float(x) for x in bbox_raw)
    except (TypeError, ValueError):
        await message.answer("⚠️ Ошибка координат.")
        return

    # Защита от дублей
    existing = [
        o for o in _store.list_recent(limit=200)
        if o.get("user_id") == message.from_user.id
        and o.get("kind") == "clip"
        and o.get("status") in ("awaiting_payment", "payment_claimed")
        and (o.get("meta") or {}).get("layer_id") == layer_id
    ]
    if existing:
        await message.answer(
            "⏳ У вас уже есть активный клип-заказ для этого слоя.\n"
            "Дождитесь обработки или отмените: /myorders"
        )
        return

    from tools.clip_geodata import haversine_km2
    area_km2 = haversine_km2(*bbox)

    if area_km2 < 0.01:
        await message.answer("⚠️ Область слишком маленькая. Выделите большую зону.")
        return

    layer = CLIP_LAYERS[layer_id]
    if area_km2 > layer.get("area_km2", 9999) * 0.8:
        shop_fmt = f"{layer['shop_price']:,}".replace(",", " ")
        await message.answer(
            f"⚠️ Выделенная область очень большая ({area_km2:.0f} км²).\n"
            f"Дешевле купить полный файл «{layer['name']}» за {shop_fmt} ₽\n"
            f"в магазине: /shop"
        )
        return

    price = calculate_clip_price(area_km2, layer_id)
    price_msg = format_price_msg(area_km2, layer_id, price)
    bbox_cb = ",".join(str(round(x, 6)) for x in bbox)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Оплатить {price:,} ₽".replace(",", " "),
            callback_data=f"clippay:{layer_id}:{bbox_cb}:{price}",
        )],
        [
            InlineKeyboardButton(text="✏️ Перерисовать", callback_data="clip_redraw"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="clip_cancel_ui"),
        ],
    ])

    await message.answer(
        f"✂️ <b>Клип «{layer['name']}»</b>\n\n"
        f"{price_msg}\n\n"
        f"Нажмите «Оплатить» и переведите точную сумму на карту.",
        reply_markup=kb,
    )


# ─── Оплата ────────────────────────────────────────────

@router.callback_query(F.data.startswith("clippay:"))
async def clip_pay(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    layer_id = parts[1]
    bbox_str = parts[2]
    price = int(parts[3])
    bbox = tuple(float(x) for x in bbox_str.split(","))

    from tools.clip_geodata import haversine_km2
    area_km2 = haversine_km2(*bbox)
    layer = CLIP_LAYERS.get(layer_id, {})
    layer_name = layer.get("name", layer_id)
    username = callback.from_user.username or str(callback.from_user.id)

    order = _store.create(
        item_id=f"clip_{layer_id}",
        user_id=callback.from_user.id,
        username=username,
        price=price,
        title=f"Клип «{layer_name}» · {area_km2:.1f} км²",
        kind="clip",
    )
    _store.set_meta(order["id"], {"bbox": list(bbox), "layer_id": layer_id})

    amount_str = fmt_amount(price, order.get("kopecks", 0))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Я оплатил(а)",
            callback_data=f"clipclaimed:{order['id']}",
        )],
        [InlineKeyboardButton(
            text="❌ Отменить заказ",
            callback_data=f"cancel_order:{order['id']}",
        )],
    ])
    await callback.message.edit_text(
        f"💳 <b>Оплата клипа «{layer_name}»</b>\n\n"
        f"Сумма: <b>{amount_str}</b>\n"
        f"Переведите на карту:\n"
        f"📋 <code>{settings.SHOP_CARD_NUMBER}</code>\n\n"
        f"⚠️ <b>Переводите ТОЧНУЮ сумму с копейками</b> —\n"
        f"по ним мы найдём ваш платёж.\n\n"
        f"После перевода нажмите «Я оплатил(а)».",
        reply_markup=kb,
    )
    await callback.answer()


# ─── Пользователь заявил об оплате ───────────────────────

@router.callback_query(F.data.startswith("clipclaimed:"))
async def clip_claimed(callback: CallbackQuery, bot: Bot) -> None:
    order_id = callback.data.split(":", 1)[1]
    order = _store.set_status(order_id, STATUS_CLAIMED)
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    meta = order.get("meta") or {}
    layer_id = meta.get("layer_id", "?")
    bbox = meta.get("bbox", [])
    layer_name = CLIP_LAYERS.get(layer_id, {}).get("name", layer_id)
    amount_str = fmt_amount(order["price"], order.get("kopecks", 0))
    bbox_str = ", ".join(f"{x:.4f}" for x in bbox) if bbox else "?"

    kb_admin = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Выдать клип",
            callback_data=f"clipapprove:{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"clipreject:{order_id}",
        ),
    ]])

    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✂️ <b>Клип-заказ #{order_id}</b>\n\n"
                f"👤 @{order.get('username', '?')}\n"
                f"🗺 Слой: {layer_name}\n"
                f"📐 BBox: {bbox_str}\n"
                f"💰 Сумма: <b>{amount_str}</b>\n\n"
                f"Проверьте перевод и подтвердите.",
                reply_markup=kb_admin,
            )
        except Exception:
            pass

    await callback.message.edit_text(
        "✅ Заявка отправлена!\n\n"
        "Как только платёж проверен — бот пришлёт вам файл.\n"
        "Обычно это занимает несколько минут."
    )
    await callback.answer()


# ─── Админ: выдать / отклонить ───────────────────────

@router.callback_query(F.data.startswith("clipapprove:"))
async def clip_approve(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return

    order_id = callback.data.split(":", 1)[1]
    order = _store.get(order_id)
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    meta = order.get("meta") or {}
    layer_id = meta.get("layer_id")
    bbox = meta.get("bbox")
    if not layer_id or not bbox:
        await callback.answer("Нет данных bbox.", show_alert=True)
        return

    await callback.message.edit_text(f"⏳ Выполняю клиппинг #{order_id}…")

    try:
        stats = await do_clip(order_id, layer_id, tuple(bbox))
    except FileNotFoundError as e:
        await callback.message.edit_text(f"❌ {e}")
        return
    except Exception as e:
        logger.exception("Клип провалился: order=%s", order_id)
        await callback.message.edit_text(
            f"❌ Ошибка клиппинга: {e}"
        )
        return

    if stats["feature_count"] == 0:
        await callback.message.edit_text(
            f"⚠️ В области нет объектов ПЗЗ.\n"
            f"Свяжитесь с клиентом для возврата / перевыбора."
        )
        return

    output_path = get_clip_output_path(order_id, layer_id)
    layer_name = CLIP_LAYERS.get(layer_id, {}).get("name", layer_id)
    filename = f"pzz_clip_{layer_id}_{order_id}.geojson"

    support = f"@{settings.SUPPORT_USERNAME}" if settings.SUPPORT_USERNAME else "в поддержку"

    try:
        await bot.send_document(
            chat_id=order["user_id"],
            document=FSInputFile(output_path, filename=filename),
            caption=(
                f"📁 <b>Ваш клип готов!</b>\n\n"
                f"🗺 Слой: {layer_name}\n"
                f"📦 Объектов: {stats['feature_count']}\n"
                f"📐 Площадь: {stats['area_km2']} км²\n"
                f"💾 Размер: {stats['file_size_kb']} КБ\n\n"
                f"Файл совместим с QGIS, ArcGIS, MapInfo.\n"
                f"Если вопросы — пишите {support} 🙏"
            ),
        )
    except Exception as e:
        logger.error("Не удалось отправить клип: %s", e)
        await callback.message.edit_text(f"❌ Не удалось отправить файл: {e}")
        return

    _store.set_status(order_id, STATUS_DELIVERED)
    try:
        output_path.unlink(missing_ok=True)
    except OSError:
        pass

    await callback.message.edit_text(
        f"✅ Клип #{order_id} выдан!\n"
        f"📦 {stats['feature_count']} объектов · {stats['file_size_kb']} КБ"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("clipreject:"))
async def clip_reject(callback: CallbackQuery, bot: Bot) -> None:
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return
    order_id = callback.data.split(":", 1)[1]
    order = _store.set_status(order_id, "rejected")
    if order:
        support = f"@{settings.SUPPORT_USERNAME}" if settings.SUPPORT_USERNAME else "в поддержку"
        try:
            await bot.send_message(
                order["user_id"],
                f"❌ Платёж по клип-заказу #{order_id} не найден.\n\n"
                f"Если вы действительно оплатили — напишите {support}."
            )
        except Exception:
            pass
    await callback.message.edit_text(f"❌ Заказ #{order_id} отклонён.")
    await callback.answer()


@router.callback_query(F.data == "clip_redraw")
async def clip_redraw(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "✏️ Откройте карту и выделите другую область: /app"
    )
    await callback.answer()


@router.callback_query(F.data == "clip_cancel_ui")
async def clip_cancel_ui(callback: CallbackQuery) -> None:
    await callback.message.edit_text("❌ Запрос отменён. Для нового выделения откройте /app")
    await callback.answer()
