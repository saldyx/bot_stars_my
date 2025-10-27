"""
База данных - рефакторинг
Этот файл обеспечивает обратную совместимость со старым API
"""

# Импорты всех моделей
from models.user import UserModel
from models.referral import ReferralModel
from models.task import TaskModel, FlyerTaskModel, UserTaskModel, TaskSubscriptionModel
from models.channel import ChannelModel
from models.crypto import CryptoModel, ExchangeRateModel
from models.game import KNBModel, LotteryModel, BoosterModel, ClickModel, DailyGiftModel
from models.utm import UTMModel, StatisticsModel
from models.withdrawal import WithdrawalModel, PromoCodeModel
from models.database_init import initialize_all_tables

# Импорты сервисов
from services.user_service import UserService
from services.task_service import TaskService
from services.payment_service import PaymentService, WithdrawalService, PromoCodeService
from services.game_service import GameService, LotteryService, BoostService, ClickService, DailyGiftService
from services.channel_service import ChannelService
from services.utm_service import UTMService, StatisticsService

# Импорты конфигурации
from config.database import connect_db, DATABASE_NAME

# ===============================================
# ОБРАТНАЯ СОВМЕСТИМОСТЬ - Алиасы функций
# ===============================================


def connect_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_exchange_rate():
    """Инициализирует таблицу курса валют"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rate (
            id INTEGER PRIMARY KEY,
            rate REAL NOT NULL DEFAULT 1.4,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Проверяем, есть ли запись с курсом
    cursor.execute('SELECT COUNT(*) FROM exchange_rate')
    count = cursor.fetchone()[0]

    if count == 0:
        # Устанавливаем курс по умолчанию 1.4 рубля за звезду
        cursor.execute('INSERT INTO exchange_rate (rate) VALUES (1.4)')

    conn.commit()
    conn.close()


def get_exchange_rate():
    """Получает текущий курс валют"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT rate FROM exchange_rate ORDER BY id DESC LIMIT 1')
    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]
    else:
        # Если нет записи, создаем с курсом по умолчанию
        init_exchange_rate()
        return 1.4


def set_exchange_rate(new_rate):
    """Устанавливает новый курс валют"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Обновляем существующую запись или создаем новую
    cursor.execute('''
        INSERT OR REPLACE INTO exchange_rate (id, rate, updated_at) 
        VALUES (1, ?, CURRENT_TIMESTAMP)
    ''', (new_rate,))

    conn.commit()
    conn.close()


def init_crypto_payments_table():
    """Инициализирует таблицу криптоплатежей с необходимыми столбцами"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Создаем таблицу если её нет
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

    # Проверяем и добавляем недостающие столбцы
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


def init_crypto_settings_table():
    """Инициализирует таблицу настроек криптовалюты"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crypto_settings (
            id INTEGER PRIMARY KEY,
            address TEXT NOT NULL DEFAULT 'TXYourWalletAddressHere',
            network TEXT NOT NULL DEFAULT 'TRC20',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Проверяем, есть ли запись с настройками
    cursor.execute('SELECT COUNT(*) FROM crypto_settings')
    count = cursor.fetchone()[0]

    if count == 0:
        # Устанавливаем настройки по умолчанию
        cursor.execute('INSERT INTO crypto_settings (address, network) VALUES (?, ?)',
                       ('TXYourWalletAddressHere', 'TRC20'))

    conn.commit()
    conn.close()


def get_crypto_settings():
    """Получает текущие настройки криптовалюты"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT address, network FROM crypto_settings ORDER BY id DESC LIMIT 1')
    result = cursor.fetchone()

    conn.close()

    if result:
        return {'address': result[0], 'network': result[1]}
    else:
        # Если нет записи, создаем с настройками по умолчанию
        init_crypto_settings_table()
        return {'address': 'TXYourWalletAddressHere', 'network': 'TRC20'}


def update_crypto_settings(address=None, network=None):
    """Обновляет настройки криптовалюты"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def add_crypto_payment(user_id, amount, payment_method, usdt_amount):
    """Добавляет новый криптоплатеж"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO crypto_payments (user_id, amount, payment_method, usdt_amount, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (user_id, amount, payment_method, usdt_amount))

    payment_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return payment_id


def get_crypto_payment_by_id(payment_id):
    """Получает информацию о криптоплатеже по ID"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, user_id, amount, payment_method, usdt_amount, status, created_at
        FROM crypto_payments 
        WHERE id = ?
    ''', (payment_id,))

    result = cursor.fetchone()
    conn.close()

    return result


def confirm_crypto_payment(payment_id, admin_id):
    """Подтверждает криптоплатеж"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE crypto_payments 
        SET status = 'confirmed', confirmed_by = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (admin_id, payment_id))

    conn.commit()
    conn.close()


def reject_crypto_payment(payment_id, admin_id):
    """Отклоняет криптоплатеж"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE crypto_payments 
        SET status = 'rejected', rejected_by = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (admin_id, payment_id))

    conn.commit()
    conn.close()


def init_channels_table():
    """Создает таблицу каналов если она не существует"""
    # Инициализируем таблицу курса валют
    init_exchange_rate()

    # Инициализируем таблицы криптоплатежей
    init_crypto_payments_table()
    init_crypto_settings_table()

    conn = sqlite3.connect(DATABASE_NAME)
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


def add_channel(channel_id, channel_link, subscriber_limit):
    """Добавляет новый канал в базу данных"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def get_all_channels():
    """Получает все каналы из базы данных"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT channel_id, channel_link, subscriber_limit, current_subscribers, is_active
        FROM channels
    ''')
    channels = cursor.fetchall()
    conn.close()
    return channels


def get_active_channels():
    """Получает только активные каналы"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT channel_id, channel_link, subscriber_limit, current_subscribers
        FROM channels
        WHERE is_active = 1
    ''')
    channels = cursor.fetchall()
    conn.close()
    return channels


def get_channel_info(channel_id):
    """Получает информацию о конкретном канале"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT channel_id, channel_link, subscriber_limit, current_subscribers, is_active
        FROM channels
        WHERE channel_id = ?
    ''', (channel_id,))
    channel = cursor.fetchone()
    conn.close()
    return channel


def increment_channel_subscribers(channel_id):
    """Увеличивает счетчик подписчиков канала и деактивирует при достижении лимита"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def deactivate_channel(channel_id):
    """Деактивирует канал"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def activate_channel(channel_id):
    """Активирует канал"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def reset_channel_subscribers(channel_id):
    """Сбрасывает счетчик подписчиков канала и активирует его"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def delete_channel(channel_id):
    """Удаляет канал из базы данных"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def get_channels_stats():
    """Получает статистику по всем каналам"""
    conn = sqlite3.connect(DATABASE_NAME)
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


def update_channel_limit(channel_id, new_limit):
    """Обновляет лимит подписчиков для канала"""
    conn = sqlite3.connect(DATABASE_NAME)
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


# Создание таблицы для UTM-ссылок
def create_utm_stats_table():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS utm_stats (
                user_id INTEGER,
                utm TEXT,
                passed_op BOOLEAN DEFAULT 0,
                PRIMARY KEY (user_id, utm)
            );
        """)
        conn.commit()


# Добавление записи по UTM-ссылке
def add_utm_user(user_id: int, utm: str):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO utm_stats (user_id, utm) VALUES (?, ?)", (user_id, utm))
        except sqlite3.IntegrityError:
            pass  # уже есть


# Получить общее число запусков по UTM
def users_utm_count(utm: str) -> int:
    with sqlite3.connect(DATABASE_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM utm_stats WHERE utm = ?", (utm,))
        return cur.fetchone()[0]


# Получить число, кто прошёл ОП по UTM
def users_utm_count_op(utm: str) -> int:
    with sqlite3.connect(DATABASE_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM utm_stats WHERE utm = ? AND passed_op = 1", (utm,))
        return cur.fetchone()[0]


# Удаление всех записей по UTM-ссылке
def delete_utm(utm: str):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM utm_stats WHERE utm = ?", (utm,))
        conn.commit()


def mark_utm_passed(user_id: int, utm: str):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE utm_stats
            SET passed_op = 1
            WHERE user_id = ? AND utm = ?
        """, (user_id, utm))
        conn.commit()


# Пример: таблица для пропущенных заданий
def create_skipped_tasks_table():
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skipped_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_hash TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    UNIQUE(task_hash, user_id)
                )
            """)
            conn.commit()
        print("Таблица 'skipped_tasks' успешно создана или уже существует.")
    except Exception as e:
        print(f"Ошибка при создании таблицы 'skipped_tasks': {e}")


def initialize_database():
    """Инициализирует базу данных и создает таблицы, если они не существуют."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # Создание таблицы пользователей
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
        print('Таблица "users" создана')

        # Создание таблицы заданий
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
        print('Таблица "user_tasks" создана')

        # Создание таблицы подписок на задания
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
        print('Таблица "user_task_subscriptions" создана')

        # Создание таблицы баланса рекламы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ad_balance (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print('Таблица "ad_balance" создана')

        # Создание таблицы криптоплатежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                usdt_amount REAL,
                status TEXT DEFAULT 'pending',
                confirmed_by INTEGER,
                rejected_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print('Таблица "crypto_payments" создана')

        # Добавляем недостающие поля если их нет
        try:
            cursor.execute("ALTER TABLE crypto_payments ADD COLUMN usdt_amount REAL")
            print('Поле usdt_amount добавлено в таблицу "crypto_payments"')
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print('Выполнено подключение к полю usdt_amount в таблице "crypto_payments".')
            else:
                print(f"Ошибка при добавлении поля usdt_amount: {e}")

        try:
            cursor.execute("ALTER TABLE crypto_payments ADD COLUMN confirmed_by INTEGER")
            print('Поле confirmed_by добавлено в таблицу "crypto_payments"')
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print('Выполнено подключение к полю confirmed_by в таблице "crypto_payments".')
            else:
                print(f"Ошибка при добавлении поля confirmed_by: {e}")

        try:
            cursor.execute("ALTER TABLE crypto_payments ADD COLUMN rejected_by INTEGER")
            print('Поле rejected_by добавлено в таблицу "crypto_payments"')
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print('Выполнено подключение к полю rejected_by в таблице "crypto_payments".')
            else:
                print(f"Ошибка при добавлении поля rejected_by: {e}")

        try:
            cursor.execute("ALTER TABLE crypto_payments ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print('Поле updated_at добавлено в таблицу "crypto_payments"')
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print('Выполнено подключение к полю updated_at в таблице "crypto_payments".')
            else:
                print(f"Ошибка при добавлении поля updated_at: {e}")

        # Создание таблицы заданий
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
        print('Таблица "new_tasks" создана')

        try:
            cursor.execute("ALTER TABLE new_tasks ADD COLUMN id_channel_private INTEGER DEFAULT 0")
            print('Поле id_channel_private добавлено в таблицу "new_tasks"')
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print('Выполнено подключение к полю id_channel_private в таблице "new_tasks".')
            else:
                print(f"Ошибка при добавлении поля id_channel_private: {e}")

        # Создание таблицы выполненных заданий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS completed_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, task_id)
            )
        ''')
        print('Таблица "completed_tasks" создана')

        # Создание таблицы кликов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS click_times (
                user_id INTEGER PRIMARY KEY,
                last_click_time REAL NOT NULL,
                click_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print('Таблица "click_times" создана')

        # Создание таблицы ежедневных подарков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_gifts (
                user_id INTEGER PRIMARY KEY,
                last_claimed_time REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print('Таблица "daily_gifts" создана')

        # Создание таблицы выплат
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawales (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                stars REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        print('Таблица "withdrawales" создана')

        # Создание таблицы бустеров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS booster (
                id INTEGER PRIMARY KEY,
                username TEXT DEFAULT NULL,
                user_id INTEGER NOT NULL,
                end_time REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        print('Таблица "booster" создана')

        cursor.execute('PRAGMA table_info(booster)')
        columns = cursor.fetchall()
        username_column = next((col for col in columns if col[1] == 'username'), None)

        if username_column:
            if username_column[3] == 1:
                print('Столбец "username" имеет ограничение NOT NULL. Изменяем на DEFAULT NULL...')
                cursor.execute("""
                    ALTER TABLE booster
                    RENAME TO temp_booster
                """)
                cursor.execute("""
                    CREATE TABLE booster (
                        id INTEGER PRIMARY KEY,
                        username TEXT DEFAULT NULL,
                        user_id INTEGER NOT NULL,
                        end_time REAL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                cursor.execute("""
                    INSERT INTO booster (id, username, user_id, end_time)
                    SELECT id, username, user_id, end_time FROM temp_booster
                """)
                cursor.execute("DROP TABLE temp_booster")
                print('Ограничение NOT NULL удалено, установлено DEFAULT NULL.')
            else:
                print('Столбец "username" уже имеет DEFAULT NULL.')
        else:
            print('Столбец "username" не найден в таблице "booster".')

        # Создание таблицы лотереи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lottery (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                cash REAL NOT NULL,
                ticket_cash REAL NOT NULL,
                winner_id INTEGER DEFAULT NULL
            )
        """)
        print('Таблица "lottery" создана')

        # Создание таблицы данных лотереи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lottery_data (
                lottery_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                count_tickets INTEGER DEFAULT 0,
                FOREIGN KEY (lottery_id) REFERENCES lottery(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        print('Таблица "lottery_data" создана')

        # Создание таблицы knb
        cursor.execute("""
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
        """)
        print('Таблица "knb" создана')

        # Создание таблицы данных UTM
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS utm_data (
                url TEXT NOT NULL,
                count_users INTEGER DEFAULT 0,
                count_op_users INTEGER DEFAULT 0
            )
        """)
        print('Таблица "utm_data" создана')

        # Создание таблицы данных заданий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_data (
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        print('Таблица "task_data" создана')

        # Создание таблицы заданий flyer
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flyer_task (
                task_hash TEXT PRIMARY KEY
            )
        """)
        print('Таблица "flyer_task" создана')

        # Создание таблицы логгера заданий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_logger (
                user_id INTEGER NOT NULL,
                completed_at REAL DEFAULT (CAST(strftime('%s','now') AS REAL)),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        print('Таблица "task_logger" создана')

        # Создание таблицы подписок на задания
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
        print('Таблица "task_subscriptions" создана')

        conn.commit()
        conn.close()
        print('База данных успешно инициализирована.')
    except Exception as e:
        print(f"Ошибка при инициализации базы данных: {e}")
        return False


# Функции для работы с рекламным балансом
def get_ad_balance(user_id: int) -> float:
    """Получает рекламный баланс пользователя"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(ad_balance, 0) FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0.0


def update_ad_balance(user_id: int, amount: float):
    """Обновляет рекламный баланс пользователя (добавляет сумму)"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET ad_balance = COALESCE(ad_balance, 0) + ? 
            WHERE id = ?
        ''', (amount, user_id))
        conn.commit()


def transfer_to_ad_balance(user_id: int, amount: float) -> bool:
    """Переводит звезды с обычного баланса на рекламный"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()

        # Проверяем текущий баланс
        cursor.execute('SELECT stars FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()

        if not result or result[0] < amount:
            return False

        # Списываем с обычного баланса и добавляем на рекламный
        cursor.execute('''
            UPDATE users 
            SET stars = stars - ?, ad_balance = COALESCE(ad_balance, 0) + ? 
            WHERE id = ?
        ''', (amount, amount, user_id))

        conn.commit()
        return True


def deduct_ad_balance(user_id: int, amount: float) -> bool:
    """Списывает средства с рекламного баланса"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET ad_balance = COALESCE(ad_balance, 0) - ? 
            WHERE id = ? AND COALESCE(ad_balance, 0) >= ?
        ''', (amount, user_id, amount))

        success = cursor.rowcount > 0
        conn.commit()
        return success


def cancel_user_task(task_id: int) -> bool:
    """Отменяет пользовательское задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
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


def get_user_task_cost(task_id: int) -> Optional[float]:
    """Получает стоимость пользовательского задания"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT total_cost FROM user_tasks WHERE id = ?', (task_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Ошибка при получении стоимости задания: {e}")
            return None


def get_active_user_tasks() -> List[Tuple]:
    """Получает активные пользовательские задания отсортированные по приоритету"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, creator_id, post_text, post_entities, channel_id, channel_link, 
                       target_subscribers, current_subscribers
                FROM user_tasks 
                WHERE status = 'active' AND current_subscribers < target_subscribers
                ORDER BY target_subscribers DESC, created_at DESC
            ''')
            return cursor.fetchall()
        except Exception as e:
            print(f"Ошибка при получении активных заданий: {e}")
            return []


def get_pending_user_tasks() -> List[Tuple]:
    """Получает задания ожидающие модерации"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, creator_id, post_text, target_subscribers, total_cost, created_at
                FROM user_tasks 
                WHERE status = 'pending'
                ORDER BY created_at DESC
            ''')
            return cursor.fetchall()
        except Exception as e:
            print(f"Ошибка при получении заданий на модерации: {e}")
            return []


def get_all_user_tasks_for_admin():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT task_id, creator_id, post_text, post_entities, channel_id,
               channel_link, target_subscribers, current_subscribers, status
        FROM tasks
    ''')
    all_tasks = cursor.fetchall()
    conn.close()

    # Исключаем Subgram-задания по ID или ссылке
    filtered = [
        task for task in all_tasks
        if not is_subgram_task(task)
    ]
    return filtered

def is_subgram_task(task):
    # Пример: если creator_id = 777 — это Subgram
    # Или если ссылка содержит subgram
    creator_id = task[1]
    channel_link = task[5]
    return creator_id == 777 or 'subgram' in str(channel_link).lower()


# Функции для работы с пользовательскими заданиями
def create_user_task(creator_id: int, post_text: str, post_entities: str, channel_id: int, channel_link: str,
                     target_subscribers: int, total_cost: float, status: str = 'active') -> int:
    """Создает новое пользовательское задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_tasks (creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, total_cost, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, total_cost, status))
        conn.commit()
        return cursor.lastrowid


def approve_user_task(task_id: int) -> bool:
    """Одобряет пользовательское задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_tasks 
            SET status = 'active' 
            WHERE id = ? AND status = 'pending'
        ''', (task_id,))
        conn.commit()
        return cursor.rowcount > 0


def reject_user_task(task_id: int) -> bool:
    """Отклоняет пользовательское задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_tasks 
            SET status = 'rejected' 
            WHERE id = ? AND status = 'pending'
        ''', (task_id,))
        conn.commit()
        return cursor.rowcount > 0


def add_skipped_user_task(task_id: int, user_id: int):
    """Добавляет запись о пропущенном пользовательском задании"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO user_task_subscriptions (task_id, user_id, reward_given)
            VALUES (?, ?, 'skipped')
        ''', (task_id, user_id))
        conn.commit()


def is_user_task_skipped(task_id: int, user_id: int) -> bool:
    """Проверяет, пропустил ли пользователь это задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM user_task_subscriptions 
            WHERE task_id = ? AND user_id = ? AND reward_given = 'skipped'
        ''', (task_id, user_id))
        return cursor.fetchone() is not None


def get_user_tasks(creator_id: int) -> list:
    """Получает все задания пользователя"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, post_text, target_subscribers, current_subscribers, total_cost, status, created_at
            FROM user_tasks WHERE creator_id = ? ORDER BY created_at DESC
        ''', (creator_id,))
        return cursor.fetchall()


def update_task_subscribers(task_id: int):
    """Увеличивает счетчик подписчиков задания"""
    with sqlite3.connect(DATABASE_NAME) as conn:
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


def add_task_subscription(task_id: int, user_id: int):
    """Добавляет подписку пользователя на задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO user_task_subscriptions (task_id, user_id)
            VALUES (?, ?)
        ''', (task_id, user_id))
        conn.commit()


def check_task_subscription(task_id: int, user_id: int) -> bool:
    """Проверяет, выполнил ли пользователь уже это задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM user_task_subscriptions 
            WHERE task_id = ? AND user_id = ? AND reward_given = TRUE
        ''', (task_id, user_id))
        return cursor.fetchone() is not None


def mark_task_subscription_rewarded(task_id: int, user_id: int):
    """Отмечает, что пользователь получил награду за задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_task_subscriptions 
            SET reward_given = TRUE 
            WHERE task_id = ? AND user_id = ?
        ''', (task_id, user_id))
        conn.commit()


def get_task_by_id(task_id: int):
    """Получает задание по ID"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status
            FROM user_tasks WHERE id = ?
        ''', (task_id,))
        return cursor.fetchone()


def update_user_task_link(task_id: int, task_link: str):
    """Обновляет ссылку на задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE user_tasks SET task_link = ? WHERE id = ?', (task_link, task_id))
        conn.commit()


def delete_user_task(task_id: int) -> bool:
    """Удаляет пользовательское задание"""
    with sqlite3.connect(DATABASE_NAME) as conn:
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


def get_tasks_count_by_user_for_day(user_id: int) -> int:
    now_moscow = datetime.now(timezone(timedelta(hours=3)))
    start_of_day = now_moscow.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now_moscow.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_ts = start_of_day.timestamp()
    end_ts = end_of_day.timestamp()

    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM task_logger WHERE user_id = ? AND completed_at BETWEEN ? AND ?",
            (user_id, start_ts, end_ts)
        )
        result = cursor.fetchone()
    return result[0] if result is not None else 0


def get_tasks_count_by_user_for_week(user_id: int) -> int:
    now_moscow = datetime.now(timezone(timedelta(hours=3)))
    start_of_week = (now_moscow - timedelta(days=now_moscow.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)

    start_ts = start_of_week.timestamp()
    end_ts = end_of_week.timestamp()

    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM task_logger WHERE user_id = ? AND completed_at BETWEEN ? AND ?",
            (user_id, start_ts, end_ts)
        )
        result = cursor.fetchone()
    return result[0] if result is not None else 0


def get_tasks_count_by_user_for_month(user_id: int) -> int:
    now_moscow = datetime.now(timezone(timedelta(hours=3)))
    start_of_month = now_moscow.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(now_moscow.year, now_moscow.month)[1]
    end_of_month = now_moscow.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

    start_ts = start_of_month.timestamp()
    end_ts = end_of_month.timestamp()

    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM task_logger WHERE user_id = ? AND completed_at BETWEEN ? AND ?",
            (user_id, start_ts, end_ts)
        )
        result = cursor.fetchone()
    return result[0] if result is not None else 0


def add_completed_task(user_id: int) -> None:
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO task_logger (user_id) VALUES (?)", (user_id,))
        conn.commit()


def is_flyer_task_completed(task_hash):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT task_hash FROM flyer_task WHERE task_hash = ?", (task_hash,))
        return cursor.fetchone() is not None


def add_flyer_task(task_hash):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO flyer_task (task_hash) VALUES (?)", (task_hash,))
        conn.commit()
        return True


def get_urls_by_id(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM task_data WHERE user_id = ?", (user_id,))
        return [row[0] for row in cursor.fetchall()]


def add_url(user_id, url):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO task_data (user_id, url) VALUES (?, ?)", (user_id, url))
        conn.commit()
        return True


def increment_counter_tasks(user_id, count):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET count_tasker = count_tasker + ? WHERE id = ?", (count, user_id))
        conn.commit()
        return True


def get_count_tasks(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count_tasker FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return 0


def get_banned_user(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT banned FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return 0


def set_banned_user(user_id, banned):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET banned = ? WHERE id = ?", (banned, user_id))
        conn.commit()
        return True


def delete_user(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True


def create_utm(url, count_users=0):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO utm_data (url, count_users) VALUES (?, ?)", (url, count_users))
        conn.commit()
        return True


def get_urls_utm():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM utm_data")
        return [row[0] for row in cursor.fetchall()]


def users_add_utm(url):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE utm_data SET count_users = count_users + 1 WHERE url = ?", (url,))
        conn.commit()
        return True


def get_all_promocodes():
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM promocodes")
            rows = cursor.fetchall()
            promocodes = [dict(row) for row in rows]
            return promocodes
    except sqlite3.Error as e:
        print(f"Ошибка доступа к базе данных: {e}")
        return []


def users_add_utm_op(url):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE utm_data SET count_op_users = count_op_users + 1 WHERE url = ?", (url,))
        conn.commit()
        return True


def readd_username(id, username):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET username = ? WHERE id = ?", (username, id))
        conn.commit()
        return True


def get_username(id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        result = cursor.execute("SELECT username FROM users WHERE id = ?", (id,)).fetchone()
        return result[0] if result else None


def get_id_from_username(username):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        result = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        return result[0] if result else None


def set_result(id_game, choice_first, choice_second):
    with sqlite3.connect(DATABASE_NAME) as conn:
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
                bet = get_bet(id_game)
                winner = "first_player" if result.startswith("Первый") else "second_player"
                cursor.execute(
                    "SELECT first_player, second_player FROM knb WHERE id_game = ?",
                    (id_game,)
                )
                first_id, second_id = cursor.fetchone()
                winner_id = first_id if winner == "first_player" else second_id
                increment_stars(winner_id, bet * 2)

            conn.commit()
            return result

        except Exception as e:
            conn.rollback()
            raise e


def get_bet(game_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute("SELECT bet FROM knb WHERE id_game = ?", (game_id,)).fetchone()[0]


def get_choice(player_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        if player_id == "first_player":
            return cursor.execute("SELECT choice_first FROM knb WHERE first_player = ?", (player_id,)).fetchone()[0]
        elif player_id == "second_player":
            return cursor.execute("SELECT choice_second FROM knb WHERE second_player = ?", (player_id,)).fetchone()[0]
        else:
            return None


def change_choice(game_id, player_id, choice):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        if player_id == "first_player":
            cursor.execute("UPDATE knb SET choice_first = ? WHERE id_game = ?", (choice, game_id))
        elif player_id == "second_player":
            cursor.execute("UPDATE knb SET choice_second = ? WHERE id_game = ?", (choice, game_id))
        conn.commit()
        return True


def get_knb_game(game_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute("SELECT * FROM knb WHERE id_game = ?", (game_id,)).fetchone()


def create_knb(first_player, second_player, choice_first=None, choice_second=None, result=None, bet=0):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO knb (first_player, second_player, choice_first, choice_second, result, bet) VALUES (?, ?, ?, ?, ?, ?)",
            (first_player, second_player, choice_first, choice_second, result, bet))
        game_id = cursor.lastrowid
        conn.commit()
        return game_id


def delete_knb(game_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM knb WHERE id_game = ?", (game_id,))
        conn.commit()
        return True


def create_lottery(cash, ticket_cash):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO lottery (status, cash, ticket_cash) VALUES ('enabled', ?, ?)", (cash, ticket_cash))
        conn.commit()
        return True


def finish_and_update_winner():
    with sqlite3.connect(DATABASE_NAME) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        active_lottery = cursor.execute("""
            SELECT id
            FROM lottery 
            WHERE status = 'enabled'
        """).fetchone()

        if not active_lottery:
            raise ValueError("Нет активной лотереи")

        lottery_id = active_lottery[0]

        participants = cursor.execute("""
            SELECT user_id, count_tickets 
            FROM lottery_data 
            WHERE count_tickets > 0 
            AND lottery_id = ?
        """, (lottery_id,)).fetchall()

        if not participants:
            return False, None

        weighted_users = []
        for user_id, tickets in participants:
            weighted_users.extend([user_id] * tickets)

        winner_id = random.choice(weighted_users)

        cursor.execute("""
            UPDATE lottery 
            SET status = 'disabled', winner_id = ?
            WHERE id = ?
        """, (winner_id, lottery_id))

        conn.commit()
        return True, winner_id


def get_cash_in_lottery():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cash FROM lottery WHERE status = 'enabled'")
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return "Нет."


def get_ticket_cash_in_lottery():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_cash FROM lottery WHERE status = 'enabled'")
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return "Нет."


def get_id_lottery_enabled():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM lottery WHERE status = 'enabled'")
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return "Нет."


def get_count_tickets_by_user(lottery_id, user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count_tickets FROM lottery_data WHERE lottery_id = ? AND user_id = ?",
                       (lottery_id, user_id))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return 0


def add_lottery_entry(lottery_id, user_id, username, cash, count_tickets=1):
    with sqlite3.connect(DATABASE_NAME) as conn:
        if username is None:
            username = "None"
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lottery_data 
            (lottery_id, user_id, username, count_tickets)
            VALUES (?, ?, ?, ?)
        """, (lottery_id, user_id, username, count_tickets))

        cursor.execute("""
            UPDATE lottery 
            SET cash = cash + ?
            WHERE id = ?
        """, (cash, lottery_id))
        conn.commit()
        return True


def get_active_lottery_id():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM lottery WHERE status = 'enabled'")
        result = cursor.fetchone()
        return result[0] if result else None


def add_or_update_user_boost(user_id, end_time):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM booster WHERE user_id = ?", (user_id,))
        existing_record = cursor.fetchone()

        if existing_record:
            cursor.execute("UPDATE booster SET end_time = ? WHERE user_id = ?", (end_time, user_id))
        else:
            cursor.execute("INSERT INTO booster (user_id, end_time) VALUES (?, ?)", (user_id, end_time))

        conn.commit()
        return True


def remove_user_boost(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM booster WHERE user_id = ?", (user_id,))
        conn.commit()
        return True


def check_and_remove_expired_boosts():
    current_time = datetime.now().timestamp()

    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
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
    except Exception as e:
        print("Ошибка при удалении просроченных бустов:", e)


def user_in_booster(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM booster WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return True if result else False


def get_time_until_boost(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT end_time FROM booster WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            end_time = result[0]
            current_time = time.time()
            time_until_boost = end_time - current_time
            return time_until_boost
        else:
            return None


def get_clicks_by_period(period):
    if period not in ('day', 'week', 'month'):
        raise ValueError("Неизвестный период. Допустимые значения: 'day', 'week', 'month'")

    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
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

            query = """
                SELECT SUM(click_count)
                FROM click_times
                WHERE last_click_time >= ?
            """
            params = (time_threshold,)

            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0

    except sqlite3.Error as e:
        return 0
    except Exception as e:
        return 0


def get_users_by_period(period):
    if period not in ['day', 'week', 'month']:
        raise ValueError("Недопустимый период. Ожидается 'day', 'week' или 'month'.")

    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
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
            return result[0] if result else 0

    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
        return 0
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return 0


def change_status(id, status):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET status = ? WHERE id = ?', (status, id))
        conn.commit()
        return True


def get_count_ref(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT count_refs FROM users WHERE id = ?', (user_id,)).fetchone()[0]


def get_user_referrals_count(referrer_id):
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*)
                FROM users
                WHERE referral_id = ?;
            ''', (referrer_id,))
            result = cursor.fetchone()
            if result and result[0] is not None:
                return result[0]
            else:
                return 0
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
        return None


def get_id_refferer(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT referral_id FROM users WHERE id = ?', (user_id,)).fetchone()[0]


def get_withdrawn(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT withdrawn FROM users WHERE id = ?', (user_id,)).fetchone()[0]


def get_top_balance():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT username, stars FROM users ORDER BY stars DESC LIMIT 50').fetchall()


def add_withdrawale(username, user_id, stars, status='Ожидает обработки ⚙️'):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO withdrawales (username, user_id, stars, status) VALUES (?, ?, ?, ?)',
                       (username, user_id, stars, status))
        conn.commit()
        return True, cursor.lastrowid


def get_status_withdrawal(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM withdrawales WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_withdrawals(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT * FROM withdrawales WHERE user_id = ?', (user_id,)).fetchall()


def get_count_clicks(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT click_count FROM click_times WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return 0


def add_promocode(code, stars, max_uses):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO promocodes (code, stars, max_uses) VALUES (?, ?, ?)',
                           (code, stars, max_uses))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def use_promocode(code, user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
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


def get_user_refferals_list_and_username(user_id) -> list:
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT id, username FROM users WHERE referral_id = ?', (user_id,)).fetchall()


def deactivate_promocode(code):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE promocodes SET is_active = FALSE WHERE code = ?', (code,))
        conn.commit()


def add_tasker(description, reward, link=None, boter=None, max_uses=0, channelprivate_id=0):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO new_tasks (description, reward, link, bot, max_completed, id_channel_private) VALUES (?, ?, ?, ?, ?, ?)',
            (description, reward, link, boter, max_uses, channelprivate_id))
        conn.commit()


def increment_current_completed(task_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE new_tasks SET current_completed = current_completed + 1 WHERE id = ?', (task_id,))
        conn.commit()


def get_current_completed(task_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT current_completed FROM new_tasks WHERE id = ?', (task_id,)).fetchone()[0]


def get_max_completed(task_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT max_completed FROM new_tasks WHERE id = ?', (task_id,)).fetchone()[0]


def deactivate_task(task_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE new_tasks SET is_active = FALSE WHERE id = ?', (task_id,))
        conn.commit()


def delete_task(task_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM new_tasks WHERE id = ?', (task_id,))
        conn.commit()


def get_active_tasks():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT * FROM new_tasks WHERE is_active = TRUE').fetchall()


def get_completed_tasks_for_user(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT task_id FROM completed_tasks WHERE user_id = ?', (user_id,))
        return [row[0] for row in cursor.fetchall()]


def complete_task_for_user(user_id, task_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)', (user_id, task_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False, "Вы уже выполняли это задание."
        except Exception as e:
            conn.rollback()
            return False


def add_skipped_flyer_task(task_hash: str, user_id: int):
    """
    Добавляет запись о пропущенном задании в базу данных.
    """
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO skipped_tasks (task_hash, user_id) VALUES (?, ?)", (task_hash, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"ERROR: Ошибка при добавлении пропущенного задания в БД: {e}")


def is_flyer_task_skipped(task_hash: str, user_id: int) -> bool:
    """
    Проверяет, было ли задание пропущено данным пользователем.
    """
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


def get_task(task_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT * FROM new_tasks WHERE id = ?', (task_id,)).fetchone()


def get_user_count():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]


def get_total_withdrawn():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT COALESCE(SUM(withdrawn), 0.0) FROM users').fetchone()[0]


def get_normal_time_registration(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT registration_time FROM users WHERE id = ?', (user_id,)).fetchone()[0]


def update_click_count(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE click_times SET click_count = click_count + 1 WHERE user_id = ?', (user_id,))
        conn.commit()


def get_top_clicked():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT users.id, users.username, click_times.click_count
            FROM users
            JOIN click_times ON users.id = click_times.user_id
            ORDER BY click_times.click_count DESC
            LIMIT 10
        ''')
        return cursor.fetchall()


def get_last_daily_gift_time(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT last_claimed_time FROM daily_gifts WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None


def update_last_daily_gift_time(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO daily_gifts (user_id, last_claimed_time)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_claimed_time = ?
        ''', (user_id, time.time(), time.time()))
        conn.commit()


def get_last_click_time(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT last_click_time FROM click_times WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None


def update_last_click_time(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO click_times (user_id, last_click_time)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_click_time = ?
        ''', (user_id, time.time(), time.time()))
        conn.commit()


def get_users():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT id, username FROM users').fetchall()


def get_users_ids():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT id FROM users').fetchall()


def add_user(user_id, username, referral_id=None):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (id, username, stars, count_refs, referral_id) VALUES (?, ?, ?, ?, ?)',
                       (user_id, username, 0.0, 0, referral_id))
        conn.commit()


def add_withdrawal(user_id, amount, username):
    """Добавляет запись о выводе и возвращает ID этой записи."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Исправляем запрос: используем колонку 'stars' и добавляем 'status'
    cursor.execute('INSERT INTO withdrawales (user_id, stars, status, username) VALUES (?, ?, ?, ?)', (user_id, amount, 'pending', username))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id


def get_balance_user(user_id: int) -> float:
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stars FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0.0


def get_count_refs(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        result = cursor.execute('SELECT count_refs FROM users WHERE id = ?', (user_id,)).fetchone()
        return result[0]


def user_exists(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        result = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        return bool(result)


def increment_referrals(referrer_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET count_refs = count_refs + 1 WHERE id = ?', (referrer_id,))
        conn.commit()


def increment_stars(user_id: int, stars: float):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET stars = stars + ? WHERE id = ?", (stars, user_id))
        conn.commit()

def ensure_user_exists(user_id: int, username: str = None):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO users (id, username, stars, count_refs, referral_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, username or "Unknown", 0.0, 0, None)
            )
            conn.commit()


def deincrement_stars(user_id, stars):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET stars = stars - ? WHERE id = ?', (stars, user_id))
        conn.commit()


def get_top_referrals():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT id, count_refs, username FROM users ORDER BY count_refs DESC LIMIT 10').fetchall()


def sum_all_stars():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT COALESCE(SUM(stars), 0.0) FROM users').fetchone()[0]


def sum_all_withdrawn():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        return cursor.execute('SELECT COALESCE(SUM(withdrawn), 0.0) FROM users').fetchone()[0]


def get_period_timestamps(period: str) -> tuple[int, int]:
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


def get_top_referrals_formatted(period: str) -> list[str]:
    try:
        start_ts, end_ts = get_period_timestamps(period)
    except ValueError as ve:
        return [str(ve)]

    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
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


def get_weekly_referrals(user_id: int) -> int:
    try:
        start_ts, end_ts = get_period_timestamps('week')
    except ValueError as ve:
        return 0

    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*)
                FROM users
                WHERE referral_id = ?
                AND registration_time BETWEEN ? AND ?
            ''', (user_id, start_ts, end_ts))
            result = cursor.fetchone()
    except Exception as e:
        return 0

    return result[0] if result else 0


def get_user_referral_rank_formatted(user_id: int, period: str) -> str:
    try:
        start_ts, end_ts = get_period_timestamps(period)
    except ValueError as ve:
        return str(ve)

    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
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
    except Exception as e:
        return f"Ошибка при получении вашего места в топе: {e}"

    if user_referral_count > 0:
        return f"<b>🏅 Ты на {rank_value - 1} месте</b> | <code>{user_referral_count}</code> рефералов."
    else:
        return f"<b>🚫 Ты не попал в топ!</b> | <code>{user_referral_count}</code> рефералов."


# Инициализация базы данных при импорте
initialize_database()

def is_user_in_db(user_id):
    """Проверяет, существует ли пользователь в базе данных."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None