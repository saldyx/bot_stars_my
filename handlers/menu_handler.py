"""
Обработчики меню
"""
import logging
from aiogram import Router, types, Bot, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types.input_file import FSInputFile

from services.user_service import UserService
from services.channel_service import ChannelService

router = Router()


async def send_main_menu(user_id: int, bot: Bot):
    """Отправляет главное меню"""
    try:
        # Получаем информацию о пользователе
        user_info = UserService.get_user_info(user_id)
        balance = user_info['balance']
        
        # Создаем клавиатуру главного меню
        builder = InlineKeyboardBuilder()
        builder.button(text="⭐️ Заработать звезды", callback_data="tasks")
        builder.button(text="👥 Рефералы", callback_data="referrals")
        builder.button(text="💰 Купить подписчиков", callback_data="create_task")
        builder.button(text="🎮 Игры", callback_data="games")
        builder.button(text="💸 Вывести", callback_data="withdraw")
        builder.button(text="📊 Профиль", callback_data="profile")
        markup = builder.adjust(1, 2, 1, 2).as_markup()
        
        caption = (
            f"<b>🌟 Добро пожаловать в Pixel Stars!</b>\n\n"
            f"💰 <b>Ваш баланс:</b> {balance:.2f} ⭐️\n\n"
            f"🎯 <b>Выберите действие:</b>"
        )
        
        try:
            photo = FSInputFile("photos/main_menu.jpg")
            await bot.send_photo(user_id, photo, caption=caption, parse_mode='HTML', reply_markup=markup)
        except:
            await bot.send_message(user_id, caption, parse_mode='HTML', reply_markup=markup)
    
    except Exception as e:
        logging.error(f"Ошибка при отправке главного меню: {e}")
        await bot.send_message(user_id, "❌ Произошла ошибка. Попробуйте позже.")


async def send_earn_stars_menu(user_id: int, bot: Bot, first_name: str, language_code: str):
    """Отправляет меню заработка звезд"""
    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="🎯 Задания", callback_data="tasks")
        builder.button(text="🎁 Ежедневный подарок", callback_data="daily_gift")
        builder.button(text="🖱 Клики", callback_data="click")
        builder.button(text="🎲 Промокоды", callback_data="promocodes")
        builder.button(text="⬅️ В главное меню", callback_data="back_main")
        markup = builder.adjust(2, 2, 1).as_markup()
        
        caption = (
            f"<b>⭐️ Заработать звезды</b>\n\n"
            f"Выберите способ заработка:"
        )
        
        try:
            photo = FSInputFile("photos/earn_stars.jpg")
            await bot.send_photo(user_id, photo, caption=caption, parse_mode='HTML', reply_markup=markup)
        except:
            await bot.send_message(user_id, caption, parse_mode='HTML', reply_markup=markup)
    
    except Exception as e:
        logging.error(f"Ошибка при отправке меню заработка: {e}")


@router.message(F.text == "⭐️ Заработать звезды")
async def earn_stars_keyboard_handler(message: types.Message, bot: Bot):
    """Обработчик кнопки заработка звезд"""
    user_id = message.from_user.id
    
    # Проверяем блокировку
    user_info = UserService.get_user_info(user_id)
    if user_info['banned'] == 1:
        await message.reply("🚫 Вы заблокированы в боте!", parse_mode='HTML')
        return
    
    # Проверяем подписки если не админ
    from settings import id_chat, admins_id
    chat_id = message.chat.id
    first_name = message.from_user.first_name
    language_code = message.from_user.language_code
    is_premium = getattr(message.from_user, 'is_premium', None)
    
    if chat_id != id_chat and message.chat.id not in admins_id:
        # Проверка SubGram
        from services.external_api import SubgramService
        response = await SubgramService.request_op(
            user_id=user_id,
            chat_id=chat_id,
            first_name=first_name,
            language_code=language_code,
            bot=bot,
            ref_id=None,
            is_premium=is_premium
        )
        
        if response != 'ok':
            return
        
        # Проверка админских каналов
        active_channels_data = ChannelService.get_active_channels()
        active_channel_ids = [row[0] for row in active_channels_data]
        if active_channel_ids:
            from services.subscription_service import SubscriptionService
            if not await SubscriptionService.check_subscription(user_id, active_channel_ids, bot):
                return
    
    await send_earn_stars_menu(user_id, bot, first_name, language_code)


@router.message(F.text == "💰 Купить подписчиков")
async def buy_subscribers_keyboard_handler(message: types.Message, bot: Bot):
    """Обработчик кнопки покупки подписчиков"""
    user_id = message.from_user.id
    
    # Проверяем блокировку
    user_info = UserService.get_user_info(user_id)
    if user_info['banned'] == 1:
        await message.reply("🚫 Вы заблокированы в боте!", parse_mode='HTML')
        return
    
    # Проверяем подписки если не админ
    from settings import id_chat, admins_id
    chat_id = message.chat.id
    first_name = message.from_user.first_name
    language_code = message.from_user.language_code
    is_premium = getattr(message.from_user, 'is_premium', None)
    
    if chat_id != id_chat and message.chat.id not in admins_id:
        # Проверка SubGram
        from services.external_api import SubgramService
        response = await SubgramService.request_op(
            user_id=user_id,
            chat_id=chat_id,
            first_name=first_name,
            language_code=language_code,
            bot=bot,
            ref_id=None,
            is_premium=is_premium
        )
        
        if response != 'ok':
            return
        
        # Проверка админских каналов
        active_channels_data = ChannelService.get_active_channels()
        active_channel_ids = [row[0] for row in active_channels_data]
        if active_channel_ids:
            from services.subscription_service import SubscriptionService
            if not await SubscriptionService.check_subscription(user_id, active_channel_ids, bot):
                return
    
    # Показываем меню создания задания
    from handlers.user_task_handler import create_task_menu
    await create_task_menu(user_id, bot)


@router.callback_query(F.data == "back_main")
async def back_to_main_callback(call: types.CallbackQuery, bot: Bot):
    """Возврат в главное меню"""
    try:
        await bot.delete_message(call.from_user.id, call.message.message_id)
    except:
        pass
    
    await send_main_menu(call.from_user.id, bot)