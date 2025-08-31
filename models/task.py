"""
Модель заданий
"""
import sqlite3
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
import calendar
from config.database import connect_db


class TaskModel:
    """Модель для работы с заданиями"""
    
    @staticmethod
    def create_tables():
        """Создает таблицы заданий"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Таблица новых заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS new_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                reward REAL NOT NULL,
                link TEXT DEFAULT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                bot TEXT DEFAULT 'None',
                max_completed INTEGER DEFAULT 0,
                current_completed INTEGER DEFAULT 0,
                id_channel_private INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица выполненных заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS completed_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, task_id)
            )
        ''')
        
        # Таблица логов заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_logger (
                user_id INTEGER NOT NULL,
                completed_at REAL DEFAULT (CAST(strftime('%s','now') AS REAL)),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица flyer заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flyer_task (
                task_hash TEXT PRIMARY KEY
            )
        ''')
        
        # Таблица пропущенных заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skipped_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_hash TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                UNIQUE(task_hash, user_id)
            )
        ''')
        
        # Добавляем недостающие поля если их нет
        try:
            cursor.execute("ALTER TABLE new_tasks ADD COLUMN id_channel_private INTEGER DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Ошибка при добавлении поля id_channel_private: {e}")
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_task(description: str, reward: float, link: Optional[str] = None, 
                 bot: Optional[str] = None, max_uses: int = 0, channel_private_id: int = 0):
        """Добавляет новое задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO new_tasks (description, reward, link, bot, max_completed, id_channel_private) VALUES (?, ?, ?, ?, ?, ?)',
            (description, reward, link, bot, max_uses, channel_private_id)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_task(task_id: int) -> Optional[Tuple]:
        """Получает задание по ID"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT * FROM new_tasks WHERE id = ?', (task_id,)).fetchone()
        conn.close()
        return result
    
    @staticmethod
    def get_active_tasks() -> List[Tuple]:
        """Получает активные задания"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT * FROM new_tasks WHERE is_active = TRUE').fetchall()
        conn.close()
        return result
    
    @staticmethod
    def deactivate_task(task_id: int):
        """Деактивирует задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE new_tasks SET is_active = FALSE WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete_task(task_id: int):
        """Удаляет задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM new_tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def increment_current_completed(task_id: int):
        """Увеличивает счетчик выполненных заданий"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE new_tasks SET current_completed = current_completed + 1 WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_current_completed(task_id: int) -> int:
        """Получает количество выполненных заданий"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT current_completed FROM new_tasks WHERE id = ?', (task_id,)).fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def get_max_completed(task_id: int) -> int:
        """Получает максимальное количество выполнений задания"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT max_completed FROM new_tasks WHERE id = ?', (task_id,)).fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def get_completed_tasks_for_user(user_id: int) -> List[int]:
        """Получает выполненные задания пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('SELECT task_id FROM completed_tasks WHERE user_id = ?', (user_id,))
        result = [row[0] for row in cursor.fetchall()]
        conn.close()
        return result
    
    @staticmethod
    def complete_task_for_user(user_id: int, task_id: int) -> Tuple[bool, Optional[str]]:
        """Отмечает задание как выполненное для пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)', (user_id, task_id))
            conn.commit()
            conn.close()
            return True, None
        except sqlite3.IntegrityError:
            conn.close()
            return False, "Вы уже выполняли это задание."
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, str(e)
    
    @staticmethod
    def add_completed_task_log(user_id: int):
        """Добавляет запись в лог выполненных заданий"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO task_logger (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_tasks_count_by_user_for_day(user_id: int) -> int:
        """Получает количество заданий пользователя за день"""
        now_moscow = datetime.now(timezone(timedelta(hours=3)))
        start_of_day = now_moscow.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now_moscow.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        start_ts = start_of_day.timestamp()
        end_ts = end_of_day.timestamp()
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM task_logger WHERE user_id = ? AND completed_at BETWEEN ? AND ?",
            (user_id, start_ts, end_ts)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result is not None else 0
    
    @staticmethod
    def get_tasks_count_by_user_for_week(user_id: int) -> int:
        """Получает количество заданий пользователя за неделю"""
        now_moscow = datetime.now(timezone(timedelta(hours=3)))
        start_of_week = (now_moscow - timedelta(days=now_moscow.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
        
        start_ts = start_of_week.timestamp()
        end_ts = end_of_week.timestamp()
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM task_logger WHERE user_id = ? AND completed_at BETWEEN ? AND ?",
            (user_id, start_ts, end_ts)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result is not None else 0
    
    @staticmethod
    def get_tasks_count_by_user_for_month(user_id: int) -> int:
        """Получает количество заданий пользователя за месяц"""
        now_moscow = datetime.now(timezone(timedelta(hours=3)))
        start_of_month = now_moscow.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(now_moscow.year, now_moscow.month)[1]
        end_of_month = now_moscow.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        
        start_ts = start_of_month.timestamp()
        end_ts = end_of_month.timestamp()
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM task_logger WHERE user_id = ? AND completed_at BETWEEN ? AND ?",
            (user_id, start_ts, end_ts)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result is not None else 0
    
    @staticmethod
    def increment_counter_tasks(user_id: int, count: int):
        """Увеличивает счетчик заданий пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET count_tasker = count_tasker + ? WHERE id = ?", (count, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_count_tasks(user_id: int) -> int:
        """Получает количество заданий пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT count_tasker FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0


class FlyerTaskModel:
    """Модель для работы с Flyer заданиями"""
    
    @staticmethod
    def is_task_completed(task_hash: str) -> bool:
        """Проверяет выполнено ли Flyer задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT task_hash FROM flyer_task WHERE task_hash = ?", (task_hash,))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    @staticmethod
    def add_task(task_hash: str):
        """Добавляет выполненное Flyer задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO flyer_task (task_hash) VALUES (?)", (task_hash,))
        conn.commit()
        conn.close()
        return True
    
    @staticmethod
    def add_skipped_task(task_hash: str, user_id: int):
        """Добавляет запись о пропущенном задании"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO skipped_tasks (task_hash, user_id) VALUES (?, ?)", (task_hash, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"ERROR: Ошибка при добавлении пропущенного задания в БД: {e}")
    
    @staticmethod
    def is_task_skipped(task_hash: str, user_id: int) -> bool:
        """Проверяет было ли задание пропущено пользователем"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM skipped_tasks WHERE task_hash = ? AND user_id = ?", (task_hash, user_id))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            print(f"ERROR: Ошибка при проверке пропущенного задания в БД: {e}")
            return False


class UserTaskModel:
    """Модель для пользовательских заданий"""
    
    @staticmethod
    def create_tables():
        """Создает таблицы пользовательских заданий"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Таблица пользовательских заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                post_text TEXT NOT NULL,
                post_entities TEXT,
                channel_id INTEGER,
                channel_link TEXT,
                target_subscribers INTEGER NOT NULL,
                current_subscribers INTEGER DEFAULT 0,
                cost_per_subscriber REAL DEFAULT 1.0,
                total_cost REAL NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                task_link TEXT,
                FOREIGN KEY (creator_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица подписок на пользовательские задания
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_task_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unsubscribed_at TIMESTAMP NULL,
                reward_given BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (task_id) REFERENCES user_tasks (id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(task_id, user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_task(creator_id: int, post_text: str, post_entities: str, channel_id: int, 
                   channel_link: str, target_subscribers: int, total_cost: float, 
                   status: str = 'active') -> int:
        """Создает новое пользовательское задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_tasks (creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, total_cost, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, total_cost, status))
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    @staticmethod
    def get_task_by_id(task_id: int) -> Optional[Tuple]:
        """Получает пользовательское задание по ID"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status
            FROM user_tasks WHERE id = ?
        ''', (task_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    
    @staticmethod
    def get_active_tasks() -> List[Tuple]:
        """Получает активные пользовательские задания"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, creator_id, post_text, post_entities, channel_id, channel_link, 
                       target_subscribers, current_subscribers
                FROM user_tasks 
                WHERE status = 'active' AND current_subscribers < target_subscribers
                ORDER BY target_subscribers DESC, created_at DESC
            ''')
            result = cursor.fetchall()
        except Exception as e:
            print(f"Ошибка при получении активных заданий: {e}")
            result = []
        finally:
            conn.close()
        return result
    
    @staticmethod
    def get_pending_tasks() -> List[Tuple]:
        """Получает задания ожидающие модерации"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, creator_id, post_text, target_subscribers, total_cost, created_at
                FROM user_tasks 
                WHERE status = 'pending'
                ORDER BY created_at DESC
            ''')
            result = cursor.fetchall()
        except Exception as e:
            print(f"Ошибка при получении заданий на модерации: {e}")
            result = []
        finally:
            conn.close()
        return result
    
    @staticmethod
    def get_user_tasks(creator_id: int) -> List[Tuple]:
        """Получает все задания пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, post_text, target_subscribers, current_subscribers, total_cost, status, created_at
            FROM user_tasks WHERE creator_id = ? ORDER BY created_at DESC
        ''', (creator_id,))
        result = cursor.fetchall()
        conn.close()
        return result
    
    @staticmethod
    def approve_task(task_id: int) -> bool:
        """Одобряет пользовательское задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_tasks 
            SET status = 'active' 
            WHERE id = ? AND status = 'pending'
        ''', (task_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    @staticmethod
    def reject_task(task_id: int) -> bool:
        """Отклоняет пользовательское задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_tasks 
            SET status = 'rejected' 
            WHERE id = ? AND status = 'pending'
        ''', (task_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    @staticmethod
    def cancel_task(task_id: int) -> bool:
        """Отменяет пользовательское задание"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE user_tasks 
                SET status = 'cancelled' 
                WHERE id = ? AND status = 'active'
            ''', (task_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
        except Exception as e:
            print(f"Ошибка при отмене задания: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_task_cost(task_id: int) -> Optional[float]:
        """Получает стоимость пользовательского задания"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT total_cost FROM user_tasks WHERE id = ?', (task_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Ошибка при получении стоимости задания: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def update_task_subscribers(task_id: int):
        """Увеличивает счетчик подписчиков задания"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_tasks 
            SET current_subscribers = current_subscribers + 1 
            WHERE id = ?
        ''', (task_id,))
        
        # Проверяем, достигли ли мы цели (110% от target_subscribers)
        cursor.execute('''
            SELECT target_subscribers, current_subscribers 
            FROM user_tasks WHERE id = ?
        ''', (task_id,))
        result = cursor.fetchone()
        
        if result:
            target, current = result
            if current >= target * 1.1:  # Достигли 110%
                cursor.execute('''
                    UPDATE user_tasks 
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (task_id,))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def update_task_link(task_id: int, task_link: str):
        """Обновляет ссылку на задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE user_tasks SET task_link = ? WHERE id = ?', (task_link, task_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def delete_task(task_id: int) -> bool:
        """Удаляет пользовательское задание"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            # Удаляем связанные записи из user_task_subscriptions
            cursor.execute('DELETE FROM user_task_subscriptions WHERE task_id = ?', (task_id,))
            
            # Удаляем записи из task_subscriptions если они есть
            cursor.execute('DELETE FROM task_subscriptions WHERE task_id = ? AND task_type = "user_task"', (task_id,))
            
            # Удаляем само задание
            cursor.execute('DELETE FROM user_tasks WHERE id = ?', (task_id,))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка при удалении задания {task_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


class TaskSubscriptionModel:
    """Модель для подписок на задания"""
    
    @staticmethod
    def create_table():
        """Создает таблицу подписок на задания"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER,
                task_type TEXT NOT NULL,  -- 'flyer', 'user_task', 'subgram'
                task_signature TEXT,      -- для flyer заданий
                channel_id INTEGER,       -- ID канала для проверки
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reward_amount REAL NOT NULL,
                reward_given BOOLEAN DEFAULT TRUE,
                checked_at TIMESTAMP,
                is_still_subscribed BOOLEAN DEFAULT TRUE,
                UNIQUE(user_id, task_id, task_type, task_signature)
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_subscription(task_id: int, user_id: int):
        """Добавляет подписку пользователя на задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO user_task_subscriptions (task_id, user_id)
            VALUES (?, ?)
        ''', (task_id, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def check_subscription(task_id: int, user_id: int) -> bool:
        """Проверяет выполнил ли пользователь задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM user_task_subscriptions 
            WHERE task_id = ? AND user_id = ? AND reward_given = TRUE
        ''', (task_id, user_id))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    @staticmethod
    def mark_subscription_rewarded(task_id: int, user_id: int):
        """Отмечает что пользователь получил награду за задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_task_subscriptions 
            SET reward_given = TRUE 
            WHERE task_id = ? AND user_id = ?
        ''', (task_id, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_skipped_user_task(task_id: int, user_id: int):
        """Добавляет запись о пропущенном пользовательском задании"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO user_task_subscriptions (task_id, user_id, reward_given)
            VALUES (?, ?, 'skipped')
        ''', (task_id, user_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def is_user_task_skipped(task_id: int, user_id: int) -> bool:
        """Проверяет пропустил ли пользователь задание"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM user_task_subscriptions 
            WHERE task_id = ? AND user_id = ? AND reward_given = 'skipped'
        ''', (task_id, user_id))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    @staticmethod
    def get_subscriptions_to_check() -> List[Tuple]:
        """Получает подписки которые нужно проверить (старше 3 дней)"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Получаем подписки старше 3 дней, которые еще не проверялись
        three_days_ago = datetime.now() - timedelta(days=3)
        
        cursor.execute('''
            SELECT id, user_id, task_id, task_type, task_signature, channel_id, reward_amount
            FROM task_subscriptions 
            WHERE subscribed_at <= ? 
            AND checked_at IS NULL 
            AND reward_given = TRUE
            AND is_still_subscribed = TRUE
        ''', (three_days_ago,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    @staticmethod
    def mark_subscription_checked(subscription_id: int, is_still_subscribed: bool):
        """Отмечает подписку как проверенную"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE task_subscriptions 
            SET checked_at = CURRENT_TIMESTAMP, is_still_subscribed = ?
            WHERE id = ?
        ''', (is_still_subscribed, subscription_id))
        
        conn.commit()
        conn.close()