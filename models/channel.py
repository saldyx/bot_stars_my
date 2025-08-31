"""
Модель каналов
"""
import sqlite3
from typing import Optional, List, Tuple
from config.database import connect_db


class ChannelModel:
    """Модель для работы с каналами"""
    
    @staticmethod
    def create_table():
        """Создает таблицу каналов"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                channel_link TEXT NOT NULL,
                subscriber_limit INTEGER NOT NULL DEFAULT 0,
                current_subscribers INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_channel(channel_id: int, channel_link: str, subscriber_limit: int) -> bool:
        """Добавляет новый канал"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO channels 
                (channel_id, channel_link, subscriber_limit, current_subscribers, is_active)
                VALUES (?, ?, ?, 0, 1)
            ''', (channel_id, channel_link, subscriber_limit))
            conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении канала: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_all_channels() -> List[Tuple]:
        """Получает все каналы"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT channel_id, channel_link, subscriber_limit, current_subscribers, is_active
            FROM channels
        ''')
        channels = cursor.fetchall()
        conn.close()
        return channels
    
    @staticmethod
    def get_active_channels() -> List[Tuple]:
        """Получает только активные каналы"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT channel_id, channel_link, subscriber_limit, current_subscribers
            FROM channels
            WHERE is_active = 1
        ''')
        channels = cursor.fetchall()
        conn.close()
        return channels
    
    @staticmethod
    def get_channel_info(channel_id: int) -> Optional[Tuple]:
        """Получает информацию о конкретном канале"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT channel_id, channel_link, subscriber_limit, current_subscribers, is_active
            FROM channels
            WHERE channel_id = ?
        ''', (channel_id,))
        channel = cursor.fetchone()
        conn.close()
        return channel
    
    @staticmethod
    def increment_subscribers(channel_id: int) -> bool:
        """Увеличивает счетчик подписчиков канала"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            # Получаем текущую информацию о канале
            cursor.execute('''
                SELECT current_subscribers, subscriber_limit
                FROM channels
                WHERE channel_id = ? AND is_active = 1
            ''', (channel_id,))
            result = cursor.fetchone()
            
            if not result:
                return False
            
            current_subs, limit = result
            new_subs = current_subs + 1
            
            # Проверяем, достигнут ли лимит
            is_active = 1 if new_subs < limit else 0
            
            # Обновляем данные
            cursor.execute('''
                UPDATE channels
                SET current_subscribers = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (new_subs, is_active, channel_id))
            
            conn.commit()
            return is_active == 1  # Возвращаем True если канал все еще активен
        except Exception as e:
            print(f"Ошибка при обновлении подписчиков канала {channel_id}: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def deactivate_channel(channel_id: int) -> bool:
        """Деактивирует канал"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE channels
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (channel_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка при деактивации канала {channel_id}: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def activate_channel(channel_id: int) -> bool:
        """Активирует канал"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE channels
                SET is_active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (channel_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка при активации канала {channel_id}: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def reset_subscribers(channel_id: int) -> bool:
        """Сбрасывает счетчик подписчиков канала"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE channels
                SET current_subscribers = 0, is_active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (channel_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка при сбросе подписчиков канала {channel_id}: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def delete_channel(channel_id: int) -> bool:
        """Удаляет канал"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка при удалении канала {channel_id}: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_channels_stats() -> List[Tuple]:
        """Получает статистику по всем каналам"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                channel_id,
                channel_link,
                subscriber_limit,
                current_subscribers,
                is_active,
                created_at,
                updated_at
            FROM channels
            ORDER BY created_at DESC
        ''')
        stats = cursor.fetchall()
        conn.close()
        return stats
    
    @staticmethod
    def update_channel_limit(channel_id: int, new_limit: int) -> bool:
        """Обновляет лимит подписчиков для канала"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            # Получаем текущее количество подписчиков
            cursor.execute('''
                SELECT current_subscribers
                FROM channels
                WHERE channel_id = ?
            ''', (channel_id,))
            result = cursor.fetchone()
            
            if not result:
                return False
            
            current_subs = result[0]
            # Определяем активность канала на основе нового лимита
            is_active = 1 if current_subs < new_limit else 0
            
            cursor.execute('''
                UPDATE channels
                SET subscriber_limit = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (new_limit, is_active, channel_id))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка при обновлении лимита канала {channel_id}: {e}")
            return False
        finally:
            conn.close()