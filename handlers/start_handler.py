"""
Обработчик команды /start
"""
import logging
import re
from aiogram import Router, types, Bot, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from services.user_service import UserService
from services.utm_service import UTMService
from services.channel_service import ChannelService
from utils.helpers import is_subgram_task

router = Router()


@router.message(CommandStart())
async def start_command(message: types.Message, bot: Bot, state: FSMContext):
    """Обработчик команды /start"""
    user = message.from_user
    user_id = user.id
    username = user.username
    args = message.text.split()
    command_arg = args[1] if len(args) > 1 else None
    
    # Проверяем, если это ссылка на пользовательское задание
    if command_arg and command_arg.startswith("user_task_"):
        task_id = int(command_arg.split("_")[-1])
        from handlers.task_handler import handle_user_task_subscription
        await handle_user_task_subscription(message, bot, task_id)
        return
    
    # Проверяем блокировку пользователя
    user_info = UserService.get_user_info(user_id)
    if user_info['banned'] == 1:
        await message.reply("<b>🚫 Вы заблокированы в боте!</b>", parse_mode='HTML')
        return
    
    is_premium = getattr(user, 'is_premium', None)
    referral_id = None
    is_utm_link = False
    
    # Обработка реферальных ссылок и UTM
    if len(args) > 1 and args[1].isdigit():
        referral_id = int(args[1])
    elif len(args) > 1:
        referral_id = args[1]
        # Проверяем, является ли это UTM-ссылкой
        urls_utm = UTMService.get_all_utm_urls()
        utm_link = f"https://t.me/{(await bot.me()).username}?start={referral_id}"
        if utm_link in urls_utm:
            is_utm_link = True
    
    # Импортируем необходимые функции из settings
    from settings import id_chat, admins_id
    
    # Обработка подписок и регистрации
    if message.chat.id != id_chat:
        if message.chat.id not in admins_id:
            # Обработка для обычных пользователей
            if not is_utm_link:
                # Проверка SubGram OP
                from services.external_api import SubgramService
                response = await SubgramService.request_op(
                    user_id=user_id,
                    chat_id=message.chat.id,
                    first_name=user.first_name,
                    language_code=user.language_code,
                    bot=bot,
                    ref_id=referral_id,
                    is_premium=is_premium
                )
                
                if response != 'ok':
                    return
                
                # Проверка админских каналов
                active_channels_data = ChannelService.get_active_channels()
                active_channel_ids = [row[0] for row in active_channels_data]
                if active_channel_ids:
                    from services.subscription_service import SubscriptionService
                    if not await SubscriptionService.check_subscription(user_id, active_channel_ids, bot, referral_id):
                        return
        else:
            # Обработка UTM-ссылок для админов
            if is_utm_link:
                urls_utm = UTMService.get_all_utm_urls()
                utm_link = f"https://t.me/{(await bot.me()).username}?start={referral_id}"
                if utm_link in urls_utm:
                    UTMService.increment_utm_users(utm_link)
                    referral_id = None
            else:
                # Обычная обработка UTM для реферальных ссылок
                urls_utm = UTMService.get_all_utm_urls()
                for url in urls_utm:
                    parts = url.split('=')
                    if len(parts) >= 2:
                        url_title = parts[1]
                        if str(referral_id) == url_title:
                            UTMService.increment_utm_users(url)
                            referral_id = None
                            break
            
            # Регистрируем пользователя если его нет
            UserService.register_user(user_id, user.username, referral_id)
    
    # Обновляем username если изменился
    UserService.update_username_if_changed(user_id, username)
    
    # Обработка глубоких ссылок
    if command_arg == "tasks":
        from handlers.task_handler import send_tasks_menu
        await send_tasks_menu(user_id, bot, user.first_name, user.language_code)
    elif command_arg == "earn_stars":
        from handlers.menu_handler import send_earn_stars_menu
        await send_earn_stars_menu(user_id, bot, user.first_name, user.language_code)
    elif command_arg == "promocode":
        from handlers.promocode_handler import send_promocode_menu
        await send_promocode_menu(user_id, bot, state)
    else:
        from handlers.menu_handler import send_main_menu
        await send_main_menu(user_id, bot)