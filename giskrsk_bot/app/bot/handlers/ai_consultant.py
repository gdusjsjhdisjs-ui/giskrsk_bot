"""AI consultant: any questions, no filters, shows daily limit (admin = unlimited)."""

from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import back_keyboard
from app.bot.states import AiConsultation
from app.core.config import settings
from app.repositories.user_repo import UserRepo
from app.services.ai_service import AiService
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)
router = Router(name="ai_consultant")


def get_repo(data: dict, name: str):
    return (data.get("repos") or {}).get(name)


def get_service(data: dict, name: str):
    return (data.get("services") or {}).get(name)


async def daily_quota_msg(data: dict, tg_id: int) -> str:
    """Return remaining daily requests string."""
    user_repo: UserRepo | None = get_repo(data, "user")
    sub_service: SubscriptionService | None = get_service(data, "subscription")
    if not user_repo:
        return ""
    user = await user_repo.get_by_telegram_id(tg_id)
    if not user:
        return ""
    if tg_id in settings.ADMIN_IDS:
        return "\n\n\u2014\n\U0001f451 Администратор (безлимит)"
    limit = settings.DAILY_LIMIT_FREE
    if sub_service:
        limit = await sub_service.get_daily_limit(tg_id)
    used = user.daily_requests_used or 0
    remaining = max(0, limit - used)
    return f"\n\n\u2014\n\U0001f4ca Запросы сегодня: {used}/{limit}"


@router.message(F.text == "\U0001f916 AI-консультант")
async def cmd_ai_start(message: Message, state: FSMContext, **data) -> None:
    ai_service: AiService | None = get_service(data, "ai")
    available = ai_service and ai_service.available
    await state.set_state(AiConsultation.waiting_for_question)
    quota = await daily_quota_msg(data, message.from_user.id) if data.get("repos") else ""
    base = (
        "\U0001f916 <b>AI-консультант</b>\n\n"
        "Задайте любой вопрос про земельные участки, зоны ПЗЗ, ВРИ, строительство.\n\n"
        "\u2022 Что можно строить в зоне Ж-1?\n"
        "\u2022 Чем отличается ИЖС от ЛПХ?\n"
        "\u2022 24:11:0330102:814 \u2014 что за участок?\n"
        "\u2022 Можно ли открыть магазин в зоне ОД-1?\n"
        "\u2022 Расскажи про зону Сх-1\n\n"
        "\U0001f447 Пиши что хочешь узнать:"
    )
    if not available:
        base = "\U0001f916 <b>AI-консультант</b>\n\n\u2139 <i>Сервис использует DeepSeek API.</i>"
    await message.answer(base + quota, reply_markup=back_keyboard("main_menu"))


@router.message(AiConsultation.waiting_for_question)
async def handle_ai_question(message: Message, state: FSMContext, **data) -> None:
    await state.clear()
    ai_service: AiService | None = get_service(data, "ai")
    user_repo: UserRepo | None = get_repo(data, "user")
    sub_service: SubscriptionService | None = get_service(data, "subscription")
    if not ai_service or not ai_service.available:
        await message.answer("AI consultant unavailable.")
        return
    question = message.text or ""
    if len(question.strip()) < 3:
        await message.answer("Напишите вопрос подлиннее \U0001f60a")
        return

    # Check + increment daily limit (skip for admin)
    if user_repo and message.from_user.id not in settings.ADMIN_IDS:
        try:
            used = await user_repo.update_daily_requests(message.from_user.id)
            limit = settings.DAILY_LIMIT_FREE
            if sub_service:
                limit = await sub_service.get_daily_limit(message.from_user.id)
            if used > limit:
                await message.answer(
                    f"\U0001f6ab Дневной лимит ({limit}) исчерпан.\n"
                    f"Завтра обновится или /tariffs"
                )
                return
        except Exception as e:
            logger.warning("Daily limit check failed: %s", e)

    await message.answer("\U0001f914 Думаю...")
    try:
        answer = await ai_service.explain_parcel(
            parcel_info={"cadastral_number": question},
            user_question=question,
        )
        quota = await daily_quota_msg(data, message.from_user.id)
        await message.answer(answer + quota, reply_markup=back_keyboard("main_menu"))
    except Exception as e:
        await message.answer(
            f"\u274c {e}\n\nПопробуйте ещё раз.",
            reply_markup=back_keyboard("main_menu"),
        )
