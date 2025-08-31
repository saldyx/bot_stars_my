"""
Состояния для FSM
"""
from aiogram.fsm.state import State, StatesGroup


class ConfigStates(StatesGroup):
    waiting_for_referrals = State()
    waiting_for_tasks = State()
    waiting_for_boost = State()
    waiting_for_click = State()
    waiting_for_daily = State()


class KNBGame(StatesGroup):
    waiting_username = State()
    waiting_stake = State()


class AddUtmState(StatesGroup):
    waiting_for_url = State()
    waiting_for_delete = State()


class TheftGame(StatesGroup):
    waiting_username = State()


class LotteryState(StatesGroup):
    ticket_cash = State()


class CaptchaState(StatesGroup):
    waiting_for_answer = State()


class CaptchaClick(StatesGroup):
    waiting_click_captcha = State()


class UserTaskStates(StatesGroup):
    waiting_for_post = State()
    waiting_for_subscribers = State()
    waiting_for_payment_method = State()
    waiting_for_stars_amount = State()
    transfer_amount = State()


class AdminState(StatesGroup):
    USERS_CHECK = State()
    ADD_STARS = State()
    REMOVE_STARS = State()
    MAILING = State()
    ADD_PROMO_CODE = State()
    REMOVE_PROMO_CODE = State()
    ADD_CHANNEL = State()
    REMOVE_CHANNEL = State()
    ADD_MAX_USES = State()
    ADD_TASK = State()
    REMOVE_TASK = State()
    WAITING_FOR_BUTTONS_AFTER_STICKER = State()
    PROMOCODE_INPUT = State()
    ADD_TASK_REWARD = State()
    ADD_TASK_CHANNEL = State()
    ADD_TASK_PRIVATE = State()
    CHECK_TASK_BOT = State()
    DELETE_TASK_INPUT = State()
    DELETE_ACTIVE_TASK_INPUT = State()
    DELETE_CHANNEL_INPUT = State()
    DELETE_PROMO_INPUT = State()
    GIVE_BOOST = State()
    WAIT_TIME_BOOSTER = State()
    ADD_CHANNEL_LINK = State()
    ADD_CHANNEL_LIMIT = State()
    ADD_AD_BALANCE = State()
    CONFIRM_CRYPTO = State()
    MASS_AD_BALANCE = State()
    CRYPTO_ADDRESS = State()
    CRYPTO_NETWORK = State()
    WAITING_FOR_EXCHANGE_RATE = State()