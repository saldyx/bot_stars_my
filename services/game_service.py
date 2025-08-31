"""
Сервис для игр и развлечений
"""
import random
import time
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from models.game import KNBModel, LotteryModel, BoosterModel, ClickModel, DailyGiftModel
from models.user import UserModel


class GameService:
    """Сервис для игр"""
    
    @staticmethod
    def create_knb_game(first_player: int, second_player: int, bet: float) -> Optional[int]:
        """Создает игру КНБ"""
        try:
            # Проверяем достаточность средств у обоих игроков
            first_balance = UserModel.get_balance(first_player)
            second_balance = UserModel.get_balance(second_player)
            
            if first_balance < bet or second_balance < bet:
                return None
            
            # Списываем ставки
            UserModel.deincrement_stars(first_player, bet)
            UserModel.deincrement_stars(second_player, bet)
            
            # Создаем игру
            game_id = KNBModel.create_game(first_player, second_player, bet=bet)
            return game_id
        except Exception as e:
            print(f"Ошибка при создании игры КНБ: {e}")
            return None
    
    @staticmethod
    def make_choice(game_id: int, player_id: str, choice: str) -> bool:
        """Делает выбор в игре КНБ"""
        try:
            KNBModel.change_choice(game_id, player_id, choice)
            return True
        except Exception as e:
            print(f"Ошибка при выборе в игре: {e}")
            return False
    
    @staticmethod
    def finish_knb_game(game_id: int, choice_first: str, choice_second: str) -> str:
        """Завершает игру КНБ"""
        return KNBModel.set_result(game_id, choice_first, choice_second)
    
    @staticmethod
    def delete_knb_game(game_id: int):
        """Удаляет игру КНБ"""
        KNBModel.delete_game(game_id)


class LotteryService:
    """Сервис для лотереи"""
    
    @staticmethod
    def create_lottery(cash: float, ticket_cash: float) -> bool:
        """Создает новую лотерею"""
        try:
            LotteryModel.create_lottery(cash, ticket_cash)
            return True
        except Exception as e:
            print(f"Ошибка при создании лотереи: {e}")
            return False
    
    @staticmethod
    def buy_lottery_ticket(user_id: int, username: str) -> Tuple[bool, str]:
        """Покупает билет лотереи"""
        try:
            lottery_id = LotteryModel.get_active_lottery_id()
            if not lottery_id:
                return False, "Нет активной лотереи"
            
            ticket_cost = LotteryModel.get_ticket_cash_in_lottery()
            user_balance = UserModel.get_balance(user_id)
            
            if user_balance < ticket_cost:
                return False, "Недостаточно средств"
            
            # Списываем средства
            UserModel.deincrement_stars(user_id, ticket_cost)
            
            # Добавляем билет
            LotteryModel.add_lottery_entry(lottery_id, user_id, username, ticket_cost)
            
            return True, "Билет куплен успешно"
        except Exception as e:
            print(f"Ошибка при покупке билета: {e}")
            return False, str(e)
    
    @staticmethod
    def finish_lottery() -> Tuple[bool, Optional[int]]:
        """Завершает лотерею"""
        return LotteryModel.finish_and_update_winner()
    
    @staticmethod
    def get_lottery_info() -> dict:
        """Получает информацию о лотерее"""
        return {
            'active_id': LotteryModel.get_active_lottery_id(),
            'cash': LotteryModel.get_cash_in_lottery(),
            'ticket_cost': LotteryModel.get_ticket_cash_in_lottery()
        }


class BoostService:
    """Сервис для бустеров"""
    
    @staticmethod
    def activate_boost(user_id: int, days: int = 15) -> bool:
        """Активирует буст для пользователя"""
        try:
            current_time = datetime.now()
            delta = timedelta(days=days)
            future_time = current_time + delta
            future_timestamp = future_time.timestamp()
            
            BoosterModel.add_or_update_user_boost(user_id, future_timestamp)
            return True
        except Exception as e:
            print(f"Ошибка при активации буста: {e}")
            return False
    
    @staticmethod
    def deactivate_boost(user_id: int) -> bool:
        """Деактивирует буст пользователя"""
        try:
            BoosterModel.remove_user_boost(user_id)
            return True
        except Exception as e:
            print(f"Ошибка при деактивации буста: {e}")
            return False
    
    @staticmethod
    def check_user_boost(user_id: int) -> dict:
        """Проверяет статус буста пользователя"""
        return {
            'has_boost': BoosterModel.user_in_booster(user_id),
            'time_left': BoosterModel.get_time_until_boost(user_id)
        }
    
    @staticmethod
    def cleanup_expired_boosts():
        """Очищает просроченные бусты"""
        BoosterModel.check_and_remove_expired_boosts()


class ClickService:
    """Сервис для кликов"""
    
    @staticmethod
    def process_click(user_id: int) -> bool:
        """Обрабатывает клик пользователя"""
        try:
            ClickModel.update_last_click_time(user_id)
            ClickModel.update_click_count(user_id)
            return True
        except Exception as e:
            print(f"Ошибка при обработке клика: {e}")
            return False
    
    @staticmethod
    def get_user_click_info(user_id: int) -> dict:
        """Получает информацию о кликах пользователя"""
        return {
            'last_click_time': ClickModel.get_last_click_time(user_id),
            'click_count': ClickModel.get_count_clicks(user_id)
        }
    
    @staticmethod
    def get_click_statistics(period: str) -> int:
        """Получает статистику кликов за период"""
        return ClickModel.get_clicks_by_period(period)
    
    @staticmethod
    def get_top_clickers() -> List[Tuple]:
        """Получает топ кликеров"""
        return ClickModel.get_top_clicked()


class DailyGiftService:
    """Сервис для ежедневных подарков"""
    
    @staticmethod
    def can_claim_daily_gift(user_id: int) -> bool:
        """Проверяет можно ли получить ежедневный подарок"""
        last_claim_time = DailyGiftModel.get_last_daily_gift_time(user_id)
        if not last_claim_time:
            return True
        
        # Проверяем прошло ли 24 часа
        current_time = time.time()
        return (current_time - last_claim_time) >= 86400  # 24 часа в секундах
    
    @staticmethod
    def claim_daily_gift(user_id: int, gift_amount: float) -> bool:
        """Получает ежедневный подарок"""
        try:
            if not DailyGiftService.can_claim_daily_gift(user_id):
                return False
            
            # Начисляем подарок
            UserModel.increment_stars(user_id, gift_amount)
            
            # Обновляем время последнего получения
            DailyGiftModel.update_last_daily_gift_time(user_id)
            
            return True
        except Exception as e:
            print(f"Ошибка при получении ежедневного подарка: {e}")
            return False
    
    @staticmethod
    def get_time_until_next_gift(user_id: int) -> Optional[float]:
        """Получает время до следующего подарка"""
        last_claim_time = DailyGiftModel.get_last_daily_gift_time(user_id)
        if not last_claim_time:
            return 0  # Можно получить сразу
        
        current_time = time.time()
        time_passed = current_time - last_claim_time
        time_until_next = 86400 - time_passed  # 24 часа - прошедшее время
        
        return max(0, time_until_next)