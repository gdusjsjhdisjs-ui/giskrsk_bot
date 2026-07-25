from aiogram.filters.callback_data import CallbackData


class MainMenuAction(CallbackData, prefix="mm"):
    """Действия главного меню."""
    action: str  # check_parcel | tariffs | my_subscription | tracking | profile | admin | help


class TariffSelect(CallbackData, prefix="tariff"):
    """Выбор тарифа для покупки."""
    plan_code: str  # basic_30d | pro_30d | pro_90d | year


class PaymentConfirm(CallbackData, prefix="pay"):
    """Подтверждение / проверка платежа."""
    payment_id: str  # UUID платежа
    action: str = "pay"  # pay


class ParcelAction(CallbackData, prefix="parcel"):
    """Действия при проверке участка."""
    action: str  # search | by_cadnum | by_geo | retry
    cadnum: str = ""


class TrackingAction(CallbackData, prefix="trk"):
    """Действия с отслеживанием участков."""
    action: str  # add | remove | list | toggle
    track_id: str = ""


class BatchAction(CallbackData, prefix="batch"):
    """Действия пакетной проверки."""
    action: str  # upload | download_result | retry


class SubscriptionAction(CallbackData, prefix="sub"):
    """Действия с подпиской пользователя."""
    action: str  # status | extend | cancel | change_plan


class ProfileAction(CallbackData, prefix="prof"):
    """Действия с профилем пользователя."""
    action: str  # show | requests_used


class ShopAction(CallbackData, prefix="shop"):
    """Действия в магазине георесурсов."""
    action: str  # list | item | buy | paid
    value: str = ""  # item_id для item/buy, order_id для paid


class ShopAdminAction(CallbackData, prefix="shopadm"):
    """Админские действия с заказами магазина."""
    action: str  # approve | reject
    order_id: str


class SubPayAction(CallbackData, prefix="subpay"):
    """Оплата подписки переводом по номеру карты."""
    action: str  # list | buy | paid
    value: str = ""  # plan_code для buy, order_id для paid


class SubAdminAction(CallbackData, prefix="subadm"):
    """Админские действия с оплатой подписки."""
    action: str  # approve | reject
    order_id: str


class RegAction(CallbackData, prefix="reg"):
    """Регистрация пользователя."""
    action: str  # start | consent_yes | consent_no
