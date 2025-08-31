"""
Конфигурация базы данных
"""
import sqlite3
from typing import Optional

DATABASE_NAME = 'database.db'


def connect_db() -> sqlite3.Connection:
    """Создает подключение к базе данных с оптимизированными настройками"""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_database_path() -> str:
    """Возвращает путь к файлу базы данных"""
    return DATABASE_NAME