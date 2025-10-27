"""
Вспомогательные функции
"""
import random
import hashlib
from typing import Optional, Tuple


def get_random_value() -> float:
    """Получает случайное значение"""
    return round(random.uniform(0.1, 0.12), 2)


def generate_channel_link(channel_id: int) -> str:
    """
    Создает ссылку на канал из ID канала
    Для всех каналов создает приватную ссылку вида https://t.me/c/{clean_id}
    """
    # Убираем префикс -100 если он есть
    clean_channel_id = str(channel_id).replace('-100', '')
    return f"https://t.me/c/{clean_channel_id}"


def hash_flyer_task(signature: str, user_id: int) -> str:
    """Создает хеш для Flyer задания"""
    combined = f"{signature}_{user_id}"
    return hashlib.md5(combined.encode()).hexdigest()


def format_time_remaining(seconds: float) -> str:
    """Форматирует оставшееся время в читаемый вид"""
    if seconds <= 0:
        return "Доступно сейчас"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours}ч {minutes}м"
    else:
        return f"{minutes}м"


def validate_user_input(text: str, input_type: str) -> Tuple[bool, Optional[str]]:
    """Валидирует пользовательский ввод"""
    if input_type == 'number':
        try:
            float(text)
            return True, None
        except ValueError:
            return False, "Введите числовое значение"
    
    elif input_type == 'positive_number':
        try:
            value = float(text)
            if value <= 0:
                return False, "Значение должно быть больше 0"
            return True, None
        except ValueError:
            return False, "Введите положительное число"
    
    elif input_type == 'integer':
        try:
            int(text)
            return True, None
        except ValueError:
            return False, "Введите целое число"
    
    elif input_type == 'positive_integer':
        try:
            value = int(text)
            if value <= 0:
                return False, "Значение должно быть больше 0"
            return True, None
        except ValueError:
            return False, "Введите положительное целое число"
    
    return True, None


def is_subgram_task(task: Tuple) -> bool:
    """Проверяет является ли задание Subgram заданием"""
    # Пример: если creator_id = 777 — это Subgram
    # Или если ссылка содержит subgram
    creator_id = task[1]
    channel_link = task[5] if len(task) > 5 else ""
    return creator_id == 777 or 'subgram' in str(channel_link).lower()