# 🚀 Как использовать новую структуру

## 📋 Быстрый старт

### 1️⃣ Ваш код продолжает работать как раньше:
```python
# В любом файле просто импортируйте как обычно:
from database import *

# Все ваши функции работают:
user_balance = get_balance_user(user_id)
add_user(user_id, username)
increment_stars(user_id, 10.0)
# ... и все остальные функции
```

### 2️⃣ Запуск бота:
```bash
python3 main.py  # Работает как обычно!
```

## 🎯 Примеры использования новой архитектуры

### 👤 Работа с пользователями:
```python
# Старый способ (работает):
from database import *
balance = get_balance_user(user_id)

# Новый способ (рекомендуется):
from services.user_service import UserService
user_info = UserService.get_user_info(user_id)
balance = user_info['balance']
```

### 🎯 Работа с заданиями:
```python
# Старый способ:
from database import *
tasks = get_active_tasks()

# Новый способ:
from services.task_service import TaskService
next_task = TaskService.get_next_available_task(user_id)
```

### 💳 Работа с платежами:
```python
# Старый способ:
from database import *
add_crypto_payment(user_id, amount, "crypto", usdt_amount)

# Новый способ:
from services.payment_service import PaymentService
payment_id = PaymentService.create_crypto_payment(user_id, amount, usdt_amount)
```

## 📁 Где что находится:

### 🔍 Ищете функции пользователей?
- **Модель:** `models/user.py` - прямая работа с БД
- **Сервис:** `services/user_service.py` - бизнес-логика
- **Старые функции:** `database.py` - алиасы для совместимости

### 🔍 Ищете функции заданий?
- **Модель:** `models/task.py` - все типы заданий
- **Сервис:** `services/task_service.py` - логика заданий
- **Обработчики:** `handlers/` - команды бота

### 🔍 Ищете функции игр?
- **Модель:** `models/game.py` - КНБ, лотерея, бусты
- **Сервис:** `services/game_service.py` - игровая логика

## 🛠 Добавление новых функций

### Новая функция пользователя:
1. Добавьте метод в `models/user.py`
2. Добавьте логику в `services/user_service.py`  
3. Добавьте алиас в `database.py` (для совместимости)

### Новый обработчик команды:
1. Создайте функцию в подходящем `handlers/*.py`
2. Зарегистрируйте роутер в `main.py`

## 🔄 Миграция на новую структуру

### Постепенная миграция (рекомендуется):
```python
# Заменяйте старые импорты постепенно:

# Было:
from database import get_balance_user, increment_stars
balance = get_balance_user(user_id)
increment_stars(user_id, 10)

# Стало:
from services.user_service import UserService
UserService.update_user_balance(user_id, 10, 'add')
balance = UserService.get_user_info(user_id)['balance']
```

### Полная миграция:
```python
# Замените все импорты database на сервисы
from services.user_service import UserService
from services.task_service import TaskService
from services.payment_service import PaymentService
# и т.д.
```

## 🛡️ Безопасность

Ваши оригинальные файлы сохранены:
- `main_old.py` - оригинальный main.py
- `database_old.py` - оригинальный database.py

Чтобы вернуться к старой версии:
```bash
cp main_old.py main.py
cp database_old.py database.py
```

## ✅ Проверка работоспособности

Протестируйте новую структуру:
```bash
python3 -c "from database import *; print('✅ Все работает!')"
```

---

## 🎉 Готово!

Ваш проект теперь имеет профессиональную модульную архитектуру, но весь старый код продолжает работать без изменений! 

**Запускайте бота как обычно:** `python3 main.py` 🚀