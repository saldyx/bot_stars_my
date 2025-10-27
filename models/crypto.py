"""
Модель криптоплатежей
"""
import sqlite3
from typing import Optional, Tuple
from config.database import connect_db


class CryptoModel:
    """Модель для работы с криптоплатежами"""
    
    @staticmethod
    def create_tables():
        """Создает таблицы для криптоплатежей"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Таблица криптоплатежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                usdt_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                confirmed_by INTEGER,
                rejected_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица настроек криптовалюты
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto_settings (
                id INTEGER PRIMARY KEY,
                address TEXT NOT NULL DEFAULT 'TXYourWalletAddressHere',
                network TEXT NOT NULL DEFAULT 'TRC20',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Добавляем недостающие столбцы если их нет
        cursor.execute("PRAGMA table_info(crypto_payments)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'confirmed_by' not in columns:
            cursor.execute('ALTER TABLE crypto_payments ADD COLUMN confirmed_by INTEGER')
        
        if 'rejected_by' not in columns:
            cursor.execute('ALTER TABLE crypto_payments ADD COLUMN rejected_by INTEGER')
        
        if 'updated_at' not in columns:
            cursor.execute('ALTER TABLE crypto_payments ADD COLUMN updated_at TIMESTAMP')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def init_settings():
        """Инициализирует настройки криптовалюты"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Проверяем, есть ли запись с настройками
        cursor.execute('SELECT COUNT(*) FROM crypto_settings')
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Устанавливаем настройки по умолчанию
            cursor.execute('INSERT INTO crypto_settings (address, network) VALUES (?, ?)',
                          ('TXYourWalletAddressHere', 'TRC20'))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_settings() -> dict:
        """Получает текущие настройки криптовалюты"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT address, network FROM crypto_settings ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {'address': result[0], 'network': result[1]}
        else:
            # Если нет записи, создаем с настройками по умолчанию
            CryptoModel.init_settings()
            return {'address': 'TXYourWalletAddressHere', 'network': 'TRC20'}
    
    @staticmethod
    def update_settings(address: Optional[str] = None, network: Optional[str] = None):
        """Обновляет настройки криптовалюты"""
        conn = connect_db()
        cursor = conn.cursor()
        
        if address is not None:
            cursor.execute('''
                INSERT OR REPLACE INTO crypto_settings (id, address, network, updated_at) 
                SELECT 1, ?, COALESCE((SELECT network FROM crypto_settings WHERE id = 1), 'TRC20'), CURRENT_TIMESTAMP
            ''', (address,))
        
        if network is not None:
            cursor.execute('''
                INSERT OR REPLACE INTO crypto_settings (id, address, network, updated_at) 
                SELECT 1, COALESCE((SELECT address FROM crypto_settings WHERE id = 1), 'TXYourWalletAddressHere'), ?, CURRENT_TIMESTAMP
            ''', (network,))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def add_payment(user_id: int, amount: float, payment_method: str, usdt_amount: float) -> int:
        """Добавляет новый криптоплатеж"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO crypto_payments (user_id, amount, payment_method, usdt_amount, status)
            VALUES (?, ?, ?, ?, 'pending')
        ''', (user_id, amount, payment_method, usdt_amount))
        
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return payment_id
    
    @staticmethod
    def get_payment_by_id(payment_id: int) -> Optional[Tuple]:
        """Получает информацию о криптоплатеже по ID"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, amount, payment_method, usdt_amount, status, created_at
            FROM crypto_payments 
            WHERE id = ?
        ''', (payment_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result
    
    @staticmethod
    def confirm_payment(payment_id: int, admin_id: int):
        """Подтверждает криптоплатеж"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE crypto_payments 
            SET status = 'confirmed', confirmed_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (admin_id, payment_id))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def reject_payment(payment_id: int, admin_id: int):
        """Отклоняет криптоплатеж"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE crypto_payments 
            SET status = 'rejected', rejected_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (admin_id, payment_id))
        
        conn.commit()
        conn.close()


class ExchangeRateModel:
    """Модель для работы с курсом валют"""
    
    @staticmethod
    def create_table():
        """Создает таблицу курса валют"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rate (
                id INTEGER PRIMARY KEY,
                rate REAL NOT NULL DEFAULT 1.4,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def init_rate():
        """Инициализирует курс валют"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Проверяем, есть ли запись с курсом
        cursor.execute('SELECT COUNT(*) FROM exchange_rate')
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Устанавливаем курс по умолчанию 1.4 рубля за звезду
            cursor.execute('INSERT INTO exchange_rate (rate) VALUES (1.4)')
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_rate() -> float:
        """Получает текущий курс валют"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT rate FROM exchange_rate ORDER BY id DESC LIMIT 1')
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return result[0]
        else:
            # Если нет записи, создаем с курсом по умолчанию
            ExchangeRateModel.init_rate()
            return 1.4
    
    @staticmethod
    def set_rate(new_rate: float):
        """Устанавливает новый курс валют"""
        conn = connect_db()
        cursor = conn.cursor()
        
        # Обновляем существующую запись или создаем новую
        cursor.execute('''
            INSERT OR REPLACE INTO exchange_rate (id, rate, updated_at) 
            VALUES (1, ?, CURRENT_TIMESTAMP)
        ''', (new_rate,))
        
        conn.commit()
        conn.close()