"""Handler: convert coordinates to GeoJSON file via DeepSeek AI.

User sends coordinates (text) → DeepSeek generates GeoJSON → bot sends .geojson file.
No chatting, no questions — only file output.
Stays in FSM after each response so user can send multiple requests.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import uuid

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from app.bot.keyboards import cancel_keyboard, back_keyboard
from app.bot.states import GeoConvert
from app.services.ai_service import AiService

logger = logging.getLogger(__name__)
router = Router(name="convert")


def get_ai_service(data: dict) -> AiService | None:
    return data.get("services", {}).get("ai")


@router.message(F.text == "🔄 Координаты → GeoJSON")
async def cmd_convert_start(message: Message, state: FSMContext) -> None:
    """Start conversion mode — user stays in FSM for multiple requests."""
    await message.answer(
        "📌 <b>Координаты → GeoJSON</b>\n\n"
        "Отправляйте координаты — бот будет присылать .geojson файлы.\n"
        "Можно сделать сколько угодно запросов подряд.\n"
        "Нажмите «❌ Отмена» чтобы выйти из режима.\n\n"
        "📐 <b>Примеры ввода:</b>\n\n"
        "📏 <b>EPSG:3857 (метры — из QGIS):</b>\n"
        "<code>5601840 9287310\n5601880 9287400\n5601900 9287350</code>\n\n"
        "🌍 <b>EPSG:4326 (градусы):</b>\n"
        "<code>56.0184 92.8731\n56.0188 92.8740\n56.0190 92.8735</code>\n\n"
        "🔷 <b>WKT:</b>\n"
        "<code>POLYGON((5601840 9287310, 5601880 9287400, 5601900 9287350, 5601840 9287310))</code>",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(GeoConvert.waiting_for_coordinates)


@router.message(GeoConvert.waiting_for_coordinates)
async def handle_coordinates_input(message: Message, state: FSMContext, **data) -> None:
    """Receive coordinates → send to DeepSeek → return .geojson file. Stay in FSM."""
    # Handle cancel
    if message.text and message.text.strip() == "❌ Отмена":
        await state.clear()
        await message.answer("✖️ Выход из режима конвертации.", reply_markup=None)
        return

    if not message.text:
        await message.answer("⚠️ Отправьте координаты текстом.")
        return

    ai_service = get_ai_service(data)
    if not ai_service or not ai_service.available:
        await message.answer("❌ AI-сервис недоступен.", reply_markup=back_keyboard())
        await state.clear()
        return

    status_msg = await message.answer("📡 Обрабатываю...")

    try:
        geojson_str = await ai_service.generate_geojson(message.text.strip())

        # Check for error JSON
        try:
            parsed = json.loads(geojson_str)
            if isinstance(parsed, dict) and "error" in parsed:
                await status_msg.edit_text(f"❌ {parsed['error']}", reply_markup=back_keyboard())
                return
        except json.JSONDecodeError:
            pass

        # Save to temp file (async via thread to avoid blocking event loop)
        filename = f"participok_{uuid.uuid4().hex[:8]}.geojson"
        filepath = os.path.join(tempfile.gettempdir(), filename)

        def _write_file() -> None:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(geojson_str)

        await asyncio.to_thread(_write_file)

        # Send file
        await status_msg.edit_text("✅ <b>GeoJSON готов!</b>")
        doc = FSInputFile(filepath, filename=filename)
        await message.answer_document(
            document=doc,
            caption=f"📄 <b>{filename}</b> — {len(geojson_str)} байт",
        )

        # Cleanup
        try:
            os.remove(filepath)
        except OSError:
            pass

        # Stay in FSM — user can send more coordinates
        await message.answer(
            "✅ Можно прислать ещё координаты\nили нажмите «❌ Отмена» чтобы выйти.",
            reply_markup=cancel_keyboard(),
        )

    except Exception as e:
        logger.exception("GeoJSON generation failed")
        await status_msg.edit_text(f"❌ Ошибка: {e}", reply_markup=back_keyboard())
        # Stay in FSM even on error
