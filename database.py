"""
База данных - рефакторинг
Этот файл обеспечивает обратную совместимость со старым API
"""

# Импорты всех моделей
from models.user import UserModel
from models.referral import ReferralModel
from models.task import TaskModel, FlyerTaskModel, UserTaskModel, TaskSubscriptionModel
from models.channel import ChannelModel
from models.crypto import CryptoModel, ExchangeRateModel
from models.game import KNBModel, LotteryModel, BoosterModel, ClickModel, DailyGiftModel
from models.utm import UTMModel, StatisticsModel
from models.withdrawal import WithdrawalModel, PromoCodeModel
from models.database_init import initialize_all_tables

# Импорты сервисов
from services.user_service import UserService
from services.task_service import TaskService
from services.payment_service import PaymentService, WithdrawalService, PromoCodeService
from services.game_service import GameService, LotteryService, BoostService, ClickService, DailyGiftService
from services.channel_service import ChannelService
from services.utm_service import UTMService, StatisticsService

# Импорты конфигурации
from config.database import connect_db, DATABASE_NAME

# ===============================================
# ОБРАТНАЯ СОВМЕСТИМОСТЬ - Алиасы функций
# ===============================================

# Подключение к базе
def connect_db():
    from config.database import connect_db as _connect_db
    return _connect_db()

# Инициализация
def initialize_database():
    return initialize_all_tables()

def init_channels_table():
    ChannelModel.create_table()
    ExchangeRateModel.create_table()
    ExchangeRateModel.init_rate()
    CryptoModel.create_tables()
    CryptoModel.init_settings()

def init_exchange_rate():
    ExchangeRateModel.create_table()
    ExchangeRateModel.init_rate()

def init_crypto_payments_table():
    CryptoModel.create_tables()

def init_crypto_settings_table():
    CryptoModel.create_tables()
    CryptoModel.init_settings()

def create_utm_stats_table():
    UTMModel.create_tables()

def create_skipped_tasks_table():
    TaskModel.create_tables()

def create_task_subscriptions_table():
    TaskSubscriptionModel.create_table()

# Курс валют
def get_exchange_rate():
    return ExchangeRateModel.get_rate()

def set_exchange_rate(new_rate):
    ExchangeRateModel.set_rate(new_rate)

# Криптоплатежи
def get_crypto_settings():
    return CryptoModel.get_settings()

def update_crypto_settings(address=None, network=None):
    CryptoModel.update_settings(address, network)

def add_crypto_payment(user_id, amount, payment_method, usdt_amount):
    return CryptoModel.add_payment(user_id, amount, payment_method, usdt_amount)

def get_crypto_payment_by_id(payment_id):
    return CryptoModel.get_payment_by_id(payment_id)

def confirm_crypto_payment(payment_id, admin_id):
    CryptoModel.confirm_payment(payment_id, admin_id)

def reject_crypto_payment(payment_id, admin_id):
    CryptoModel.reject_payment(payment_id, admin_id)

# Каналы
def add_channel(channel_id, channel_link, subscriber_limit):
    return ChannelModel.add_channel(channel_id, channel_link, subscriber_limit)

def get_all_channels():
    return ChannelModel.get_all_channels()

def get_active_channels():
    return ChannelModel.get_active_channels()

def get_channel_info(channel_id):
    return ChannelModel.get_channel_info(channel_id)

def increment_channel_subscribers(channel_id):
    return ChannelModel.increment_subscribers(channel_id)

def deactivate_channel(channel_id):
    return ChannelModel.deactivate_channel(channel_id)

def activate_channel(channel_id):
    return ChannelModel.activate_channel(channel_id)

def reset_channel_subscribers(channel_id):
    return ChannelModel.reset_subscribers(channel_id)

def delete_channel(channel_id):
    return ChannelModel.delete_channel(channel_id)

def get_channels_stats():
    return ChannelModel.get_channels_stats()

def update_channel_limit(channel_id, new_limit):
    return ChannelModel.update_channel_limit(channel_id, new_limit)

# UTM
def add_utm_user(user_id, utm):
    UTMModel.add_utm_user(user_id, utm)

def users_utm_count(utm):
    return UTMModel.users_utm_count(utm)

def users_utm_count_op(utm):
    return UTMModel.users_utm_count_op(utm)

def delete_utm(utm):
    UTMModel.delete_utm(utm)

def mark_utm_passed(user_id, utm):
    UTMModel.mark_utm_passed(user_id, utm)

def create_utm(url, count_users=0):
    UTMModel.create_utm(url, count_users)

def get_urls_utm():
    return UTMModel.get_urls_utm()

def users_add_utm(url):
    UTMModel.users_add_utm(url)

def users_add_utm_op(url):
    UTMModel.users_add_utm_op(url)

def get_urls_by_id(user_id):
    return UTMModel.get_urls_by_id(user_id)

def add_url(user_id, url):
    UTMModel.add_url(user_id, url)

# Пользователи
def user_exists(user_id):
    return UserModel.user_exists(user_id)

def is_user_in_db(user_id):
    return UserModel.user_exists(user_id)

def add_user(user_id, username, referral_id=None):
    UserModel.add_user(user_id, username, referral_id)

def ensure_user_exists(user_id, username=None):
    UserModel.ensure_user_exists(user_id, username)

def get_balance_user(user_id):
    return UserModel.get_balance(user_id)

def get_ad_balance(user_id):
    return UserModel.get_ad_balance(user_id)

def increment_stars(user_id, stars):
    UserModel.increment_stars(user_id, stars)

def deincrement_stars(user_id, stars):
    UserModel.deincrement_stars(user_id, stars)

def update_ad_balance(user_id, amount):
    UserModel.update_ad_balance(user_id, amount)

def transfer_to_ad_balance(user_id, amount):
    return UserModel.transfer_to_ad_balance(user_id, amount)

def deduct_ad_balance(user_id, amount):
    return UserModel.deduct_ad_balance(user_id, amount)

def get_username(user_id):
    return UserModel.get_username(user_id)

def readd_username(user_id, username):
    UserModel.update_username(user_id, username)

def get_id_from_username(username):
    return UserModel.get_id_from_username(username)

def get_banned_user(user_id):
    return UserModel.get_banned_status(user_id)

def set_banned_user(user_id, banned):
    UserModel.set_banned_status(user_id, banned)

def delete_user(user_id):
    UserModel.delete_user(user_id)

def get_user_count():
    return UserModel.get_user_count()

def get_total_withdrawn():
    return UserModel.get_total_withdrawn()

def get_users():
    return UserModel.get_users()

def get_users_ids():
    return UserModel.get_users_ids()

def get_top_balance():
    return UserModel.get_top_balance()

def sum_all_stars():
    return UserModel.sum_all_stars()

def sum_all_withdrawn():
    return UserModel.sum_all_withdrawn()

def get_normal_time_registration(user_id):
    return UserModel.get_registration_time(user_id)

# Рефералы
def get_count_ref(user_id):
    return ReferralModel.get_referral_count(user_id)

def get_count_refs(user_id):
    return ReferralModel.get_referral_count(user_id)

def get_user_referrals_count(referrer_id):
    return ReferralModel.get_user_referrals_count(referrer_id)

def get_id_refferer(user_id):
    return ReferralModel.get_referrer_id(user_id)

def increment_referrals(referrer_id):
    ReferralModel.increment_referrals(referrer_id)

def get_user_refferals_list_and_username(user_id):
    return ReferralModel.get_user_referrals_list_and_username(user_id)

def get_top_referrals():
    return ReferralModel.get_top_referrals()

def get_period_timestamps(period):
    return ReferralModel.get_period_timestamps(period)

def get_top_referrals_formatted(period):
    return ReferralModel.get_top_referrals_formatted(period)

def get_weekly_referrals(user_id):
    return ReferralModel.get_weekly_referrals(user_id)

def get_user_referral_rank_formatted(user_id, period):
    return ReferralModel.get_user_referral_rank_formatted(user_id, period)

# Задания
def add_tasker(description, reward, link=None, boter=None, max_uses=0, channelprivate_id=0):
    TaskModel.add_task(description, reward, link, boter, max_uses, channelprivate_id)

def get_task(task_id):
    return TaskModel.get_task(task_id)

def get_active_tasks():
    return TaskModel.get_active_tasks()

def deactivate_task(task_id):
    TaskModel.deactivate_task(task_id)

def delete_task(task_id):
    TaskModel.delete_task(task_id)

def increment_current_completed(task_id):
    TaskModel.increment_current_completed(task_id)

def get_current_completed(task_id):
    return TaskModel.get_current_completed(task_id)

def get_max_completed(task_id):
    return TaskModel.get_max_completed(task_id)

def get_completed_tasks_for_user(user_id):
    return TaskModel.get_completed_tasks_for_user(user_id)

def complete_task_for_user(user_id, task_id):
    return TaskModel.complete_task_for_user(user_id, task_id)

def add_completed_task(user_id):
    TaskModel.add_completed_task_log(user_id)

def get_tasks_count_by_user_for_day(user_id):
    return TaskModel.get_tasks_count_by_user_for_day(user_id)

def get_tasks_count_by_user_for_week(user_id):
    return TaskModel.get_tasks_count_by_user_for_week(user_id)

def get_tasks_count_by_user_for_month(user_id):
    return TaskModel.get_tasks_count_by_user_for_month(user_id)

def increment_counter_tasks(user_id, count):
    TaskModel.increment_counter_tasks(user_id, count)

def get_count_tasks(user_id):
    return TaskModel.get_count_tasks(user_id)

# Flyer задания
def is_flyer_task_completed(task_hash):
    return FlyerTaskModel.is_task_completed(task_hash)

def add_flyer_task(task_hash):
    return FlyerTaskModel.add_task(task_hash)

def add_skipped_flyer_task(task_hash, user_id):
    FlyerTaskModel.add_skipped_task(task_hash, user_id)

def is_flyer_task_skipped(task_hash, user_id):
    return FlyerTaskModel.is_task_skipped(task_hash, user_id)

# Пользовательские задания
def create_user_task(creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, total_cost, status='active'):
    return UserTaskModel.create_task(creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, total_cost, status)

def get_task_by_id(task_id):
    return UserTaskModel.get_task_by_id(task_id)

def get_active_user_tasks():
    return UserTaskModel.get_active_tasks()

def get_pending_user_tasks():
    return UserTaskModel.get_pending_tasks()

def get_user_tasks(creator_id):
    return UserTaskModel.get_user_tasks(creator_id)

def approve_user_task(task_id):
    return UserTaskModel.approve_task(task_id)

def reject_user_task(task_id):
    return UserTaskModel.reject_task(task_id)

def cancel_user_task(task_id):
    return UserTaskModel.cancel_task(task_id)

def get_user_task_cost(task_id):
    return UserTaskModel.get_task_cost(task_id)

def update_task_subscribers(task_id):
    UserTaskModel.update_task_subscribers(task_id)

def update_user_task_link(task_id, task_link):
    UserTaskModel.update_task_link(task_id, task_link)

def delete_user_task(task_id):
    return UserTaskModel.delete_task(task_id)

def add_task_subscription(task_id, user_id):
    TaskSubscriptionModel.add_subscription(task_id, user_id)

def check_task_subscription(task_id, user_id):
    return TaskSubscriptionModel.check_subscription(task_id, user_id)

def mark_task_subscription_rewarded(task_id, user_id):
    TaskSubscriptionModel.mark_subscription_rewarded(task_id, user_id)

def add_skipped_user_task(task_id, user_id):
    TaskSubscriptionModel.add_skipped_user_task(task_id, user_id)

def is_user_task_skipped(task_id, user_id):
    return TaskSubscriptionModel.is_user_task_skipped(task_id, user_id)

def get_subscriptions_to_check():
    return TaskSubscriptionModel.get_subscriptions_to_check()

def mark_subscription_checked(subscription_id, is_still_subscribed):
    TaskSubscriptionModel.mark_subscription_checked(subscription_id, is_still_subscribed)

# Игры - КНБ
def create_knb(first_player, second_player, choice_first=None, choice_second=None, result=None, bet=0):
    return KNBModel.create_game(first_player, second_player, choice_first, choice_second, result, bet)

def get_knb_game(game_id):
    return KNBModel.get_game(game_id)

def get_bet(game_id):
    return KNBModel.get_bet(game_id)

def change_choice(game_id, player_id, choice):
    KNBModel.change_choice(game_id, player_id, choice)

def set_result(id_game, choice_first, choice_second):
    return KNBModel.set_result(id_game, choice_first, choice_second)

def delete_knb(game_id):
    KNBModel.delete_game(game_id)

# Лотерея
def create_lottery(cash, ticket_cash):
    LotteryModel.create_lottery(cash, ticket_cash)

def get_active_lottery_id():
    return LotteryModel.get_active_lottery_id()

def get_cash_in_lottery():
    return LotteryModel.get_cash_in_lottery()

def get_ticket_cash_in_lottery():
    return LotteryModel.get_ticket_cash_in_lottery()

def get_id_lottery_enabled():
    return LotteryModel.get_active_lottery_id()

def get_count_tickets_by_user(lottery_id, user_id):
    return LotteryModel.get_count_tickets_by_user(lottery_id, user_id)

def add_lottery_entry(lottery_id, user_id, username, cash, count_tickets=1):
    LotteryModel.add_lottery_entry(lottery_id, user_id, username, cash, count_tickets)

def finish_and_update_winner():
    return LotteryModel.finish_and_update_winner()

# Бустеры
def add_or_update_user_boost(user_id, end_time):
    BoosterModel.add_or_update_user_boost(user_id, end_time)

def remove_user_boost(user_id):
    BoosterModel.remove_user_boost(user_id)

def user_in_booster(user_id):
    return BoosterModel.user_in_booster(user_id)

def get_time_until_boost(user_id):
    return BoosterModel.get_time_until_boost(user_id)

def check_and_remove_expired_boosts():
    BoosterModel.check_and_remove_expired_boosts()

# Клики
def get_last_click_time(user_id):
    return ClickModel.get_last_click_time(user_id)

def update_last_click_time(user_id):
    ClickModel.update_last_click_time(user_id)

def update_click_count(user_id):
    ClickModel.update_click_count(user_id)

def get_count_clicks(user_id):
    return ClickModel.get_count_clicks(user_id)

def get_top_clicked():
    return ClickModel.get_top_clicked()

def get_clicks_by_period(period):
    return ClickModel.get_clicks_by_period(period)

# Ежедневные подарки
def get_last_daily_gift_time(user_id):
    return DailyGiftModel.get_last_daily_gift_time(user_id)

def update_last_daily_gift_time(user_id):
    DailyGiftModel.update_last_daily_gift_time(user_id)

# Выводы
def add_withdrawale(username, user_id, stars, status='Ожидает обработки ⚙️'):
    return WithdrawalModel.add_withdrawal(username, user_id, stars, status)

def add_withdrawal(user_id, amount, username):
    return WithdrawalModel.add_withdrawal_simple(user_id, amount, username)

def get_status_withdrawal(user_id):
    return WithdrawalModel.get_status_withdrawal(user_id)

def get_withdrawals(user_id):
    return WithdrawalModel.get_withdrawals(user_id)

def get_withdrawn(user_id):
    user_info = UserService.get_user_info(user_id)
    return user_info.get('withdrawn', 0)

# Промокоды
def add_promocode(code, stars, max_uses):
    return PromoCodeModel.add_promocode(code, stars, max_uses)

def use_promocode(code, user_id):
    return PromoCodeModel.use_promocode(code, user_id)

def get_all_promocodes():
    return PromoCodeModel.get_all_promocodes()

def deactivate_promocode(code):
    PromoCodeModel.deactivate_promocode(code)

# Статистика
def get_users_by_period(period):
    return StatisticsModel.get_users_by_period(period)

# Дополнительные функции для совместимости
def change_status(id, status):
    # Эта функция не используется в новой архитектуре
    pass

def get_all_user_tasks_for_admin():
    # Возвращаем все пользовательские задания исключая Subgram
    all_tasks = UserTaskModel.get_active_tasks()
    from utils.helpers import is_subgram_task
    filtered = [task for task in all_tasks if not is_subgram_task(task)]
    return filtered

def is_subgram_task(task):
    from utils.helpers import is_subgram_task as _is_subgram_task
    return _is_subgram_task(task)

# Функция для добавления отслеживания подписки (новая функциональность)
def add_task_subscription_tracking(user_id: int, task_id: int, task_type: str, 
                                 channel_id: int, reward_amount: float, 
                                 task_signature: str = None):
    """Добавляет отслеживание подписки на 3 дня"""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO task_subscriptions 
        (user_id, task_id, task_type, task_signature, channel_id, reward_amount)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, task_id, task_type, task_signature, channel_id, reward_amount))
    conn.commit()
    conn.close()

# Автоматическая инициализация при импорте
initialize_all_tables()