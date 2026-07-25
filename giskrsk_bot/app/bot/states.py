from aiogram.fsm.state import State, StatesGroup


class ParcelInput(StatesGroup):
    """FSM-состояния для проверки участка."""
    waiting_for_cadnum = State()  # Ожидание ввода кадастрового номера
    waiting_for_location = State()  # Ожидание отправки геопозиции


class BatchUpload(StatesGroup):
    """FSM-состояния для пакетной загрузки."""
    waiting_for_file = State()  # Ожидание загрузки CSV-файла


class ProfileSettings(StatesGroup):
    """FSM-состояния для настроек профиля."""
    waiting_for_notification_toggle = State()  # Настройка уведомлений


class AiConsultation(StatesGroup):
    """FSM-состояния для AI-консультанта."""
    waiting_for_question = State()  # Ожидание вопроса


class GeoConvert(StatesGroup):
    """FSM-состояния для конвертации координат в GeoJSON."""
    waiting_for_coordinates = State()  # Ожидание координат


class Registration(StatesGroup):
    """FSM-состояния регистрации пользователя."""
    name = State()     # Имя
    email = State()    # Почта (опционально)
    phone = State()    # Телефон (опционально)
    consent = State()  # Согласие на рассылку
