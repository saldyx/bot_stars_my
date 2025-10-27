"""
Сервис для работы с каналами
"""
from typing import List, Tuple, Optional
from models.channel import ChannelModel


class ChannelService:
    """Сервис для работы с каналами"""
    
    @staticmethod
    def add_channel(channel_id: int, channel_link: str, subscriber_limit: int) -> bool:
        """Добавляет новый канал"""
        return ChannelModel.add_channel(channel_id, channel_link, subscriber_limit)
    
    @staticmethod
    def get_active_channels() -> List[Tuple]:
        """Получает активные каналы"""
        return ChannelModel.get_active_channels()
    
    @staticmethod
    def get_all_channels() -> List[Tuple]:
        """Получает все каналы"""
        return ChannelModel.get_all_channels()
    
    @staticmethod
    def get_channel_info(channel_id: int) -> Optional[Tuple]:
        """Получает информацию о канале"""
        return ChannelModel.get_channel_info(channel_id)
    
    @staticmethod
    def process_new_subscriber(channel_id: int) -> bool:
        """Обрабатывает нового подписчика канала"""
        return ChannelModel.increment_subscribers(channel_id)
    
    @staticmethod
    def activate_channel(channel_id: int) -> bool:
        """Активирует канал"""
        return ChannelModel.activate_channel(channel_id)
    
    @staticmethod
    def deactivate_channel(channel_id: int) -> bool:
        """Деактивирует канал"""
        return ChannelModel.deactivate_channel(channel_id)
    
    @staticmethod
    def reset_channel_subscribers(channel_id: int) -> bool:
        """Сбрасывает счетчик подписчиков канала"""
        return ChannelModel.reset_subscribers(channel_id)
    
    @staticmethod
    def update_channel_limit(channel_id: int, new_limit: int) -> bool:
        """Обновляет лимит подписчиков канала"""
        return ChannelModel.update_channel_limit(channel_id, new_limit)
    
    @staticmethod
    def delete_channel(channel_id: int) -> bool:
        """Удаляет канал"""
        return ChannelModel.delete_channel(channel_id)
    
    @staticmethod
    def get_channels_statistics() -> List[Tuple]:
        """Получает статистику по каналам"""
        return ChannelModel.get_channels_stats()