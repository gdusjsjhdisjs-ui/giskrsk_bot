"""Проверка участка по кадастровому номеру или геопозиции."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards import parcel_search_keyboard, parcel_result_keyboard, cancel_keyboard, back_keyboard
from app.bot.keyboards_data import ParcelAction
from app.bot.states import ParcelInput
from app.services.parcel_service import ParcelService

router = Router(name="parcel")


def get_parcel_service(data: dict) -> ParcelService:
    """Получить сервис из data (пробрасывается через middleware)."""
    return data.get("services", {}).get("parcel")


@router.message(Command("parcel"))
@router.message(F.text == "🔍 Проверить участок")
async def cmd_parcel(message: Message) -> None:
    """Начать проверку участка."""
    await message.answer(
        "🔍 Выберите способ проверки:",
        reply_markup=parcel_search_keyboard(),
    )


@router.callback_query(ParcelAction.filter(F.action == "by_cadnum"))
async def parcel_by_cadnum(callback: CallbackQuery, state: FSMContext) -> None:
    """Запросить ввод кадастрового номера."""
    await callback.message.edit_text(
        "📝 Введите кадастровый номер участка.\n\n"
        "Пример: <code>24:11:0330102:814</code>\n\n"
        "Или нажмите «Отмена» чтобы вернуться.",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(ParcelInput.waiting_for_cadnum)
    await callback.answer()


@router.callback_query(ParcelAction.filter(F.action == "by_geo"))
async def parcel_by_geo(callback: CallbackQuery, state: FSMContext) -> None:
    """Запросить геопозицию."""
    await callback.message.edit_text(
        "📍 Отправьте геопозицию (скрепка → Геолокация).\n\n"
        "Или нажмите «Отмена» чтобы вернуться.",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(ParcelInput.waiting_for_location)
    await callback.answer()


@router.message(ParcelInput.waiting_for_cadnum)
async def handle_cadnum_input(message: Message, state: FSMContext, **data) -> None:
    """Обработать ввод кадастрового номера."""
    await state.clear()
    raw = message.text or ""

    service = get_parcel_service(data)
    if not service:
        await message.answer("❌ Сервис недоступен. Попробуйте позже.")
        return

    try:
        parcel = await service.search_by_cadnum(raw)
    except Exception as e:
        await message.answer(
            f"❌ {e}\n\nПроверьте формат: <code>24:11:0330102:814</code>",
            reply_markup=back_keyboard("check_parcel"),
        )
        return

    category = parcel.category or "—"
    vri = parcel.permitted_use or "—"
    area = f"{parcel.area_m2:,.0f} м²" if parcel.area_m2 else "—"
    cad_value = f"{parcel.cadastral_value:,.0f} ₽" if parcel.cadastral_value else "—"

    await message.answer(
        f"📍 <b>Участок {parcel.cadastral_number}</b>\n\n"
        f"🏗️ Категория: {category}\n"
        f"📋 ВРИ: {vri}\n"
        f"📐 Площадь: {area}\n"
        f"💰 Кадастровая стоимость: {cad_value}\n\n"
        f"🔍 Данные Росреестра (ПКК)",
        reply_markup=parcel_result_keyboard(parcel.cadastral_number),
    )


@router.message(ParcelInput.waiting_for_location)
async def handle_geo_input(message: Message, state: FSMContext, **data) -> None:
    """Обработать геопозицию."""
    await state.clear()

    if not message.location:
        await message.answer("❌ Пожалуйста, отправьте геопозицию.", reply_markup=cancel_keyboard())
        return

    lon = message.location.longitude
    lat = message.location.latitude

    service = get_parcel_service(data)
    if not service:
        await message.answer("❌ Сервис недоступен. Попробуйте позже.")
        return

    try:
        zones = await service.identify_by_point(lon, lat)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=back_keyboard("check_parcel"))
        return

    if not zones:
        await message.answer(
            f"📍 Координаты: {lat:.6f}, {lon:.6f}\n\n"
            "❌ Зона ПЗЗ не определена для данной точки.",
            reply_markup=back_keyboard("check_parcel"),
        )
        return

    lines = [f"📍 Координаты: {lat:.6f}, {lon:.6f}\n"]
    for i, zone in enumerate(zones[:3], 1):
        fields = zone.get("fields") or zone.get("properties") or {}
        code = fields.get("zone_code") or fields.get("zone") or "—"
        name = fields.get("zone_name") or fields.get("zone_description") or "—"
        lines.append(f"{i}. 🏗️ <b>{code}</b> — {name}")

    await message.answer("\n".join(lines), reply_markup=back_keyboard("check_parcel"))


@router.callback_query(ParcelAction.filter(F.action == "retry"))
async def parcel_retry(callback: CallbackQuery) -> None:
    """Повторить проверку."""
    await callback.message.edit_text(
        "🔍 Выберите способ проверки:",
        reply_markup=parcel_search_keyboard(),
    )
    await callback.answer()
