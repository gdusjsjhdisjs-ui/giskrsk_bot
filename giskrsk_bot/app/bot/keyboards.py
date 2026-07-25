from typing import Any

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.bot.keyboards_data import (
    BatchAction,
    MainMenuAction,
    ParcelAction,
    PaymentConfirm,
    ProfileAction,
    SubPayAction,
    SubscriptionAction,
    TariffSelect,
    TrackingAction,
)


# ─── Главное меню (Reply) ────────────────────────────────────────────────


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔍 Проверить участок"),
    )
    builder.row(
        KeyboardButton(text="💳 Тарифы и подписка"),
    )
    builder.row(
        KeyboardButton(text="📋 Мои отслеживания"),
    )
    builder.row(
        KeyboardButton(text="👤 Профиль"),
    )
    builder.row(
        KeyboardButton(text="🤖 AI-консультант"),
        KeyboardButton(text="🔄 Координаты → GeoJSON"),
    )
    builder.row(
        KeyboardButton(text="🛒 Магазин"),
    )
    builder.row(
        KeyboardButton(text="❓ Помощь"),
    )
    return builder.as_markup(resize_keyboard=True)


# ─── Выбор способа проверки участка ─────────────────────────────────────


def parcel_search_keyboard() -> InlineKeyboardMarkup:
    """Способы ввода данных участка."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔢 По кадастровому номеру",
        callback_data=ParcelAction(action="by_cadnum"),
    )
    builder.button(
        text="📍 Отправить геопозицию",
        callback_data=ParcelAction(action="by_geo"),
    )
    builder.button(
        text="↩️ Назад",
        callback_data=MainMenuAction(action="main_menu"),  # check_parcel был в мм
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Тарифы ──────────────────────────────────────────────────────────────

_TARIFF_NAMES: dict[str, tuple[str, str]] = {
    "basic_30d": ("Basic 30 дней", "2 990 ₽/мес"),
    "pro_30d": ("Pro 30 дней", "4 990 ₽/мес"),
    "pro_90d": ("Pro 90 дней", "9 900 ₽ (3 300 ₽/мес)"),
    "year": ("Pro 12 мес", "24 900 ₽ (2 075 ₽/мес)"),
}


def tariffs_keyboard(plan_code: str | None = None) -> InlineKeyboardMarkup:
    """Тарифы на выбор. Если plan_code передан — выделяет его ✅."""
    builder = InlineKeyboardBuilder()
    for code, (name, price) in _TARIFF_NAMES.items():
        label = f"✅ {name} — {price}" if code == plan_code else f"{name} — {price}"
        builder.button(
            text=label,
            callback_data=TariffSelect(plan_code=code),
        )
    builder.button(
        text="🎁 Пробный день — бесплатно",
        callback_data=SubPayAction(action="trial"),
    )
    builder.button(
        text="↩️ Назад",
        callback_data=MainMenuAction(action="tariffs"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Подтверждение оплаты ───────────────────────────────────────────────


def payment_keyboard(confirmation_url: str, amount: int = 0) -> InlineKeyboardMarkup:
    """Кнопки оплаты и проверки статуса."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"💳 Оплатить {amount}₽",
        url=confirmation_url,
    )
    builder.button(
        text="🔄 Проверить статус платежа",
        callback_data=PaymentConfirm(payment_id="", action="pay"),
    )
    builder.button(
        text="↩️ Назад",
        callback_data=MainMenuAction(action="my_subscription"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Управление подпиской ───────────────────────────────────────────────


def subscription_keyboard(status: str) -> InlineKeyboardMarkup:
    """Кнопки в зависимости от статуса подписки."""
    builder = InlineKeyboardBuilder()
    if status == "active":
        builder.button(
            text="🔄 Продлить",
            callback_data=SubscriptionAction(action="extend"),
        )
        builder.button(
            text="📦 Сменить тариф",
            callback_data=SubscriptionAction(action="change_plan"),
        )
    else:
        builder.button(
            text="💳 Купить подписку",
            callback_data=TariffSelect(plan_code="basic_30d"),
        )
    builder.button(
        text="↩️ Главное меню",
        callback_data=MainMenuAction(action="main_menu"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Список отслеживаемых ────────────────────────────────────────────────


def tracking_list_keyboard(objects: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """Список отслеживаемых участков с кнопками управления."""
    builder = InlineKeyboardBuilder()
    for obj in objects:
        cadnum = obj.get("cadnum", "")
        # Кнопка: 🔔/🔕 {cadnum} — toggle уведомлений
        bell = "🔕" if obj.get("notify", False) else "🔔"
        builder.button(
            text=f"{bell} {cadnum}",
            callback_data=TrackingAction(action="toggle", track_id=cadnum),
        )
        builder.button(
            text=f"❌ {cadnum}",
            callback_data=TrackingAction(action="remove", track_id=cadnum),
        )
        builder.adjust(2)
    builder.button(
        text="➕ Добавить участок",
        callback_data=TrackingAction(action="add"),
    )
    builder.button(
        text="↩️ Назад",
        callback_data=MainMenuAction(action="main_menu"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Результат проверки участка ──────────────────────────────────────────


def parcel_result_keyboard(cadnum: str) -> InlineKeyboardMarkup:
    """Действия после проверки участка."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗺️ Открыть на карте",
        url="https://maplive.nextgis.com",  # будет заменено на реальный URL
    )
    builder.button(
        text="🔔 Отслеживать изменения",
        callback_data=TrackingAction(action="add", track_id=cadnum),
    )
    builder.button(
        text="📋 Пакетная проверка",
        callback_data=BatchAction(action="upload"),
    )
    builder.button(
        text="↩️ Назад",
        callback_data=MainMenuAction(action="main_menu"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Админ-панель ────────────────────────────────────────────────────────


def admin_keyboard() -> InlineKeyboardMarkup:
    """Панель администратора."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📊 Статистика",
        callback_data=MainMenuAction(action="stats"),
    )
    builder.button(
        text="👥 Пользователи",
        callback_data=MainMenuAction(action="users"),
    )
    builder.button(
        text="📢 Рассылка",
        callback_data=MainMenuAction(action="broadcast"),
    )
    builder.button(
        text="↩️ Назад",
        callback_data=MainMenuAction(action="main_menu"),
    )
    builder.adjust(1)
    return builder.as_markup()


# ─── Вспомогательные ─────────────────────────────────────────────────────


def back_keyboard(action: str = "main_menu") -> InlineKeyboardMarkup:
    """Одна кнопка «Назад» с произвольным callback_data."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="↩️ Назад",
        callback_data=MainMenuAction(action=action),
    )
    return builder.as_markup(as_message=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка отмены для FSM-состояний."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)
