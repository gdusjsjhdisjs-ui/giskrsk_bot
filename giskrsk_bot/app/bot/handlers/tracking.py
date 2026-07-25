"""Хендлер отслеживания изменений участков."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards import tracking_list_keyboard, back_keyboard, cancel_keyboard
from app.bot.keyboards_data import TrackingAction
from app.bot.states import ParcelInput
from app.core.exceptions import InvalidCadastralNumberError
from app.repositories.tracked_object_repo import TrackedObjectRepo
from app.services.parcel_service import normalize_cadnum

router = Router(name="tracking")


@router.message(Command("tracking"))
@router.message(F.text == "📋 Мои отслеживания")
async def cmd_tracking(message: Message, **data) -> None:
    """Показать список отслеживаемых участков."""
    repo: TrackedObjectRepo | None = data.get("repos", {}).get("tracked_object")
    if not repo:
        await message.answer("❌ Сервис недоступен.")
        return

    objects = await repo.get_user_tracked(message.from_user.id)
    if not objects:
        await message.answer(
            "📋 <b>Отслеживания</b>\n\n"
            "У вас нет отслеживаемых участков.\n\n"
            "Чтобы добавить — проверьте участок и нажмите 🔔 Отслеживать изменения.",
            reply_markup=back_keyboard("main_menu"),
        )
        return

    obj_list = [
        {
            "id": str(o.id),
            "cadastral_number": o.cadastral_number,
            "active": o.active,
        }
        for o in objects
    ]
    await message.answer(
        "📋 <b>Отслеживаемые участки:</b>",
        reply_markup=tracking_list_keyboard(obj_list),
    )


@router.callback_query(TrackingAction.filter(F.action == "add"))
async def tracking_add(callback: CallbackQuery, **data) -> None:
    """Добавить участок в отслеживание."""
    # Берём кадастровый номер из callback_data или запрашиваем
    repo: TrackedObjectRepo | None = data.get("repos", {}).get("tracked_object")
    if not repo:
        await callback.answer("❌ Сервис недоступен", show_alert=True)
        return

    cadnum = callback.data.split(":")[-1]  # fallback
    if cadnum and len(cadnum) > 5:
        try:
            if await repo.exists(callback.from_user.id, cadnum):
                await callback.answer("✅ Уже отслеживается!", show_alert=True)
                return
            await repo.add(callback.from_user.id, cadnum)
            await callback.answer("✅ Участок добавлен в отслеживание!", show_alert=True)
        except Exception as e:
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
    else:
        await callback.answer("⏳ Эта функция будет доработана", show_alert=True)


@router.callback_query(TrackingAction.filter(F.action == "remove"))
async def tracking_remove(callback: CallbackQuery, **data) -> None:
    """Удалить отслеживание."""
    repo: TrackedObjectRepo | None = data.get("repos", {}).get("tracked_object")
    if not repo:
        await callback.answer("❌ Сервис недоступен", show_alert=True)
        return

    track_id_str = callback.data.split(":")[-1]
    from uuid import UUID
    try:
        await repo.remove(UUID(track_id_str))
        await callback.answer("✅ Удалено!", show_alert=True)
        # Обновляем список
        objects = await repo.get_user_tracked(callback.from_user.id)
        obj_list = [{"id": str(o.id), "cadastral_number": o.cadastral_number, "active": o.active} for o in objects]
        if obj_list:
            await callback.message.edit_text("📋 <b>Отслеживаемые участки:</b>", reply_markup=tracking_list_keyboard(obj_list))
        else:
            await callback.message.edit_text("📋 Список отслеживания пуст.", reply_markup=back_keyboard("main_menu"))
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(TrackingAction.filter(F.action == "toggle"))
async def tracking_toggle(callback: CallbackQuery, **data) -> None:
    """Вкл/выкл уведомления для участка."""
    repo: TrackedObjectRepo | None = data.get("repos", {}).get("tracked_object")
    if not repo:
        await callback.answer("❌ Сервис недоступен", show_alert=True)
        return

    track_id_str = callback.data.split(":")[-1]
    from uuid import UUID
    try:
        new_state = await repo.toggle(UUID(track_id_str))
        status = "🔔 Вкл" if new_state else "🔕 Выкл"
        await callback.answer(f"Уведомления: {status}", show_alert=True)
        # Обновляем список
        objects = await repo.get_user_tracked(callback.from_user.id)
        obj_list = [{"id": str(o.id), "cadastral_number": o.cadastral_number, "active": o.active} for o in objects]
        if obj_list:
            await callback.message.edit_text("📋 <b>Отслеживаемые участки:</b>", reply_markup=tracking_list_keyboard(obj_list))
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(TrackingAction.filter(F.action == "list"))
async def tracking_list(callback: CallbackQuery, **data) -> None:
    """Показать список отслеживаний."""
    repo: TrackedObjectRepo | None = data.get("repos", {}).get("tracked_object")
    if not repo:
        await callback.answer("❌ Сервис недоступен", show_alert=True)
        return

    objects = await repo.get_user_tracked(callback.from_user.id)
    obj_list = [{"id": str(o.id), "cadastral_number": o.cadastral_number, "active": o.active} for o in objects]
    if obj_list:
        await callback.message.edit_text("📋 <b>Отслеживаемые участки:</b>", reply_markup=tracking_list_keyboard(obj_list))
    else:
        await callback.message.edit_text("📋 Список отслеживания пуст.", reply_markup=back_keyboard("main_menu"))
    await callback.answer()
