"""
Модель UTM и статистики
"""
import sqlite3
from typing import List
from config.database import connect_db


class UTMModel:
    """Модель для работы с UTM-ссылками"""
    
    @staticmethod
    def create_tables():
        """Создает таблицы для UTM"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Таблица UTM статистики
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS utm_stats (
                user_id INTEGER,
                utm TEXT,
                passed_op BOOLEAN DEFAULT 0,
                PRIMARY KEY (user_id, utm)
            )
        ''')
        
        # Таблица UTM данных
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS utm_data (
                url TEXT NOT NULL,
                count_users INTEGER DEFAULT 0,
                count_op_users INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица данных заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_data (
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_utm_user(user_id: int, utm: str):
        """Добавляет пользователя по UTM-ссылке"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO utm_stats (user_id, utm) VALUES (?, ?)", (user_id, utm))
        except sqlite3.IntegrityError:
            pass  # уже есть
        finally:
            conn.close()
    
    @staticmethod
    def users_utm_count(utm: str) -> int:
        """Получает общее число запусков по UTM"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM utm_stats WHERE utm = ?", (utm,))
        result = cursor.fetchone()[0]
        conn.close()
        return result
    
    @staticmethod
    def users_utm_count_op(utm: str) -> int:
        """Получает число кто прошел ОП по UTM"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM utm_stats WHERE utm = ? AND passed_op = 1", (utm,))
        result = cursor.fetchone()[0]
        conn.close()
        return result
    
    @staticmethod
    def delete_utm(utm: str):
        """Удаляет все записи по UTM-ссылке"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM utm_stats WHERE utm = ?", (utm,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def mark_utm_passed(user_id: int, utm: str):
        """Отмечает что пользователь прошел ОП по UTM"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE utm_stats
            SET passed_op = 1
            WHERE user_id = ? AND utm = ?
        ''', (user_id, utm))
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_utm(url: str, count_users: int = 0):
        """Создает UTM-ссылку"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO utm_data (url, count_users) VALUES (?, ?)", (url, count_users))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_urls_utm() -> List[str]:
        """Получает все UTM-ссылки"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM utm_data")
        result = [row[0] for row in cursor.fetchall()]
        conn.close()
        return result
    
    @staticmethod
    def users_add_utm(url: str):
        """Увеличивает счетчик пользователей по UTM"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE utm_data SET count_users = count_users + 1 WHERE url = ?", (url,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def users_add_utm_op(url: str):
        """Увеличивает счетчик прошедших ОП по UTM"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE utm_data SET count_op_users = count_op_users + 1 WHERE url = ?", (url,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_urls_by_id(user_id: int) -> List[str]:
        """Получает URL по ID пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM task_data WHERE user_id = ?", (user_id,))
        result = [row[0] for row in cursor.fetchall()]
        conn.close()
        return result
    
    @staticmethod
    def add_url(user_id: int, url: str):
        """Добавляет URL для пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO task_data (user_id, url) VALUES (?, ?)", (user_id, url))
        conn.commit()
        conn.close()


class StatisticsModel:
    """Модель для статистики"""
    
    @staticmethod
    def get_users_by_period(period: str) -> int:
        """Получает количество пользователей за период"""
        if period not in ['day', 'week', 'month']:
            raise ValueError("Недопустимый период. Ожидается 'day', 'week' или 'month'.")
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            
            if cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="users"').fetchone() is None:
                print('Таблица "users" не существует.')
                return 0
            
            if period == 'day':
                now = datetime.now(timezone.utc)
                start_of_period = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
                time_threshold = start_of_period.timestamp()
                query = '''
                    SELECT COUNT(*)
                    FROM users
                    WHERE registration_time >= ?
                '''
                params = (time_threshold,)
            elif period == 'week':
                now = datetime.now(timezone.utc)
                start_of_week = now - timedelta(days=now.weekday())
                start_of_period = datetime(start_of_week.year, start_of_week.month, start_of_week.day,
                                          tzinfo=timezone.utc)
                time_threshold = start_of_period.timestamp()
                query = '''
                    SELECT COUNT(*)
                    FROM users
                    WHERE registration_time >= ?
                '''
                params = (time_threshold,)
            elif period == 'month':
                query = '''
                    SELECT COUNT(*)
                    FROM users
                '''
                params = ()
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0
            
        except sqlite3.Error as e:
            print(f"Ошибка базы данных: {e}")
            return 0
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return 0