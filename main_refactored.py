"""
Главный файл бота - рефакторинг
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Импорты настроек
from settings import *

# Импорты моделей
from models.database_init import initialize_all_tables

# Импорты сервисов
from services.external_api import SubgramService
from services.game_service import BoostService

# Импорты обработчиков
from handlers.start_handler import router as start_router
from handlers.menu_handler import router as menu_router
from handlers.subscription_handler import router as subscription_router

# Импорты утилит
from utils.middleware import AntiFloodMiddleware

# Импорты для работы с подарками
try:
    from userbot_gifts import schedule_gift, start_userbot, stop_userbot
except ImportError as e:
    print(f"Ошибка импорта userbot_gifts: {e}")
    schedule_gift = None
    start_userbot = None
    stop_userbot = None

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Создаем основной роутер
main_router = Router()

# Глобальные переменные
admin_msg = {}
message_ids = {}


async def check_user_subscriptions_and_penalize(bot: Bot):
    """Проверяет подписки пользователей и списывает награды за отписки"""
    from models.task import TaskSubscriptionModel
    from services.user_service import UserService
    
    subscriptions = TaskSubscriptionModel.get_subscriptions_to_check()
    
    logging.info(f"Проверяем {len(subscriptions)} подписок на отписки")
    
    for subscription in subscriptions:
        sub_id, user_id, task_id, task_type, task_signature, channel_id, reward_amount = subscription
        
        try:
            # Проверяем подписку пользователя на канал
            if channel_id:
                chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                is_still_subscribed = chat_member.status in ['member', 'administrator', 'creator']
            else:
                is_still_subscribed = True
            
            # Отмечаем как проверенное
            TaskSubscriptionModel.mark_subscription_checked(sub_id, is_still_subscribed)
            
            # Если отписался, списываем награду
            if not is_still_subscribed:
                user_info = UserService.get_user_info(user_id)
                current_balance = user_info['balance']
                
                if current_balance >= reward_amount:
                    UserService.update_user_balance(user_id, reward_amount, 'subtract')
                    
                    # Уведомляем пользователя
                    try:
                        await bot.send_message(
                            user_id,
                            f"⚠️ <b>Списание награды</b>\n\n"
                            f"Вы отписались от канала в течение 3 дней после выполнения задания.\n"
                            f"💰 Списано: {reward_amount} ⭐️\n\n"
                            f"Чтобы получать награды полностью, не отписывайтесь от каналов в течение 3 дней после выполнения заданий.",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logging.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                    
                    logging.info(f"Списана награда {reward_amount} у пользователя {user_id} за отписку")
                else:
                    # Если баланса недостаточно, списываем что есть
                    if current_balance > 0:
                        UserService.update_user_balance(user_id, current_balance, 'subtract')
                        
                        try:
                            await bot.send_message(
                                user_id,
                                f"⚠️ <b>Списание награды</b>\n\n"
                                f"Вы отписались от канала в течение 3 дней после выполнения задания.\n"
                                f"💰 Списано: {current_balance} ⭐️ (весь доступный баланс)\n"
                                f"💰 Задолженность: {reward_amount - current_balance:.2f} ⭐️\n\n"
                                f"Чтобы получать награды полностью, не отписывайтесь от каналов в течение 3 дней после выполнения заданий.",
                                parse_mode='HTML'
                            )
                        except Exception as e:
                            logging.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                    
                    logging.warning(f"У пользователя {user_id} недостаточно баланса для списания {reward_amount}")
        
        except Exception as e:
            logging.error(f"Ошибка при проверке подписки пользователя {user_id}: {e}")
            # Отмечаем как проверенное с ошибкой
            TaskSubscriptionModel.mark_subscription_checked(sub_id, True)


async def check_user_tasks_validity(bot: Bot):
    """Проверяет валидность пользовательских заданий"""
    from services.task_service import TaskService
    from models.task import UserTaskModel
    
    active_tasks = UserTaskModel.get_active_tasks()
    
    logging.info(f"Проверяем валидность {len(active_tasks)} активных заданий")
    
    for task in active_tasks:
        task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = task
        
        try:
            # Проверяем, является ли бот админом канала
            bot_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
            
            if bot_member.status not in ['administrator', 'creator']:
                # Бот больше не админ - отменяем задание БЕЗ возврата средств
                TaskService.cancel_user_task(task_id)
                
                # Уведомляем создателя
                try:
                    await bot.send_message(
                        creator_id,
                        f"❌ <b>Задание отменено</b>\n\n"
                        f"🆔 ID задания: {task_id}\n"
                        f"📋 Причина: Бот был удален из администраторов канала\n"
                        f"💰 Средства не возвращаются согласно правилам сервиса\n\n"
                        f"Для создания новых заданий добавьте бота обратно в администраторы канала.",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logging.error(f"Не удалось уведомить создателя {creator_id}: {e}")
                
                logging.info(f"Отменено задание {task_id} - бот не админ канала {channel_id}")
        
        except Exception as e:
            logging.error(f"Ошибка при проверке задания {task_id}: {e}")
            # Если канал недоступен, отменяем задание
            if "chat not found" in str(e).lower() or "channel not found" in str(e).lower():
                TaskService.cancel_user_task(task_id)
                
                try:
                    await bot.send_message(
                        creator_id,
                        f"❌ <b>Задание отменено</b>\n\n"
                        f"🆔 ID задания: {task_id}\n"
                        f"📋 Причина: Канал недоступен или удален\n"
                        f"💰 Средства не возвращаются согласно правилам сервиса",
                        parse_mode='HTML'
                    )
                except Exception as notify_error:
                    logging.error(f"Не удалось уведомить создателя {creator_id}: {notify_error}")
                
                logging.info(f"Отменено задание {task_id} - канал недоступен")


async def show_op(chat_id: int, links: List[str], bot: Bot, ref_id: Optional[int] = None):
    """Показывает обязательные подписки SubGram"""
    markup = InlineKeyboardBuilder()
    temp_row = []
    sponsor_count = 0
    for url in links:
        sponsor_count += 1
        name = f'Cпонсор №{sponsor_count}'
        button = types.InlineKeyboardButton(text=name, url=url)
        temp_row.append(button)
        
        if sponsor_count % 2 == 0:
            markup.row(*temp_row)
            temp_row = []
    
    if temp_row:
        markup.row(*temp_row)
    if ref_id != "None":
        item1 = types.InlineKeyboardButton(text='✅ Я подписан', callback_data=f'subgram-op:{ref_id}')
    else:
        item1 = types.InlineKeyboardButton(text='✅ Я подписан', callback_data='subgram-op')
    markup.row(item1)
    photo = FSInputFile("photos/check_subs.jpg")
    await bot.send_photo(chat_id, photo,
                        caption="<b>Для продолжения использования бота подпишись на следующие каналы наших спонсоров</b>\n\n<blockquote><b>💜Спасибо за то что вы выбрали НАС</b></blockquote>",
                        parse_mode='HTML', reply_markup=markup.as_markup())


async def periodic_tasks(bot: Bot):
    """Периодические задачи"""
    # Проверка подписок
    await check_user_subscriptions_and_penalize(bot)
    
    # Проверка валидности заданий
    await check_user_tasks_validity(bot)
    
    # Очистка просроченных бустов
    BoostService.cleanup_expired_boosts()


async def main():
    """Основная функция запуска бота"""
    # Инициализируем базу данных
    initialize_all_tables()
    
    # Создаем бота и диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Добавляем middleware
    dp.message.middleware(AntiFloodMiddleware(limit=1))
    dp.callback_query.middleware(AntiFloodMiddleware(limit=1))
    
    # Регистрируем роутеры
    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(subscription_router)
    
    # Настраиваем планировщик
    scheduler = AsyncIOScheduler()
    
    # Добавляем периодические задачи
    scheduler.add_job(
        periodic_tasks,
        'interval',
        minutes=30,
        args=[bot],
        id='periodic_tasks'
    )
    
    scheduler.start()
    
    try:
        # Запускаем userbot если доступен
        if start_userbot:
            await start_userbot()
        
        # Запускаем бота
        await dp.start_polling(bot)
    
    finally:
        # Останавливаем userbot
        if stop_userbot:
            await stop_userbot()
        
        # Останавливаем планировщик
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())