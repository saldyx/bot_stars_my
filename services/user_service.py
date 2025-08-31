"""
Сервис для работы с пользователями
"""
from typing import Optional, List, Tuple
from models.user import UserModel
from models.referral import ReferralModel


class UserService:
    """Сервис для работы с пользователями"""
    
    @staticmethod
    def register_user(user_id: int, username: Optional[str], referral_id: Optional[int] = None) -> bool:
        """Регистрирует нового пользователя"""
        try:
            if not UserModel.user_exists(user_id):
                UserModel.add_user(user_id, username, referral_id)
                return True
            return False
        except Exception as e:
            print(f"Ошибка при регистрации пользователя: {e}")
            return False
    
    @staticmethod
    def get_user_info(user_id: int) -> dict:
        """Получает полную информацию о пользователе"""
        return {
            'balance': UserModel.get_balance(user_id),
            'ad_balance': UserModel.get_ad_balance(user_id),
            'username': UserModel.get_username(user_id),
            'banned': UserModel.get_banned_status(user_id),
            'referral_count': ReferralModel.get_referral_count(user_id),
            'referrer_id': ReferralModel.get_referrer_id(user_id),
            'registration_time': UserModel.get_registration_time(user_id)
        }
    
    @staticmethod
    def update_user_balance(user_id: int, amount: float, operation: str = 'add') -> bool:
        """Обновляет баланс пользователя"""
        try:
            if operation == 'add':
                UserModel.increment_stars(user_id, amount)
            elif operation == 'subtract':
                UserModel.deincrement_stars(user_id, amount)
            else:
                raise ValueError("Неизвестная операция. Используйте 'add' или 'subtract'")
            return True
        except Exception as e:
            print(f"Ошибка при обновлении баланса: {e}")
            return False
    
    @staticmethod
    def transfer_to_ad_balance(user_id: int, amount: float) -> bool:
        """Переводит звезды на рекламный баланс"""
        return UserModel.transfer_to_ad_balance(user_id, amount)
    
    @staticmethod
    def ban_user(user_id: int) -> bool:
        """Блокирует пользователя"""
        try:
            UserModel.set_banned_status(user_id, 1)
            return True
        except Exception as e:
            print(f"Ошибка при блокировке пользователя: {e}")
            return False
    
    @staticmethod
    def unban_user(user_id: int) -> bool:
        """Разблокирует пользователя"""
        try:
            UserModel.set_banned_status(user_id, 0)
            return True
        except Exception as e:
            print(f"Ошибка при разблокировке пользователя: {e}")
            return False
    
    @staticmethod
    def update_username_if_changed(user_id: int, new_username: Optional[str]):
        """Обновляет username если он изменился"""
        current_username = UserModel.get_username(user_id)
        if current_username != new_username:
            UserModel.update_username(user_id, new_username)
    
    @staticmethod
    def get_top_users_by_balance(limit: int = 50) -> List[Tuple]:
        """Получает топ пользователей по балансу"""
        return UserModel.get_top_balance()
    
    @staticmethod
    def get_users_statistics() -> dict:
        """Получает общую статистику пользователей"""
        return {
            'total_users': UserModel.get_user_count(),
            'total_stars': UserModel.sum_all_stars(),
            'total_withdrawn': UserModel.sum_all_withdrawn()
        }