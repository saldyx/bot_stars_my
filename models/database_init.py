"""
Инициализация базы данных
"""
from models.user import UserModel
from models.referral import ReferralModel
from models.task import TaskModel, FlyerTaskModel, UserTaskModel, TaskSubscriptionModel
from models.channel import ChannelModel
from models.crypto import CryptoModel, ExchangeRateModel
from models.game import KNBModel, LotteryModel, BoosterModel, ClickModel, DailyGiftModel
from models.utm import UTMModel
from models.withdrawal import WithdrawalModel, PromoCodeModel


def initialize_all_tables():
    """Инициализирует все таблицы базы данных"""
    try:
        print("Инициализация базы данных...")
        
        # Основные модели
        UserModel.create_table()
        print('Таблица "users" создана')
        
        # Задания
        TaskModel.create_tables()
        UserTaskModel.create_tables()
        TaskSubscriptionModel.create_table()
        print('Таблицы заданий созданы')
        
        # Каналы
        ChannelModel.create_table()
        print('Таблица "channels" создана')
        
        # Криптоплатежи
        CryptoModel.create_tables()
        ExchangeRateModel.create_table()
        ExchangeRateModel.init_rate()
        CryptoModel.init_settings()
        print('Таблицы криптоплатежей созданы')
        
        # Игры
        KNBModel.create_table()
        LotteryModel.create_tables()
        BoosterModel.create_table()
        ClickModel.create_table()
        DailyGiftModel.create_table()
        print('Таблицы игр созданы')
        
        # UTM и статистика
        UTMModel.create_tables()
        print('Таблицы UTM созданы')
        
        # Выводы и промокоды
        WithdrawalModel.create_table()
        PromoCodeModel.create_tables()
        print('Таблицы выводов и промокодов созданы')
        
        print('База данных успешно инициализирована.')
        return True
    except Exception as e:
        print(f"Ошибка при инициализации базы данных: {e}")
        return False