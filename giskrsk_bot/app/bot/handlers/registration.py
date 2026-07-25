"""Регистрация пользователя: имя → почта → телефон → согласие на рассылку.

Telegram ID фиксируется автоматически. Почта и телефон — опциональны.
Согласие на рассылку используется командой /promo (админ).
"""

from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import main_menu_keyboard
from app.bot.keyboards_data import RegAction
from app.bot.states import Registration
from app.services.profile_store import ProfileStore

logger = logging.getLogger(__name__)

router = Router(name="registration")
profiles = ProfileStore()

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
_SKIP_WORDS = {"нет", "пропустить", "skip", "-"}


async def _start_registration(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.name)
    await message.answer(
        "📝 <b>Регистрация</b> (4 коротких шага)\n\n"
        "Шаг 1 из 4. Как вас зовут? Напишите имя (можно с фамилией).",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext) -> None:
    """Начать регистрацию командой."""
    await _start_registration(message, state)


@router.callback_query(RegAction.filter(F.action == "start"))
async def cb_register(callback: CallbackQuery, state: FSMContext) -> None:
    """Начать регистрацию по кнопке."""
    await callback.answer()
    await _start_registration(callback.message, state)


@router.message(Registration.name, F.text)
async def reg_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip()[:128])
    await state.set_state(Registration.email)
    await message.answer(
        "Шаг 2 из 4. 📧 Ваша электронная почта?\n"
        "(или напишите «нет», чтобы пропустить)"
    )


@router.message(Registration.email, F.text)
async def reg_email(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.lower() in _SKIP_WORDS:
        email = ""
    elif _EMAIL_RE.match(text):
        email = text
    else:
        await message.answer(
            "🤔 Не похоже на почту. Попробуйте ещё раз или напишите «нет»."
        )
        return
    await state.update_data(email=email)
    await state.set_state(Registration.phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "Шаг 3 из 4. 📱 Номер телефона — нажмите кнопку ниже "
        "или введите вручную.",
        reply_markup=kb,
    )


async def _ask_consent(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.consent)
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Да, присылайте",
        callback_data=RegAction(action="consent_yes"),
    )
    builder.button(
        text="❌ Нет, только важное",
        callback_data=RegAction(action="consent_no"),
    )
    builder.adjust(1)
    await message.answer(
        "Шаг 4 из 4. 📢 Присылать вам акции, скидки на тарифы "
        "и новости сервиса?",
        reply_markup=builder.as_markup(),
    )


@router.message(Registration.phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.contact.phone_number)
    await _ask_consent(message, state)


@router.message(Registration.phone, F.text)
async def reg_phone_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    phone = "" if text.lower() in _SKIP_WORDS else text[:32]
    await state.update_data(phone=phone)
    await _ask_consent(message, state)


@router.callback_query(
    Registration.consent,
    RegAction.filter(F.action.in_({"consent_yes", "consent_no"})),
)
async def reg_consent(
    callback: CallbackQuery, callback_data: RegAction, state: FSMContext
) -> None:
    data = await state.get_data()
    profiles.upsert(
        callback.from_user.id,
        name=data.get("name", ""),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        username=callback.from_user.username or "",
        promo_consent=callback_data.action == "consent_yes",
    )
    await state.clear()
    await callback.message.edit_text(
        "✅ <b>Регистрация завершена!</b>\n\n"
        "Спасибо! Теперь выдача доступа будет быстрее."
    )
    await callback.message.answer(
        "Главное меню:", reply_markup=main_menu_keyboard()
    )
    await callback.answer()
