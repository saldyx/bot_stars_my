"""
Обработчики подписок
"""
import logging
from aiogram import Router, types, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types.input_file import FSInputFile

from services.user_service import UserService
from services.external_api import SubgramService
from services.utm_service import UTMService

router = Router()


async def show_gender(chat_id: int, bot: Bot, ref_id: Optional[int] = None):
    """Показывает выбор пола"""
    btn_male = types.InlineKeyboardButton(text='👱‍♂️ Парень', callback_data=f'gendergram_male:{ref_id or "None"}')
    btn_female = types.InlineKeyboardButton(text='👩‍🦰 Девушка', callback_data=f'gendergram_female:{ref_id or "None"}')
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [btn_male, btn_female]
    ])
    
    await bot.send_message(
        chat_id,
        "<b>😮 Системе не удалось автоматически определить твой пол!</b>\n\nПожалуйста, укажите, <u>кто вы?</u>",
        reply_markup=markup,
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith('gendergram_'))
async def gendergram_callback(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик выбора пола"""
    import re
    
    data = call.data.split(':')
    gender = data[0].split('gendergram_')[1]
    ref_id = None
    args = call.data.split(':')
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
    elif len(args) > 1:
        ref_id = args[1]
    
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)
    
    # Блокировка по языку
    allowed_langs = ['ru', 'uk', 'uk-UA', 'be', 'kk']
    if not language_code or (language_code.lower() not in allowed_langs):
        await call.message.answer("❌ Бот недоступен в вашем регионе.")
        return
    
    # Блокировка по арабским символам
    full_name = call.from_user.full_name
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', full_name):
        await call.message.answer("❌ Бот недоступен в вашем регионе.")
        return
    
    try:
        await bot.delete_message(chat_id, call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    await state.update_data(gender=gender)
    response = await SubgramService.request_op(user_id, chat_id, first_name, language_code, bot, 
                                             ref_id=ref_id, gender=gender, is_premium=is_premium)
    
    if response == 'ok':
        if not UserService.get_user_info(user_id)['balance']:  # Если пользователя нет
            if ref_id is not None:
                from handlers.referral_handler import handle_referral_bonus
                await handle_referral_bonus(ref_id, user_id, bot)
                
                # Обработка UTM
                urls_utm = UTMService.get_all_utm_urls()
                for url in urls_utm:
                    parts = url.split('=')
                    if len(parts) >= 2:
                        url_title = parts[1]
                        if str(ref_id) == url_title:
                            UTMService.increment_utm_users(url)
                            ref_id = None
                            break
                
                UserService.register_user(user_id, call.from_user.username, ref_id)
            else:
                UserService.register_user(user_id, call.from_user.username)
        
        await bot.answer_callback_query(call.id, 'Спасибо за подписку 👍')
        await state.clear()
        from handlers.menu_handler import send_main_menu
        await send_main_menu(user_id, bot)
    else:
        await bot.answer_callback_query(call.id, '❌ Вы всё ещё не подписаны на все каналы!', show_alert=True)


async def show_op(chat_id: int, links: List[str], bot: Bot, ref_id: Optional[int] = None):
    """Показывает обязательные подписки"""
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