"""
Модель выводов и промокодов
"""
import sqlite3
from typing import Optional, List, Tuple
from config.database import connect_db


class WithdrawalModel:
    """Модель для работы с выводами"""
    
    @staticmethod
    def create_table():
        """Создает таблицу выводов"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawales (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                stars REAL NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_withdrawal(username: str, user_id: int, stars: float, status: str = 'Ожидает обработки ⚙️') -> Tuple[bool, int]:
        """Добавляет запрос на вывод"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO withdrawales (username, user_id, stars, status) VALUES (?, ?, ?, ?)',
                      (username, user_id, stars, status))
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return True, last_id
    
    @staticmethod
    def add_withdrawal_simple(user_id: int, amount: float, username: str) -> int:
        """Добавляет запись о выводе и возвращает ID"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO withdrawales (user_id, stars, status, username) VALUES (?, ?, ?, ?)', 
                      (user_id, amount, 'pending', username))
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return last_id
    
    @staticmethod
    def get_status_withdrawal(user_id: int) -> Optional[str]:
        """Получает статус вывода пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM withdrawales WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def get_withdrawals(user_id: int) -> List[Tuple]:
        """Получает все выводы пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT * FROM withdrawales WHERE user_id = ?', (user_id,)).fetchall()
        conn.close()
        return result


class PromoCodeModel:
    """Модель для работы с промокодами"""
    
    @staticmethod
    def create_tables():
        """Создает таблицы для промокодов"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Таблица промокодов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                stars REAL NOT NULL,
                max_uses INTEGER NOT NULL,
                current_uses INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица использований промокодов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS promocode_uses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                promocode_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (promocode_id) REFERENCES promocodes(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(promocode_id, user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_promocode(code: str, stars: float, max_uses: int) -> bool:
        """Добавляет новый промокод"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO promocodes (code, stars, max_uses) VALUES (?, ?, ?)',
                          (code, stars, max_uses))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    @staticmethod
    def use_promocode(code: str, user_id: int) -> Tuple[bool, str]:
        """Использует промокод"""
        from models.user import UserModel
        
        conn = connect_db()
        cursor = conn.cursor()
        try:
            promo = cursor.execute('''
                SELECT * FROM promocodes
                WHERE code = ? AND is_active = TRUE
                AND current_uses < max_uses
            ''', (code,)).fetchone()
            
            if not promo:
                return False, "Промокод недействителен или закончились использования"
            
            used = cursor.execute('''
                SELECT 1 FROM promocode_uses
                WHERE promocode_id = ? AND user_id = ?
            ''', (promo[0], user_id)).fetchone()
            
            if used:
                return False, "Вы уже использовали этот промокод"
            
            cursor.execute('''
                UPDATE promocodes
                SET current_uses = current_uses + 1
                WHERE code = ?
            ''', (code,))
            
            cursor.execute('''
                INSERT INTO promocode_uses (promocode_id, user_id)
                VALUES (?, ?)
            ''', (promo[0], user_id))
            
            cursor.execute('''
                UPDATE users
                SET stars = stars + ?
                WHERE id = ?
            ''', (promo[2], user_id))
            
            conn.commit()
            return True, promo[2]
        except Exception as e:
            conn.rollback()
            return False, f"❌ {str(e)}"
        finally:
            conn.close()
    
    @staticmethod
    def get_all_promocodes() -> List[dict]:
        """Получает все промокоды"""
        try:
            conn = connect_db()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM promocodes")
            rows = cursor.fetchall()
            promocodes = [dict(row) for row in rows]
            conn.close()
            return promocodes
        except sqlite3.Error as e:
            print(f"Ошибка доступа к базе данных: {e}")
            return []
    
    @staticmethod
    def deactivate_promocode(code: str):
        """Деактивирует промокод"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE promocodes SET is_active = FALSE WHERE code = ?', (code,))
        conn.commit()
        conn.close()