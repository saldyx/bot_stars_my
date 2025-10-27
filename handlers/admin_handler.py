"""
Обработчики администраторских команд
"""
import logging
from aiogram import Router, types, Bot, F
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.user_service import UserService
from services.external_api import SubgramService

router = Router()


def build_admin_keyboard():
    """Создает клавиатуру админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="💰 Управление балансом", callback_data="admin_balance")
    builder.button(text="📢 Рассылка", callback_data="admin_mailing")
    builder.button(text="🎲 Промокоды", callback_data="admin_promocodes")
    builder.button(text="📺 Каналы", callback_data="admin_channels")
    builder.button(text="🎯 Задания", callback_data="admin_tasks")
    builder.button(text="💼 Рекламный баланс", callback_data="admin_ad_balance")
    builder.button(text="💎 Криптоплатежи", callback_data="admin_crypto")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    return builder.adjust(2, 2, 2, 2, 1)


@router.message(F.text == '/adminpanel')
async def adminpanel_command(message: types.Message, bot: Bot):
    """Обработчик команды админ-панели"""
    from settings import admins_id
    
    if message.from_user.id not in admins_id:
        await bot.send_message(message.from_user.id, "<b>🚫 У вас нет доступа к панели администратора</b>",
                              parse_mode='HTML')
        return
    
    builder_admin = build_admin_keyboard()
    markup_admin = builder_admin.as_markup()
    
    try:
        user_stats = UserService.get_users_statistics()
        user_count = user_stats['total_users']
        total_withdrawn = user_stats['total_withdrawn']
        
        # Получаем баланс SubGram
        balance = await SubgramService.get_balance()
        
        msg_text = (
            f"<b>🎉 Вы вошли в панель администратора</b>\n\n"
            f"👥 Пользователей: {user_count}\n"
            f"💸 Выплачено: {total_withdrawn} ⭐️\n"
            f"💰 Баланс SubGram: {balance} ₽"
        )
        
        await bot.send_message(message.from_user.id, msg_text, parse_mode='HTML', reply_markup=markup_admin)
    
    except Exception as e:
        logging.error(f"Ошибка при получении статистики для админ-панели: {e}")
        await bot.send_message(message.from_user.id,
                              "<b>🎉 Вы вошли в панель администратора</b>\n\n⚠️ Ошибка при получении статистики.",
                              parse_mode='HTML', reply_markup=markup_admin)