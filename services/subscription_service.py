"""
Сервис для работы с подписками
"""
import logging
from typing import List
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types.input_file import FSInputFile

from services.channel_service import ChannelService


class SubscriptionService:
    """Сервис для работы с подписками"""
    
    @staticmethod
    async def check_subscription(user_id: int, channel_ids: List[int], bot: Bot, 
                               referral_id: Optional[int] = None) -> bool:
        """Проверяет подписку пользователя на каналы"""
        if not channel_ids:
            return True
        
        # Получаем активные каналы из базы данных
        active_channels_data = ChannelService.get_active_channels()
        active_channels_dict = {row[0]: {'link': row[1], 'limit': row[2], 'current': row[3]}
                               for row in active_channels_data}
        
        markup = InlineKeyboardBuilder()
        temp_row = []
        sponsor_count = 0
        user_needs_subscription = False
        
        for channel_id in channel_ids:
            # Пропускаем каналы, которых нет в активных
            if channel_id not in active_channels_dict:
                continue
            
            try:
                chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if chat_member.status not in ['member', 'administrator', 'creator']:
                    # Используем заранее заданную ссылку из базы данных
                    channel_link = active_channels_dict[channel_id]['link']
                    
                    sponsor_count += 1
                    name = f'Спонсор №{sponsor_count}'
                    button = InlineKeyboardButton(text=name, url=channel_link)
                    temp_row.append(button)
                    
                    if sponsor_count % 2 == 0:
                        markup.row(*temp_row)
                        temp_row = []
                    
                    user_needs_subscription = True
            
            except Exception as e:
                logging.error(f"Ошибка при проверке подписки на канал {channel_id}: {e}")
                continue
        
        if user_needs_subscription:
            # Добавляем оставшиеся кнопки, если есть
            if temp_row:
                markup.row(*temp_row)
            
            # Добавляем кнопку проверки подписки
            if referral_id is not None:
                item1 = InlineKeyboardButton(text='✅ Я подписан', callback_data=f'check_subs')
            else:
                item1 = InlineKeyboardButton(text='✅ Я подписан', callback_data='check_subs')
            
            markup.row(item1)
            
            # Отправляем фото с сообщением
            try:
                photo = FSInputFile("photos/check_subs.jpg")
                await bot.send_photo(
                    user_id,
                    photo,
                    caption="<b>Для продолжения использования бота подпишись на следующие каналы наших спонсоров</b>\n\n<blockquote><b>💜Спасибо за то что вы выбрали НАС</b></blockquote>",
                    parse_mode='HTML',
                    reply_markup=markup.as_markup()
                )
            except Exception as e:
                logging.error(f"Ошибка при отправке фото: {e}")
                # Если фото не найдено, отправляем обычное сообщение
                await bot.send_message(
                    user_id,
                    "<b>Для продолжения использования бота подпишись на следующие каналы наших спонсоров</b>\n\n<blockquote><b>💜Спасибо за то что вы выбрали НАС</b></blockquote>",
                    parse_mode='HTML',
                    reply_markup=markup.as_markup()
                )
            
            return False
        
        return True
    
    @staticmethod
    async def validate_channel_link(bot: Bot, channel_id: int, generated_link: str) -> dict:
        """Проверяет работает ли сгенерированная ссылка на канал"""
        try:
            # Пытаемся получить информацию о канале по ID
            chat_info = await bot.get_chat(channel_id)
            
            # Проверяем различные варианты ссылок
            possible_links = []
            
            if chat_info.username:
                possible_links.append(f"https://t.me/{chat_info.username}")
            
            if hasattr(chat_info, 'invite_link') and chat_info.invite_link:
                possible_links.append(chat_info.invite_link)
            
            clean_id = str(channel_id).replace('-100', '')
            possible_links.append(f"https://t.me/c/{clean_id}")
            
            return {
                'is_valid': True,
                'recommended_link': possible_links[0] if possible_links else generated_link,
                'all_possible_links': possible_links,
                'channel_info': {
                    'title': chat_info.title,
                    'username': chat_info.username,
                    'type': chat_info.type,
                    'member_count': getattr(chat_info, 'member_count', 'Неизвестно')
                }
            }
        
        except Exception as e:
            logging.error(f"Ошибка валидации ссылки на канал {channel_id}: {e}")
            return {
                'is_valid': False,
                'recommended_link': generated_link,
                'error': str(e)
            }