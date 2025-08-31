"""
Примеры использования новой архитектуры
"""

# ===========================================
# СТАРЫЙ СПОСОБ (все еще работает!)
# ===========================================

def old_way_example():
    """Пример старого способа - все еще работает!"""
    import database
    
    # Все функции работают как раньше
    user_id = 123456
    
    # Работа с пользователями
    if not database.user_exists(user_id):
        database.add_user(user_id, "test_user")
    
    balance = database.get_balance_user(user_id)
    database.increment_stars(user_id, 10.0)
    
    # Работа с каналами
    channels = database.get_active_channels()
    
    # Работа с заданиями
    tasks = database.get_active_tasks()
    
    print(f"✅ Старый способ работает! Баланс: {balance}")


# ===========================================
# НОВЫЙ СПОСОБ (рекомендуется!)
# ===========================================

def new_way_example():
    """Пример нового способа - более чистый код!"""
    
    # Импортируем только то, что нужно
    from services.user_service import UserService
    from services.channel_service import ChannelService  
    from services.task_service import TaskService
    
    user_id = 123456
    
    # Работа с пользователями через сервис
    if not UserService.get_user_info(user_id):
        UserService.register_user(user_id, "test_user")
    
    user_info = UserService.get_user_info(user_id)
    UserService.update_user_balance(user_id, 10.0, 'add')
    
    # Работа с каналами через сервис
    channels = ChannelService.get_active_channels()
    
    # Работа с заданиями через сервис
    next_task = TaskService.get_next_available_task(user_id)
    
    print(f"✅ Новый способ! Баланс: {user_info['balance']}")


# ===========================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ МОДЕЛЕЙ НАПРЯМУЮ
# ===========================================

def direct_model_example():
    """Пример прямого использования моделей"""
    
    from models.user import UserModel
    from models.channel import ChannelModel
    
    user_id = 123456
    
    # Прямая работа с моделями (для продвинутых случаев)
    balance = UserModel.get_balance(user_id)
    UserModel.increment_stars(user_id, 5.0)
    
    # Работа с каналами
    channel_info = ChannelModel.get_channel_info(-1001234567890)
    
    print(f"✅ Прямое использование моделей! Баланс: {balance}")


if __name__ == "__main__":
    print("🚀 Демонстрация новой архитектуры")
    print()
    
    try:
        print("1️⃣ Тестируем старый способ...")
        old_way_example()
        print()
        
        print("2️⃣ Тестируем новый способ...")
        new_way_example()
        print()
        
        print("3️⃣ Тестируем прямое использование моделей...")
        direct_model_example()
        print()
        
        print("🎉 Все способы работают отлично!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")