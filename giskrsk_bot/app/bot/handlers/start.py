"""Команда /start и главное меню."""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandObject, CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import main_menu_keyboard
from app.bot.keyboards_data import MainMenuAction, RegAction
from app.services.profile_store import ProfileStore
from app.services.referral_store import BONUS_DAYS, ReferralStore

router = Router(name="start")
profiles = ProfileStore()
referrals = ReferralStore()


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Глобальный выход из любого диалога: /cancel или кнопка «❌ Отмена».

    Раньше пользователь мог «залипнуть» в FSM-состоянии (ввод кадастрового
    номера, диалог с AI, загрузка CSV) без способа выйти.
    """
    current = await state.get_state()
    await state.clear()
    if current:
        text = "✅ Действие отменено. Главное меню: /start"
    else:
        text = "Сейчас нечего отменять 🙂 Главное меню: /start"
    await message.answer(text, reply_markup=ReplyKeyboardRemove())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Справка по возможностям бота."""
    await message.answer(
        "ℹ️ <b>Справка</b>\n\n"
        "🔍 <b>Проверка участка</b> — пришлите кадастровый номер через главное меню\n"
        "🗺 <b>Веб-карта ПЗЗ</b> — кнопка меню или /start\n"
        "📦 <b>Пакетная проверка</b> — загрузите CSV со списком номеров\n"
        "🛒 <b>Магазин данных</b> и 🎬 <b>клипы карты</b> — в главном меню\n\n"
        "Команды:\n"
        "/start — главное меню\n"
        "/cancel — отменить текущее действие\n"
        "/help — эта справка\n\n"
        "Если что-то пошло не так — просто отправьте /start."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, **data) -> None:
    """Обработка /start — приветствие и главное меню."""
    # Реферальная ссылка: /start ref_123456
    args = (command.args or "").strip() if command else ""
    if args.startswith("ref_"):
        try:
            referrer_id = int(args[4:])
        except ValueError:
            referrer_id = 0
        if referrer_id and referrals.set_referrer(message.from_user.id, referrer_id):
            try:
                await message.bot.send_message(
                    referrer_id,
                    "🎉 По вашей ссылке пришёл новый пользователь!\n"
                    f"Когда он оплатит подписку — вы получите +{BONUS_DAYS} дней.",
                )
            except Exception:  # noqa: BLE001
                pass

    # Создаём/получаем пользователя в БД
    user_repo = (data.get("repos") or {}).get("user")
    if user_repo:
        await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
    
    # Диплинки из мини-приложения: /start buy_<товар> / shop / tariffs / ref
    if args.startswith("buy_"):
        from app.bot.handlers.shop import send_purchase_offer

        if await send_purchase_offer(message, args[4:]):
            return
    if args == "shop":
        from app.bot.handlers.shop import _SHOP_INTRO, shop_list_keyboard

        await message.answer(_SHOP_INTRO, reply_markup=shop_list_keyboard())
        return
    if args == "tariffs":
        from app.bot.handlers.tariffs import _TARIFFS_INTRO
        from app.bot.keyboards import tariffs_keyboard

        await message.answer(_TARIFFS_INTRO, reply_markup=tariffs_keyboard())
        return
    if args == "ref":
        await cmd_ref(message)
        return

    await message.answer(
        "🏡 <b>ГИС Красноярье</b>\n\n"
        "Проверяйте земельные участки, смотрите зоны ПЗЗ, "
        "отслеживайте изменения — всё в одном месте.\n\n"
        "🔍 Отправьте кадастровый номер или геопозицию, "
        "чтобы получить информацию об участке.",
        reply_markup=main_menu_keyboard(),
    )

    # Приглашение к регистрации для новых пользователей
    if profiles.get(message.from_user.id) is None:
        builder = InlineKeyboardBuilder()
        builder.button(
            text="📝 Пройти регистрацию",
            callback_data=RegAction(action="start"),
        )
        await message.answer(
            "👋 <b>Похоже, вы у нас впервые! Вот что умеет бот:</b>\n\n"
            "🗺 <b>Карта ПЗЗ</b> — зоны, поиск, слои: /app\n"
            "🎁 <b>Пробный день</b> — бесплатный доступ на 24 часа: /tariffs\n"
            "🛒 <b>Магазин данных</b> — готовые выгрузки ПЗЗ: /shop\n"
            "🏛 <b>Аукционы земли</b> — поиск по населённому пункту: /torgi\n"
            f"🤝 <b>Пригласить друга</b> — +{BONUS_DAYS} дней подписки: /ref\n\n"
            "Пройдите быструю регистрацию (меньше минуты) — так выдача "
            "доступа будет быстрее, а ещё вы сможете получать акции и скидки.",
            reply_markup=builder.as_markup(),
        )


@router.message(Command("menu"))
@router.message(F.text == "🏠 Главное меню")
async def cmd_menu(message: Message) -> None:
    """Показать главное меню."""
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard())


@router.callback_query(MainMenuAction.filter(F.action == "main_menu"))
async def back_to_menu(callback: CallbackQuery) -> None:
    """Вернуться в главное меню."""
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=None,
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(Command("ref"))
@router.message(F.text == "🤝 Пригласить друга")
async def cmd_ref(message: Message) -> None:
    """Реферальная ссылка: приведи друга — получи бонусные дни."""
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    invited = referrals.invited_count(message.from_user.id)
    await message.answer(
        f"🤝 <b>Приведите друга — получите +{BONUS_DAYS} дней подписки!</b>\n\n"
        f"Ваша персональная ссылка:\n{link}\n\n"
        f"Как то��ько друг оплатит любой тариф, вам автоматически "
        f"добавится +{BONUS_DAYS} дней к подписке.\n\n"
        f"👥 Приглашено по вашей ссылке: <b>{invited}</b>",
    )
