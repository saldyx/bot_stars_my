"""
Сервис для работы с платежами
"""
from typing import Optional, Tuple, List
from models.crypto import CryptoModel, ExchangeRateModel
from models.user import UserModel
from models.withdrawal import WithdrawalModel, PromoCodeModel


class PaymentService:
    """Сервис для работы с платежами"""
    
    @staticmethod
    def create_crypto_payment(user_id: int, amount: float, usdt_amount: float) -> int:
        """Создает криптоплатеж"""
        return CryptoModel.add_payment(user_id, amount, "crypto", usdt_amount)
    
    @staticmethod
    def confirm_crypto_payment(payment_id: int, admin_id: int) -> bool:
        """Подтверждает криптоплатеж"""
        try:
            # Получаем информацию о платеже
            payment_info = CryptoModel.get_payment_by_id(payment_id)
            if not payment_info:
                return False
            
            payment_id, user_id, amount, payment_method, usdt_amount, status, created_at = payment_info
            
            # Подтверждаем платеж
            CryptoModel.confirm_payment(payment_id, admin_id)
            
            # Пополняем рекламный баланс пользователя
            UserModel.update_ad_balance(user_id, amount)
            
            return True
        except Exception as e:
            print(f"Ошибка при подтверждении платежа: {e}")
            return False
    
    @staticmethod
    def reject_crypto_payment(payment_id: int, admin_id: int) -> bool:
        """Отклоняет криптоплатеж"""
        try:
            CryptoModel.reject_payment(payment_id, admin_id)
            return True
        except Exception as e:
            print(f"Ошибка при отклонении платежа: {e}")
            return False
    
    @staticmethod
    def calculate_crypto_amount(stars_amount: float) -> dict:
        """Рассчитывает сумму в криптовалюте"""
        exchange_rate = ExchangeRateModel.get_rate()
        ruble_amount = stars_amount * exchange_rate
        usdt_rate = 100  # 1 USDT = 100 рублей
        usdt_amount = ruble_amount / usdt_rate
        
        return {
            'stars': stars_amount,
            'rubles': ruble_amount,
            'usdt': usdt_amount,
            'exchange_rate': exchange_rate
        }
    
    @staticmethod
    def get_crypto_settings() -> dict:
        """Получает настройки криптовалюты"""
        return CryptoModel.get_settings()
    
    @staticmethod
    def update_crypto_settings(address: Optional[str] = None, network: Optional[str] = None):
        """Обновляет настройки криптовалюты"""
        CryptoModel.update_settings(address, network)
    
    @staticmethod
    def get_exchange_rate() -> float:
        """Получает текущий курс валют"""
        return ExchangeRateModel.get_rate()
    
    @staticmethod
    def set_exchange_rate(new_rate: float):
        """Устанавливает новый курс валют"""
        ExchangeRateModel.set_rate(new_rate)


class WithdrawalService:
    """Сервис для работы с выводами"""
    
    @staticmethod
    def create_withdrawal_request(user_id: int, amount: float, username: str) -> Tuple[bool, Optional[int]]:
        """Создает запрос на вывод"""
        try:
            # Проверяем достаточность средств
            balance = UserModel.get_balance(user_id)
            if balance < amount:
                return False, None
            
            # Списываем средства
            UserModel.deincrement_stars(user_id, amount)
            
            # Создаем запрос на вывод
            withdrawal_id = WithdrawalModel.add_withdrawal_simple(user_id, amount, username)
            
            return True, withdrawal_id
        except Exception as e:
            print(f"Ошибка при создании запроса на вывод: {e}")
            return False, None
    
    @staticmethod
    def get_user_withdrawal_status(user_id: int) -> Optional[str]:
        """Получает статус вывода пользователя"""
        return WithdrawalModel.get_status_withdrawal(user_id)
    
    @staticmethod
    def get_user_withdrawals(user_id: int) -> List[Tuple]:
        """Получает все выводы пользователя"""
        return WithdrawalModel.get_withdrawals(user_id)


class PromoCodeService:
    """Сервис для работы с промокодами"""
    
    @staticmethod
    def create_promocode(code: str, stars: float, max_uses: int) -> bool:
        """Создает новый промокод"""
        return PromoCodeModel.add_promocode(code, stars, max_uses)
    
    @staticmethod
    def use_promocode(code: str, user_id: int) -> Tuple[bool, str]:
        """Использует промокод"""
        return PromoCodeModel.use_promocode(code, user_id)
    
    @staticmethod
    def get_all_promocodes() -> List[dict]:
        """Получает все промокоды"""
        return PromoCodeModel.get_all_promocodes()
    
    @staticmethod
    def deactivate_promocode(code: str):
        """Деактивирует промокод"""
        PromoCodeModel.deactivate_promocode(code)