"""Хендлер пакетной проверки (CSV)."""

from __future__ import annotations

import asyncio
import io

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from app.bot.keyboards import cancel_keyboard, back_keyboard
from app.bot.keyboards_data import BatchAction
from app.bot.states import BatchUpload
from app.services.batch_service import BatchService

router = Router(name="batch")


def get_batch_service(data: dict) -> BatchService | None:
    return data.get("services", {}).get("batch")


@router.message(Command("batch"))
async def cmd_batch(message: Message, state: FSMContext) -> None:
    """Начать пакетную проверку."""
    await message.answer(
        "📋 <b>Пакетная проверка</b>\n\n"
        "Загрузите CSV-файл со списком кадастровых номеров.\n\n"
        "Формат: один номер на строку или в первой колонке.\n"
        "Пример:\n"
        "<code>24:11:0330102:814</code>\n"
        "<code>24:11:0330102:815</code>\n\n"
        "Максимум: 100 номеров за раз.",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(BatchUpload.waiting_for_file)


@router.message(BatchUpload.waiting_for_file, F.document)
async def handle_batch_file(message: Message, state: FSMContext, bot: Bot, **data) -> None:
    """Обработать загруженный CSV."""
    await state.clear()

    service = get_batch_service(data)
    if not service:
        await message.answer("❌ Сервис недоступен.")
        return

    # Скачиваем файл
    try:
        file = await bot.download(message.document)
        content = file.read()
    except Exception as e:
        await message.answer(f"❌ Ошибка загрузки файла: {e}", reply_markup=back_keyboard("batch"))
        return

    # Парсим CSV
    try:
        cadnums = await service.parse_csv(content)
    except Exception as e:
        await message.answer(f"❌ Ошибка парсинга CSV: {e}", reply_markup=back_keyboard("batch"))
        return

    if not cadnums:
        await message.answer(
            "❌ Не найдено кадастровых номеров в файле.",
            reply_markup=back_keyboard("batch"),
        )
        return

    if len(cadnums) > 100:
        await message.answer(f"❌ Слишком много номеров ({len(cadnums)}). Максимум 100.")
        return

    # Создаём задачу
    try:
        job_id = await service.create_job(message.from_user.id, cadnums)
    except Exception as e:
        await message.answer(f"❌ Ошибка создания задачи: {e}")
        return

    await message.answer(
        f"✅ Файл загружен. Найдено номеров: {len(cadnums)}\n"
        f"🆔 ID задачи: {job_id}\n\n"
        f"⏳ Обработка запущена...",
        reply_markup=back_keyboard("batch"),
    )

    # Обработка в ФОНЕ — хендлер не блокирует бота на время проверки
    # сотни номеров (раньше бот «вис» до конца обработки CSV)
    asyncio.create_task(_run_batch_job(message, service, job_id))


async def _run_batch_job(message: Message, service: BatchService, job_id) -> None:
    """Фоновая обработка batch-задачи + отправка результата пользователю."""
    try:
        result = await service.process_job(job_id)
        text = (
            f"✅ <b>Пакетная проверка завершена</b>\n\n"
            f"📊 Всего: {result['total']}\n"
            f"✅ Успешно: {result['success']}\n"
            f"❌ Ошибок: {result['errors']}"
        )

        # Генерируем CSV с результатами
        csv_data = await service.get_results_csv(job_id)
        file = BufferedInputFile(csv_data, filename=f"batch_{job_id}.csv")

        await message.answer_document(
            document=file,
            caption=text,
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки: {e}")


@router.callback_query(BatchAction.filter(F.action == "upload"))
async def batch_upload(callback: CallbackQuery, state: FSMContext) -> None:
    """Загрузить новый файл."""
    await callback.message.edit_text(
        "📤 Отправьте CSV-файл с кадастровыми номерами.",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(BatchUpload.waiting_for_file)
    await callback.answer()
