"""
Модель пользователя
"""
import sqlite3
from typing import Optional, List, Tuple
from config.database import connect_db


class UserModel:
    """Модель для работы с пользователями"""
    
    @staticmethod
    def create_table():
        """Создает таблицу пользователей"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT DEFAULT NULL,
                stars REAL DEFAULT 0.0,
                count_refs INTEGER DEFAULT 0,
                referral_id INTEGER DEFAULT NULL,
                withdrawn REAL DEFAULT 0.0,
                registration_time REAL DEFAULT (strftime('%s','now')),
                ad_balance REAL DEFAULT 0.0,
                banned INTEGER DEFAULT 0,
                count_tasker INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_user(user_id: int, username: Optional[str], referral_id: Optional[int] = None):
        """Добавляет нового пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (id, username, stars, count_refs, referral_id) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, 0.0, 0, referral_id)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def user_exists(user_id: int) -> bool:
        """Проверяет существование пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return bool(result)
    
    @staticmethod
    def ensure_user_exists(user_id: int, username: str = None):
        """Обеспечивает существование пользователя в базе"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO users (id, username, stars, count_refs, referral_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, username or "Unknown", 0.0, 0, None)
            )
            conn.commit()
        conn.close()
    
    @staticmethod
    def get_balance(user_id: int) -> float:
        """Получает баланс пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT stars FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0.0
    
    @staticmethod
    def get_ad_balance(user_id: int) -> float:
        """Получает рекламный баланс пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(ad_balance, 0) FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0.0
    
    @staticmethod
    def increment_stars(user_id: int, stars: float):
        """Увеличивает баланс пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET stars = stars + ? WHERE id = ?", (stars, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def deincrement_stars(user_id: int, stars: float):
        """Уменьшает баланс пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET stars = stars - ? WHERE id = ?', (stars, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def update_ad_balance(user_id: int, amount: float):
        """Обновляет рекламный баланс пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET ad_balance = COALESCE(ad_balance, 0) + ? 
            WHERE id = ?
        ''', (amount, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def transfer_to_ad_balance(user_id: int, amount: float) -> bool:
        """Переводит звезды с обычного баланса на рекламный"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Проверяем текущий баланс
        cursor.execute('SELECT stars FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result or result[0] < amount:
            conn.close()
            return False
        
        # Списываем с обычного баланса и добавляем на рекламный
        cursor.execute('''
            UPDATE users 
            SET stars = stars - ?, ad_balance = COALESCE(ad_balance, 0) + ? 
            WHERE id = ?
        ''', (amount, amount, user_id))
        
        conn.commit()
        conn.close()
        return True
    
    @staticmethod
    def deduct_ad_balance(user_id: int, amount: float) -> bool:
        """Списывает средства с рекламного баланса"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET ad_balance = COALESCE(ad_balance, 0) - ? 
            WHERE id = ? AND COALESCE(ad_balance, 0) >= ?
        ''', (amount, user_id, amount))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    @staticmethod
    def get_username(user_id: int) -> Optional[str]:
        """Получает username пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def update_username(user_id: int, username: str):
        """Обновляет username пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_id_from_username(username: str) -> Optional[int]:
        """Получает ID пользователя по username"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def get_banned_status(user_id: int) -> int:
        """Получает статус блокировки пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT banned FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def set_banned_status(user_id: int, banned: int):
        """Устанавливает статус блокировки пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET banned = ? WHERE id = ?", (banned, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete_user(user_id: int):
        """Удаляет пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_user_count() -> int:
        """Получает общее количество пользователей"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT COUNT(*) FROM users').fetchone()
        conn.close()
        return result[0]
    
    @staticmethod
    def get_total_withdrawn() -> float:
        """Получает общую сумму выводов"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT COALESCE(SUM(withdrawn), 0.0) FROM users').fetchone()
        conn.close()
        return result[0]
    
    @staticmethod
    def get_users() -> List[Tuple]:
        """Получает всех пользователей"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT id, username FROM users').fetchall()
        conn.close()
        return result
    
    @staticmethod
    def get_users_ids() -> List[Tuple]:
        """Получает ID всех пользователей"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT id FROM users').fetchall()
        conn.close()
        return result
    
    @staticmethod
    def get_top_balance() -> List[Tuple]:
        """Получает топ пользователей по балансу"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT username, stars FROM users ORDER BY stars DESC LIMIT 50').fetchall()
        conn.close()
        return result
    
    @staticmethod
    def sum_all_stars() -> float:
        """Получает сумму всех звезд"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT COALESCE(SUM(stars), 0.0) FROM users').fetchone()
        conn.close()
        return result[0]
    
    @staticmethod
    def sum_all_withdrawn() -> float:
        """Получает сумму всех выводов"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT COALESCE(SUM(withdrawn), 0.0) FROM users').fetchone()
        conn.close()
        return result[0]
    
    @staticmethod
    def get_registration_time(user_id: int) -> Optional[float]:
        """Получает время регистрации пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT registration_time FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return result[0] if result else None