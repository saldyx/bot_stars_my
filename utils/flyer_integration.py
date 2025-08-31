"""
Интеграция с Flyer API
"""
import hashlib
from typing import List, Dict, Any
from flyerapi import Flyer


class FlyerIntegration:
    """Класс для работы с Flyer API"""
    
    def __init__(self, api_key: str):
        self.flyer = Flyer(api_key)
    
    async def get_tasks(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает задания от Flyer"""
        try:
            return await self.flyer.get_tasks(user_id, limit)
        except Exception as e:
            print(f"Ошибка при получении заданий от Flyer: {e}")
            return []
    
    async def check_task(self, api_key: str, user_id: int, signature: str) -> str:
        """Проверяет выполнение задания Flyer"""
        try:
            return await self.flyer.check_task(api_key, user_id, signature)
        except Exception as e:
            print(f"Ошибка при проверке задания Flyer: {e}")
            return "error"
    
    @staticmethod
    def hash_task(signature: str, user_id: int) -> str:
        """Создает хеш для задания"""
        combined = f"{signature}_{user_id}"
        return hashlib.md5(combined.encode()).hexdigest()


# Глобальные функции для обратной совместимости
async def get_flyer_tasks(api_key: str, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Получает задания от Flyer (глобальная функция)"""
    flyer_integration = FlyerIntegration(api_key)
    return await flyer_integration.get_tasks(user_id, limit)


async def check_flyer_task(api_key: str, user_id: int, signature: str) -> str:
    """Проверяет задание Flyer (глобальная функция)"""
    flyer_integration = FlyerIntegration(api_key)
    return await flyer_integration.check_task(api_key, user_id, signature)


def hash_flyer_task(signature: str, user_id: int) -> str:
    """Создает хеш для Flyer задания (глобальная функция)"""
    return FlyerIntegration.hash_task(signature, user_id)