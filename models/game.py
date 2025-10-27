"""
Модели игр и развлечений
"""
import sqlite3
import random
import time
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from config.database import connect_db


class KNBModel:
    """Модель для игры Камень-Ножницы-Бумага"""
    
    @staticmethod
    def create_table():
        """Создает таблицу для игры КНБ"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knb (
                id_game INTEGER PRIMARY KEY,
                first_player INTEGER NOT NULL,
                second_player INTEGER NOT NULL,
                choice_first TEXT DEFAULT NULL,
                choice_second TEXT DEFAULT NULL,
                result TEXT DEFAULT NULL,
                bet REAL NOT NULL,
                FOREIGN KEY (first_player) REFERENCES users(id),
                FOREIGN KEY (second_player) REFERENCES users(id)
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_game(first_player: int, second_player: int, choice_first: Optional[str] = None,
                   choice_second: Optional[str] = None, result: Optional[str] = None, bet: float = 0) -> int:
        """Создает новую игру КНБ"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO knb (first_player, second_player, choice_first, choice_second, result, bet) VALUES (?, ?, ?, ?, ?, ?)",
            (first_player, second_player, choice_first, choice_second, result, bet)
        )
        game_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return game_id
    
    @staticmethod
    def get_game(game_id: int) -> Optional[Tuple]:
        """Получает игру по ID"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute("SELECT * FROM knb WHERE id_game = ?", (game_id,)).fetchone()
        conn.close()
        return result
    
    @staticmethod
    def get_bet(game_id: int) -> float:
        """Получает ставку игры"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute("SELECT bet FROM knb WHERE id_game = ?", (game_id,)).fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def change_choice(game_id: int, player_id: str, choice: str):
        """Изменяет выбор игрока"""
        conn = connect_db()
        cursor = conn.cursor()
        if player_id == "first_player":
            cursor.execute("UPDATE knb SET choice_first = ? WHERE id_game = ?", (choice, game_id))
        elif player_id == "second_player":
            cursor.execute("UPDATE knb SET choice_second = ? WHERE id_game = ?", (choice, game_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def set_result(id_game: int, choice_first: str, choice_second: str) -> str:
        """Устанавливает результат игры"""
        from models.user import UserModel
        
        conn = connect_db()
        cursor = conn.cursor()
        
        if choice_first == choice_second:
            result = "Ничья"
        elif choice_first == "stone" and choice_second == "scissors":
            result = "Первый игрок победил!"
        elif choice_first == "scissors" and choice_second == "paper":
            result = "Первый игрок победил!"
        elif choice_first == "paper" and choice_second == "stone":
            result = "Первый игрок победил!"
        elif choice_first == "scissors" and choice_second == "stone":
            result = "Второй игрок победил!"
        elif choice_first == "paper" and choice_second == "scissors":
            result = "Второй игрок победил!"
        elif choice_first == "stone" and choice_second == "paper":
            result = "Второй игрок победил!"
        
        try:
            cursor.execute(
                "UPDATE knb SET result = ? WHERE id_game = ?",
                (result, id_game)
            )
            
            if result != "Ничья":
                bet = KNBModel.get_bet(id_game)
                winner = "first_player" if result.startswith("Первый") else "second_player"
                cursor.execute(
                    "SELECT first_player, second_player FROM knb WHERE id_game = ?",
                    (id_game,)
                )
                first_id, second_id = cursor.fetchone()
                winner_id = first_id if winner == "first_player" else second_id
                UserModel.increment_stars(winner_id, bet * 2)
            
            conn.commit()
            return result
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def delete_game(game_id: int):
        """Удаляет игру"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM knb WHERE id_game = ?", (game_id,))
        conn.commit()
        conn.close()


class LotteryModel:
    """Модель для лотереи"""
    
    @staticmethod
    def create_tables():
        """Создает таблицы для лотереи"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Таблица лотереи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lottery (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                cash REAL NOT NULL,
                ticket_cash REAL NOT NULL,
                winner_id INTEGER DEFAULT NULL
            )
        ''')
        
        # Таблица данных лотереи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lottery_data (
                lottery_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                count_tickets INTEGER DEFAULT 0,
                FOREIGN KEY (lottery_id) REFERENCES lottery(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_lottery(cash: float, ticket_cash: float):
        """Создает новую лотерею"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO lottery (status, cash, ticket_cash) VALUES ('enabled', ?, ?)", (cash, ticket_cash))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_active_lottery_id() -> Optional[int]:
        """Получает ID активной лотереи"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM lottery WHERE status = 'enabled'")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def get_cash_in_lottery() -> float:
        """Получает сумму в активной лотерее"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT cash FROM lottery WHERE status = 'enabled'")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def get_ticket_cash_in_lottery() -> float:
        """Получает стоимость билета в активной лотерее"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_cash FROM lottery WHERE status = 'enabled'")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def get_count_tickets_by_user(lottery_id: int, user_id: int) -> int:
        """Получает количество билетов пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT count_tickets FROM lottery_data WHERE lottery_id = ? AND user_id = ?",
                      (lottery_id, user_id))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def add_lottery_entry(lottery_id: int, user_id: int, username: str, cash: float, count_tickets: int = 1):
        """Добавляет участника в лотерею"""
        conn = connect_db()
        if username is None:
            username = "None"
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lottery_data 
            (lottery_id, user_id, username, count_tickets)
            VALUES (?, ?, ?, ?)
        ''', (lottery_id, user_id, username, count_tickets))
        
        cursor.execute('''
            UPDATE lottery 
            SET cash = cash + ?
            WHERE id = ?
        ''', (cash, lottery_id))
        conn.commit()
        conn.close()
    
    @staticmethod
    def finish_and_update_winner() -> Tuple[bool, Optional[int]]:
        """Завершает лотерею и выбирает победителя"""
        conn = connect_db()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        active_lottery = cursor.execute('''
            SELECT id
            FROM lottery 
            WHERE status = 'enabled'
        ''').fetchone()
        
        if not active_lottery:
            conn.close()
            raise ValueError("Нет активной лотереи")
        
        lottery_id = active_lottery[0]
        
        participants = cursor.execute('''
            SELECT user_id, count_tickets 
            FROM lottery_data 
            WHERE count_tickets > 0 
            AND lottery_id = ?
        ''', (lottery_id,)).fetchall()
        
        if not participants:
            conn.close()
            return False, None
        
        weighted_users = []
        for user_id, tickets in participants:
            weighted_users.extend([user_id] * tickets)
        
        winner_id = random.choice(weighted_users)
        
        cursor.execute('''
            UPDATE lottery 
            SET status = 'disabled', winner_id = ?
            WHERE id = ?
        ''', (winner_id, lottery_id))
        
        conn.commit()
        conn.close()
        return True, winner_id


class BoosterModel:
    """Модель для бустеров"""
    
    @staticmethod
    def create_table():
        """Создает таблицу бустеров"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS booster (
                id INTEGER PRIMARY KEY,
                username TEXT DEFAULT NULL,
                user_id INTEGER NOT NULL,
                end_time REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_or_update_user_boost(user_id: int, end_time: float):
        """Добавляет или обновляет буст пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM booster WHERE user_id = ?", (user_id,))
        existing_record = cursor.fetchone()
        
        if existing_record:
            cursor.execute("UPDATE booster SET end_time = ? WHERE user_id = ?", (end_time, user_id))
        else:
            cursor.execute("INSERT INTO booster (user_id, end_time) VALUES (?, ?)", (user_id, end_time))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def remove_user_boost(user_id: int):
        """Удаляет буст пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM booster WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def user_in_booster(user_id: int) -> bool:
        """Проверяет есть ли у пользователя буст"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM booster WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return bool(result)
    
    @staticmethod
    def get_time_until_boost(user_id: int) -> Optional[float]:
        """Получает время до окончания буста"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT end_time FROM booster WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            end_time = result[0]
            current_time = time.time()
            time_until_boost = end_time - current_time
            return time_until_boost
        else:
            return None
    
    @staticmethod
    def check_and_remove_expired_boosts():
        """Проверяет и удаляет просроченные бусты"""
        current_time = datetime.now().timestamp()
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM booster WHERE end_time < ?", (current_time,))
            expired_users = cursor.fetchall()
            
            if expired_users:
                for (user_id,) in expired_users:
                    cursor.execute("DELETE FROM booster WHERE user_id = ?", (user_id,))
                    print(f"Удален буст для пользователя с ID: {user_id}")
                conn.commit()
            else:
                print("Нет просроченных бустов.")
            conn.close()
        except Exception as e:
            print("Ошибка при удалении просроченных бустов:", e)


class ClickModel:
    """Модель для кликов"""
    
    @staticmethod
    def create_table():
        """Создает таблицу кликов"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS click_times (
                user_id INTEGER PRIMARY KEY,
                last_click_time REAL NOT NULL,
                click_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_last_click_time(user_id: int) -> Optional[float]:
        """Получает время последнего клика"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('SELECT last_click_time FROM click_times WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def update_last_click_time(user_id: int):
        """Обновляет время последнего клика"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO click_times (user_id, last_click_time)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_click_time = ?
        ''', (user_id, time.time(), time.time()))
        conn.commit()
        conn.close()
    
    @staticmethod
    def update_click_count(user_id: int):
        """Обновляет счетчик кликов"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE click_times SET click_count = click_count + 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_count_clicks(user_id: int) -> int:
        """Получает количество кликов пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('SELECT click_count FROM click_times WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def get_top_clicked() -> List[Tuple]:
        """Получает топ пользователей по кликам"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT users.id, users.username, click_times.click_count
            FROM users
            JOIN click_times ON users.id = click_times.user_id
            ORDER BY click_times.click_count DESC
            LIMIT 10
        ''')
        result = cursor.fetchall()
        conn.close()
        return result
    
    @staticmethod
    def get_clicks_by_period(period: str) -> int:
        """Получает количество кликов за период"""
        if period not in ('day', 'week', 'month'):
            raise ValueError("Неизвестный период. Допустимые значения: 'day', 'week', 'month'")
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            now = datetime.now(timezone.utc)
            
            if period == 'day':
                start_of_period = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            elif period == 'week':
                start_of_week = now - timedelta(days=now.weekday())
                start_of_period = datetime(start_of_week.year, start_of_week.month, start_of_week.day,
                                          tzinfo=timezone.utc)
            elif period == 'month':
                start_of_period = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            
            time_threshold = start_of_period.timestamp()
            
            query = '''
                SELECT SUM(click_count)
                FROM click_times
                WHERE last_click_time >= ?
            '''
            params = (time_threshold,)
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result and result[0] is not None else 0
            
        except sqlite3.Error:
            return 0
        except Exception:
            return 0


class DailyGiftModel:
    """Модель для ежедневных подарков"""
    
    @staticmethod
    def create_table():
        """Создает таблицу ежедневных подарков"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_gifts (
                user_id INTEGER PRIMARY KEY,
                last_claimed_time REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_last_daily_gift_time(user_id: int) -> Optional[float]:
        """Получает время последнего получения ежедневного подарка"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('SELECT last_claimed_time FROM daily_gifts WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def update_last_daily_gift_time(user_id: int):
        """Обновляет время последнего получения ежедневного подарка"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO daily_gifts (user_id, last_claimed_time)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_claimed_time = ?
        ''', (user_id, time.time(), time.time()))
        conn.commit()
        conn.close()