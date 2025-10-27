"""
Модель реферальной системы
"""
import sqlite3
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import calendar
from config.database import connect_db


class ReferralModel:
    """Модель для работы с реферальной системой"""
    
    @staticmethod
    def get_referral_count(user_id: int) -> int:
        """Получает количество рефералов пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT count_refs FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return result[0] if result else 0
    
    @staticmethod
    def get_referrer_id(user_id: int) -> Optional[int]:
        """Получает ID реферера пользователя"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT referral_id FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return result[0] if result else None
    
    @staticmethod
    def increment_referrals(referrer_id: int):
        """Увеличивает счетчик рефералов"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET count_refs = count_refs + 1 WHERE id = ?', (referrer_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_user_referrals_count(referrer_id: int) -> int:
        """Получает количество рефералов пользователя из базы"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*)
                FROM users
                WHERE referral_id = ?;
            ''', (referrer_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result and result[0] is not None else 0
        except sqlite3.Error as e:
            print(f"Ошибка базы данных: {e}")
            return 0
    
    @staticmethod
    def get_user_referrals_list_and_username(user_id: int) -> List[Tuple]:
        """Получает список рефералов пользователя с username"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT id, username FROM users WHERE referral_id = ?', (user_id,)).fetchall()
        conn.close()
        return result
    
    @staticmethod
    def get_top_referrals() -> List[Tuple]:
        """Получает топ пользователей по рефералам"""
        conn = connect_db()
        cursor = conn.cursor()
        result = cursor.execute('SELECT id, count_refs, username FROM users ORDER BY count_refs DESC LIMIT 10').fetchall()
        conn.close()
        return result
    
    @staticmethod
    def get_period_timestamps(period: str) -> Tuple[int, int]:
        """Получает временные метки для периода"""
        local_tz = ZoneInfo("Europe/Moscow")
        now_local = datetime.now(local_tz)
        
        if period == 'day':
            start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(seconds=1)
        elif period == 'week':
            start = now_local - timedelta(days=now_local.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7) - timedelta(seconds=1)
        elif period == 'month':
            start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start.month == 12:
                next_month = start.replace(year=start.year + 1, month=1)
            else:
                next_month = start.replace(month=start.month + 1)
            end = next_month - timedelta(seconds=1)
        else:
            raise ValueError("Неверный период времени")
        
        return int(start.timestamp()), int(end.timestamp())
    
    @staticmethod
    def get_top_referrals_formatted(period: str) -> List[str]:
        """Получает форматированный топ рефералов за период"""
        try:
            start_ts, end_ts = ReferralModel.get_period_timestamps(period)
        except ValueError as ve:
            return [str(ve)]
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u2.id, u2.username, COUNT(u1.id) as referral_count
                FROM users u1
                JOIN users u2 ON u1.referral_id = u2.id
                WHERE u1.referral_id IS NOT NULL
                AND u1.registration_time BETWEEN ? AND ?
                GROUP BY u2.id
                HAVING referral_count > 0
                ORDER BY referral_count DESC
                LIMIT 5;
            ''', (start_ts, end_ts))
            top_referrals = cursor.fetchall()
            conn.close()
        except Exception as e:
            return [f"Ошибка при получении топа рефералов: {e}"]
        
        if not top_referrals:
            return ["Нет данных о рефералах за выбранный период."]
        
        places = ["🥇", "🥈", "🥉"]
        formatted_referrals = []
        for i, (user_id, username, count) in enumerate(top_referrals):
            place = places[i] if i < 3 else '✨'
            name = username if username else f"Пользователь {user_id}"
            formatted_referrals.append(f"{place} <b>{name}</b> | Рефералов: <code>{count}</code>")
        
        return formatted_referrals
    
    @staticmethod
    def get_weekly_referrals(user_id: int) -> int:
        """Получает количество рефералов за неделю"""
        try:
            start_ts, end_ts = ReferralModel.get_period_timestamps('week')
        except ValueError:
            return 0
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*)
                FROM users
                WHERE referral_id = ?
                AND registration_time BETWEEN ? AND ?
            ''', (user_id, start_ts, end_ts))
            result = cursor.fetchone()
            conn.close()
        except Exception:
            return 0
        
        return result[0] if result else 0
    
    @staticmethod
    def get_user_referral_rank_formatted(user_id: int, period: str) -> str:
        """Получает место пользователя в топе рефералов"""
        try:
            start_ts, end_ts = ReferralModel.get_period_timestamps(period)
        except ValueError as ve:
            return str(ve)
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(id)
                FROM users
                WHERE referral_id = ? AND registration_time BETWEEN ? AND ?
            ''', (user_id, start_ts, end_ts))
            user_referral_count = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(DISTINCT referral_count) + 1
                FROM (
                    SELECT referral_id, COUNT(id) AS referral_count
                    FROM users
                    WHERE registration_time BETWEEN ? AND ?
                    GROUP BY referral_id
                    HAVING referral_count > 0
                ) AS referral_counts
                WHERE referral_count > ?
            ''', (start_ts, end_ts, user_referral_count))
            result = cursor.fetchone()
            rank_value = result[0] if result else 1
            conn.close()
        except Exception as e:
            return f"Ошибка при получении вашего места в топе: {e}"
        
        if user_referral_count > 0:
            return f"<b>🏅 Ты на {rank_value - 1} месте</b> | <code>{user_referral_count}</code> рефералов."
        else:
            return f"<b>🚫 Ты не попал в топ!</b> | <code>{user_referral_count}</code> рефералов."