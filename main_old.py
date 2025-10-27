"""
Главный файл Telegram бота - Pixel Stars
Рефакторинг для улучшения структуры кода
"""
import asyncio
import random
import time
import logging
import re
import html
import aiohttp
import string
import json
import hashlib

from typing import Union, List, Tuple, Optional, Callable, Dict, Any, Awaitable
from flyerapi import Flyer
from collections import deque
from aiogram import Bot, Dispatcher, Router, types, F, BaseMiddleware
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, 
                          InputFile, LabeledPrice, PreCheckoutQuery, BufferedInputFile,
                          ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from aiogram.types.input_file import FSInputFile
from aiogram.exceptions import (
    TelegramAPIError, TelegramBadRequest, TelegramNotFound, TelegramForbiddenError,
    TelegramConflictError, TelegramUnauthorizedError, TelegramRetryAfter, TelegramMigrateToChat
)
from datetime import datetime, timedelta
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Импорты настроек и конфигурации
try:
    from settings import *
    from config.states import *
    
    # Импорты моделей (через обратную совместимость)
    from database_refactored import *
    
    # Импорты сервисов
    from services.user_service import UserService
    from services.task_service import TaskService
    from services.payment_service import PaymentService, WithdrawalService, PromoCodeService
    from services.game_service import GameService, LotteryService, BoostService, ClickService, DailyGiftService
    from services.channel_service import ChannelService
    from services.utm_service import UTMService, StatisticsService
    from services.external_api import SubgramService, GramAdsService
    from services.subscription_service import SubscriptionService
    
    # Импорты утилит
    from utils.helpers import get_random_value, generate_channel_link, hash_flyer_task, format_time_remaining
    from utils.captcha import generate_captcha, create_captcha_keyboard
    from utils.middleware import AntiFloodMiddleware
    from utils.flyer_integration import get_flyer_tasks, check_flyer_task
    
    # Импорты для работы с подарками
    from userbot_gifts import schedule_gift, start_userbot, stop_userbot
    
except ImportError as e:
    print(f"Ошибка импорта: {e}. Убедитесь, что все модули находятся в правильных местах.")
    exit()

flyer = Flyer(FLYER_KEY)

logging.basicConfig(level=logging.INFO)

router = Router()
admin_msg = {}
message_ids = {}



@router.message(Command("testwithdraw"))
async def test_withdraw_command(message: Message, bot: Bot):
    if message.from_user.id not in admins_id:
        return await message.reply("Эта команда только для администраторов.")

    user_id = message.from_user.id
    username = message.from_user.username
    user_full_name = message.from_user.full_name
    test_gift_id = 5170233102089322756  # 🧸 мишка
    withdrawal_id = 0  # тестовый ID
    stars = 0  # тестовые звёзды
    bot_username = (await bot.me()).username

    await message.reply(
        f"🧸 Тестовый вывод запущен.\n"
        f"Подарок (Мишка, ID: {test_gift_id}) будет отправлен через 10 секунд."
    )

    schedule_gift(
        bot=bot,
        user_id=user_id,
        username=username,
        gift_id=test_gift_id,
        delay_seconds=10,
        stars=stars,
        withdrawal_id=withdrawal_id,
        user_full_name=user_full_name,
        bot_username=bot_username
    )



class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 1):
        self.limit = limit
        self.last_time: Dict[int, float] = {}

    async def __call__(
            self,
            handler: Callable[[types.Message | types.CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: types.Message | types.CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, types.Message):
            if event.text and event.text.startswith('/start'):
                return await handler(event, data)

            user_id = event.from_user.id
            current_time = time.time()

            if user_id in self.last_time:
                last_time = self.last_time[user_id]
                if (current_time - last_time) < self.limit:
                    await event.answer("⚠️ Пожалуйста, не флудите! Ожидайте {:.0f} сек.".format(self.limit))
                    return

            self.last_time[user_id] = current_time
            return await handler(event, data)

        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id
            current_time = time.time()

            if user_id in self.last_time:
                last_time = self.last_time[user_id]
                if (current_time - last_time) < self.limit:
                    await event.answer("⚠️ Пожалуйста, не флудите! Ожидайте {:.0f} сек.".format(self.limit),
                                       show_alert=True)
                    return

            self.last_time[user_id] = current_time
            return await handler(event, data)


class ConfigStates(StatesGroup):
    waiting_for_referrals = State()
    waiting_for_tasks = State()
    waiting_for_boost = State()
    waiting_for_click = State()
    waiting_for_daily = State()


class KNBGame(StatesGroup):
    waiting_username = State()
    waiting_stake = State()


class AddUtmState(StatesGroup):
    waiting_for_url = State()
    waiting_for_delete = State()


class TheftGame(StatesGroup):
    waiting_username = State()


class LotteryState(StatesGroup):
    ticket_cash = State()


class CaptchaState(StatesGroup):
    waiting_for_answer = State()


class CaptchaClick(StatesGroup):
    waiting_click_captcha = State()


class UserTaskStates(StatesGroup):
    waiting_for_post = State()
    waiting_for_subscribers = State()
    waiting_for_payment_method = State()
    waiting_for_stars_amount = State()
    transfer_amount = State()


class AdminState(StatesGroup):
    USERS_CHECK = State()
    ADD_STARS = State()
    REMOVE_STARS = State()
    MAILING = State()
    ADD_PROMO_CODE = State()
    REMOVE_PROMO_CODE = State()
    ADD_CHANNEL = State()
    REMOVE_CHANNEL = State()
    ADD_MAX_USES = State()
    ADD_TASK = State()
    REMOVE_TASK = State()
    WAITING_FOR_BUTTONS_AFTER_STICKER = State()
    PROMOCODE_INPUT = State()
    ADD_TASK_REWARD = State()
    ADD_TASK_CHANNEL = State()
    ADD_TASK_PRIVATE = State()
    CHECK_TASK_BOT = State()
    DELETE_TASK_INPUT = State()
    DELETE_ACTIVE_TASK_INPUT = State()
    DELETE_CHANNEL_INPUT = State()
    DELETE_PROMO_INPUT = State()
    GIVE_BOOST = State()
    WAIT_TIME_BOOSTER = State()
    ADD_CHANNEL_LINK = State()
    ADD_CHANNEL_LIMIT = State()
    ADD_AD_BALANCE = State()
    CONFIRM_CRYPTO = State()
    MASS_AD_BALANCE = State()
    CRYPTO_ADDRESS = State()
    CRYPTO_NETWORK = State()
    WAITING_FOR_EXCHANGE_RATE = State()


# Инициализируем таблицу каналов при запуске
init_channels_table()


async def show_advert(user_id: int):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                'https://api.gramads.net/ad/SendPost',
                headers={
                    'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzMDI2NCIsImp0aSI6IjA0MDJjZDllLWQ2NDMtNDlhYy1iNjIzLWYyZTZmNmRhNjQ1NSIsIm5hbWUiOiJQaXhlbCBTdGFycyIsImJvdGlkIjoiMTQwMDMiLCJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9uYW1laWRlbnRpZmllciI6IjMwMjY0IiwibmJmIjoxNzQyNDc0Mzc3LCJleHAiOjE3NDI2ODMxNzcsImlzcyI6IlN0dWdub3YiLCJhdWQiOiJVc2VycyJ9.YUCZ74JjTDET7-5cgLq-VK2i6JBL92IUjmagdUUNIeA',
                    'Content-Type': 'application/json',
                },
                json={'SendToChatId': user_id}, ) as response:
            if not response.ok:
                pass


async def request_op(user_id, chat_id, first_name, language_code, bot: Bot, ref_id=None, gender=None, is_premium=None):
    headers = {
        'Content-Type': 'application/json',
        'Auth': f'{SUBGRAM_TOKEN}',
        'Accept': 'application/json',
    }
    data = {'UserId': user_id, 'ChatId': chat_id, 'first_name': first_name, 'language_code': language_code}
    if gender:
        data['Gender'] = gender
    if is_premium:
        data['Premium'] = is_premium

    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.subgram.ru/request-op-tokenless/', headers=headers, json=data) as response:
            if not response.ok or response.status != 200:
                logging.error(
                    "Ошибка при запросе SubGram. Если такая видишь такую ошибку - ставь другие настройки Subgram или проверь свой API KEY. Вот ошибка: %s" % str(
                        await response.text()))
                return 'ok'
            response_json = await response.json()

            if response_json.get('status') == 'warning':
                if ref_id:
                    await show_op(chat_id, response_json.get("links", []), bot, ref_id=ref_id)
                else:
                    await show_op(chat_id, response_json.get("links", []), bot)
            elif response_json.get('status') == 'gender':
                if ref_id:
                    await show_gender(chat_id, bot, ref_id=ref_id)
                else:
                    await show_gender(chat_id, bot)
            return response_json.get("status")


async def show_gender(chat_id, bot: Bot, ref_id=None):
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
async def gendergram(call: types.CallbackQuery, state: FSMContext, bot: Bot):
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
        logging.error(f"Ошибка при удалении сообщения 123123: {e}")
    await state.update_data(gender=gender)
    response = await request_op(user_id, chat_id, first_name, language_code, bot, ref_id=ref_id, gender=gender,
                                is_premium=is_premium)

    if response == 'ok':
        if not user_exists(user_id):
            if ref_id is not None:
                await handle_referral_bonus(ref_id, user_id, bot)
                urls_utm = get_urls_utm()
                for url in urls_utm:
                    parts = url.split('=')
                    if len(parts) >= 2:
                        url_title = parts[1]
                        if str(ref_id) == url_title:
                            users_add_utm(url)
                            ref_id = None
                            break
                # Добавляем пользователя, только если его еще нет в базе
                if not is_user_in_db(user_id):
                    add_user(user_id, call.from_user.username, ref_id)
            else:
                # Добавляем пользователя, только если его еще нет в базе
                if not is_user_in_db(user_id):
                    add_user(user_id, call.from_user.username)

        await bot.answer_callback_query(call.id, 'Спасибо за подписку 👍')
        await state.clear()
        await send_main_menu(user_id, bot)
    else:
        await bot.answer_callback_query(call.id, '❌ Вы всё ещё не подписаны на все каналы!', show_alert=True)


async def request_task(user_id, chat_id, first_name, language_code, bot: Bot):
    headers = {
        'Content-Type': 'application/json',
        'Auth': f'{SUBGRAM_TOKEN}',
        'Accept': 'application/json',
    }
    data = {'UserId': user_id, 'ChatId': chat_id, 'action': 'task', 'MaxOP': 1}

    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.subgram.ru/request-op-tokenless/', headers=headers, json=data) as response:
            if not response.ok or response.status != 200:
                logging.error(
                    "Ошибка при запросе Tasks SubGram. idk че делать при такой хуйне... спаси и сохрани епта. Вот ошибка: % s" % str(
                        await response.text()))
                return 'ok'
            response_json = await response.json()

            if response_json.get('status') == 'warning':
                await show_task(chat_id, response_json.get("links", []), bot)
            return response_json.get("status")


async def show_task(chat_id, links, bot: Bot):
    markup = InlineKeyboardBuilder()
    temp_row = []
    sponsor_count = 0
    for url in links:
        urls = get_urls_by_id(chat_id)
        if url in urls:
            continue
        sponsor_count += 1
        name = f'✅ Подписаться на канал №{sponsor_count}'
        button = types.InlineKeyboardButton(text=name, url=url)
        temp_row.append(button)

        if sponsor_count % 2 == 0:
            markup.row(*temp_row)
            temp_row = []

    if temp_row:
        markup.row(*temp_row)
    if sponsor_count > 0:
        item1 = types.InlineKeyboardButton(text='🔎 Проверить подписку', callback_data=f'subgram-task:{sponsor_count}')
        skip_task = types.InlineKeyboardButton(text='➡️ Пропустить', callback_data='skip_task')
        back_to_main = types.InlineKeyboardButton(text='⬅️ В главное меню', callback_data='back_main')
        markup.row(item1)
        markup.row(skip_task, back_to_main)
        markup.row(back_to_main)
        photo = FSInputFile("photos/check_subs.jpg")
        await bot.send_photo(chat_id=chat_id, photo=photo,
                             caption=f"<b>✨ Новое задание! ✨!\n\n• Подпишитесь на каналы, которые указаны ниже.\n\nНаграда: {task_grant[0]} ⭐️</b>\n\n📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней \"Проверить подписку\" 👇",
                             parse_mode='HTML', reply_markup=markup.as_markup())
    else:
        builder_back = InlineKeyboardBuilder()
        builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
        markup_back = builder_back.as_markup()
        await bot.send_message(chat_id=chat_id,
                               text="<b>🎯 На данный момент нет доступных заданий!\n\nВозвращайся позже!</b>",
                               parse_mode='HTML', reply_markup=markup_back)


async def show_op(chat_id, links, bot: Bot, ref_id=None):
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


def get_random_value():
    return round(random.uniform(0.1, 0.12), 2)


async def check_subscription(user_id, channel_ids, bot: Bot, refferal_id=None):
    if not channel_ids:
        return True

    # Получаем активные каналы из базы данных
    active_channels_data = get_active_channels()
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
        if refferal_id is not None:
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


def generate_captcha(difficulty=1):
    if difficulty == 1:
        min_num, max_num = 0, 9
        operators = ['+', '-', '*']
    elif difficulty == 2:
        min_num, max_num = 0, 20
        operators = ['+', '-', '*']
    else:
        min_num, max_num = 0, 50
        operators = ['+', '-', '*']

    num1 = random.randint(min_num, max_num)
    num2 = random.randint(min_num, max_num)
    operator = random.choice(operators)

    if operator == '-' and num1 < num2:
        num1, num2 = num2, num1

    question = f"<b>{num1} {operator} {num2} =</b>"

    if operator == '+':
        answer = num1 + num2
    elif operator == '-':
        answer = num1 - num2
    elif operator == '*':
        answer = num1 * num2
    else:
        answer = None

    return question, answer


def create_captcha_keyboard(correct_answer, ref_id):
    answers = set()
    answers.add(correct_answer)
    while len(answers) < 3:
        offset = random.choice([i for i in range(-5, 6) if i != 0])
        candidate = correct_answer + offset
        answers.add(candidate)
    answers_list = list(answers)
    random.shuffle(answers_list)

    builder = InlineKeyboardBuilder()
    for answer in answers_list:
        builder.button(text=str(answer), callback_data=f"captcha_{answer}_{ref_id}")
    builder.adjust(3)
    return builder.as_markup()


# Функция для получения оптимальной ссылки на канал
def generate_channel_link(channel_id: int) -> str:
    """
    Создает ссылку на канал из ID канала
    Для всех каналов создает приватную ссылку вида https://t.me/c/{clean_id}
    """
    # Убираем префикс -100 если он есть
    clean_channel_id = str(channel_id).replace('-100', '')
    return f"https://t.me/c/{clean_channel_id}"


# Функция для проверки валидности ссылки на канал
async def validate_channel_link(bot: Bot, channel_id: int, generated_link: str):
    """
    Проверяет, работает ли сгенерированная ссылка на канал
    """
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


# Функция для создания таблицы отслеживания подписок на задания
def create_task_subscriptions_table():
    """Создает таблицу для отслеживания подписок пользователей на задания"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()


def get_subscriptions_to_check():
    """Получает подписки, которые нужно проверить (старше 3 дней)"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Получаем подписки старше 3 дней, которые еще не проверялись
    three_days_ago = datetime.now() - timedelta(days=3)

    cursor.execute('''
        SELECT id, user_id, task_id, task_type, task_signature, channel_id, reward_amount
        FROM task_subscriptions 
        WHERE subscribed_at <= ? 
        AND checked_at IS NULL 
        AND reward_given = TRUE
        AND is_still_subscribed = TRUE
    ''', (three_days_ago,))

    results = cursor.fetchall()
    conn.close()
    return results


def mark_subscription_checked(subscription_id: int, is_still_subscribed: bool):
    """Отмечает подписку как проверенную"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE task_subscriptions 
        SET checked_at = CURRENT_TIMESTAMP, is_still_subscribed = ?
        WHERE id = ?
    ''', (is_still_subscribed, subscription_id))

    conn.commit()
    conn.close()


async def check_user_subscriptions_and_penalize(bot: Bot):
    """Проверяет подписки пользователей и списывает награды за отписки"""
    subscriptions = get_subscriptions_to_check()

    logging.info(f"Проверяем {len(subscriptions)} подписок на отписки")

    for subscription in subscriptions:
        sub_id, user_id, task_id, task_type, task_signature, channel_id, reward_amount = subscription

        try:
            # Проверяем подписку пользователя на канал
            if channel_id:
                chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                is_still_subscribed = chat_member.status in ['member', 'administrator', 'creator']
            else:
                is_still_subscribed = True  # Если нет channel_id, считаем что подписка есть

            # Отмечаем как проверенное
            mark_subscription_checked(sub_id, is_still_subscribed)

            # Если отписался, списываем награду
            if not is_still_subscribed:
                current_balance = get_balance_user(user_id)
                if current_balance >= reward_amount:
                    deincrement_stars(user_id, reward_amount)

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
                    # Если баланса недостаточно, все равно списываем что есть
                    if current_balance > 0:
                        deincrement_stars(user_id, current_balance)

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
            mark_subscription_checked(sub_id, True)


# ИЗМЕНЕНИЕ 1: Обновленная функция проверки валидности пользовательских заданий
async def check_user_tasks_validity(bot: Bot):
    """Проверяет валидность пользовательских заданий"""
    active_tasks = get_active_user_tasks()

    logging.info(f"Проверяем валидность {len(active_tasks)} активных заданий")

    for task in active_tasks:
        task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = task

        try:
            # Проверяем, является ли бот админом канала
            bot_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)

            if bot_member.status not in ['administrator', 'creator']:
                # Бот больше не админ - отменяем задание БЕЗ возврата средств
                cancel_user_task(task_id)

                # Уведомляем создателя (без возврата средств)
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

                logging.info(f"Отменено задание {task_id} - бот не админ канала {channel_id}, средства НЕ возвращены")

        except Exception as e:
            logging.error(f"Ошибка при проверке задания {task_id}: {e}")
            # Если не можем проверить статус бота (например, канал удален), отменяем задание
            if "chat not found" in str(e).lower() or "channel not found" in str(e).lower():
                cancel_user_task(task_id)

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

                logging.info(f"Отменено задание {task_id} - канал недоступен, средства НЕ возвращены")


@router.message(CommandStart())
async def start_command(message: Message, bot: Bot, state: FSMContext):
    user = message.from_user
    user_id = user.id
    username = user.username
    args = message.text.split()
    command_arg = args[1] if len(args) > 1 else None

    # Проверяем, если это ссылка на пользовательское задание
    if command_arg and command_arg.startswith("user_task_"):
        task_id = int(command_arg.split("_")[-1])
        await handle_user_task_subscription(message, bot, task_id)
        return

    banned = get_banned_user(user_id)
    if banned == 1:
        await message.reply("<b>🚫 Вы заблокированы в боте!</b>", parse_mode='HTML')
        return

    is_premium = getattr(user, 'is_premium', None)
    referral_id = None
    is_utm_link = False  # Флаг для определения UTM-ссылки

    if len(args) > 1 and args[1].isdigit():
        referral_id = int(args[1])
    elif len(args) > 1:
        referral_id = args[1]
        # Проверяем, является ли это UTM-ссылкой
        urls_utm = get_urls_utm()
        utm_link = f"https://t.me/{(await bot.me()).username}?start={referral_id}"
        if utm_link in urls_utm:
            is_utm_link = True

    if message.chat.id != id_chat:
        if message.chat.id not in admins_id:
            # Пропускаем проверку SubGram для UTM-ссылок
            if not is_utm_link:
                # ПРИОРИТЕТ 1: SubGram обязательная подписка
                response = await request_op(
                    user_id=user_id,
                    chat_id=message.chat.id,
                    first_name=user.first_name,
                    language_code=user.language_code,
                    bot=bot,
                    ref_id=referral_id,
                    is_premium=is_premium
                )

                if response != 'ok':
                    # Если SubGram показал обязательную подписку, останавливаемся здесь
                    # НЕ проверяем админские каналы
                    return

                # ПРИОРИТЕТ 2: Только если SubGram прошел, проверяем админские каналы
                active_channels_data = get_active_channels()
                active_channel_ids = [row[0] for row in active_channels_data]
                if active_channel_ids and not await check_subscription(user_id, active_channel_ids, bot, referral_id):
                    # Если админские каналы показали подписку, останавливаемся здесь
                    return

        else:
            # Обработка UTM-ссылок
            if is_utm_link:
                urls_utm = get_urls_utm()
                utm_link = f"https://t.me/{(await bot.me()).username}?start={referral_id}"
                if utm_link in urls_utm:
                    users_add_utm(utm_link)
                    referral_id = None  # Сбрасываем referral_id для UTM
            else:
                # Обычная обработка UTM для реферальных ссылок
                urls_utm = get_urls_utm()
                for url in urls_utm:
                    parts = url.split('=')
                    if len(parts) >= 2:
                        url_title = parts[1]
                        if str(referral_id) == url_title:
                            users_add_utm(url)
                            referral_id = None
                            break

            # Добавляем пользователя, только если его еще нет в базе
            if not is_user_in_db(user_id):
                add_user(user_id, user.username, referral_id)

    cur_username = get_username(user_id)
    if cur_username != username:
        readd_username(user_id, username)

    # Проверяем аргумент команды /start для "глубоких ссылок"
    if command_arg == "tasks":
        await send_tasks_menu(user_id, bot, user.first_name, user.language_code)
    elif command_arg == "earn_stars":
        await send_earn_stars_menu(user_id, bot, user.first_name, user.language_code)
    elif command_arg == "promocode":
        await send_promocode_menu(user_id, bot, state)
    else:
        await send_main_menu(user_id, bot)


@router.callback_query(CaptchaState.waiting_for_answer)
async def process_captcha(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username if callback_query.from_user.username else None
    try:
        if not callback_query.data.startswith("captcha_"):
            await bot.answer_callback_query(callback_query.id, "❌ Неизвестный формат данных.")
            return

        parts = callback_query.data.split('_')
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query.id, "❌ Неверный формат данных.")
            return

        user_answer = int(parts[1])
        referal = int(parts[2])

        data = await state.get_data()
        captcha_answer = data.get('captcha_answer')
        if captcha_answer is None:
            await bot.answer_callback_query(callback_query.id, "❌ Ошибка проверки, попробуйте заново.")
            return

        if user_answer == captcha_answer:
            # Добавляем пользователя, только если его еще нет в базе
            if not is_user_in_db(user_id):
                add_user(user_id, username, referal)
            await bot.answer_callback_query(callback_query.id, "✅ Вы ответили верно!")
            c_refs = get_user_referrals_count(referal)
            increment_referrals(referal)
            if c_refs < 50:
                nac = nac_1[0] * 2 if user_in_booster(referal) else nac_1[0]
                increment_stars(referal, nac)
            elif 50 <= c_refs < 250:
                nac = nac_2[0] * 2 if user_in_booster(referal) else nac_2[0]
                increment_stars(referal, nac)
            else:
                nac = nac_3[0] * 2 if user_in_booster(referal) else nac_3[0]
                increment_stars(referal, nac)

            new_ref_link = f"https://t.me/{(await bot.me()).username}?start={referal}"
            await bot.send_message(
                referal,
                f"🎉 Пользователь <code>{user_id}</code> запустил бота по вашей ссылке!\n"
                f"Вы получили +{nac}⭐️ за реферала.\n"
                f"Поделитесь ссылкой ещё раз:\n<code>{new_ref_link}</code>",
                parse_mode='HTML'
            )

            await bot.delete_message(user_id, callback_query.message.message_id)
            await send_main_menu(user_id, bot)
            await state.clear()
        else:
            await bot.answer_callback_query(callback_query.id, "❌ Вы ответили неверно! Попробуйте ещё раз",
                                            show_alert=True)
    except Exception as e:
        print(f"Ошибка в process_captcha: {e}")
        await bot.answer_callback_query(callback_query.id, "❌ Произошла ошибка. Попробуйте ещё раз.")


@router.message(F.text == '/adminpanel')
async def adminpanel_command(message: Message, bot: Bot):
    if message.from_user.id not in admins_id:
        await bot.send_message(message.from_user.id, "<b>🚫 У вас нет доступа к панели администратора</b>",
                               parse_mode='HTML')
        return

    builder_admin = build_admin_keyboard()
    markup_admin = builder_admin.as_markup()

    try:
        user_count = get_user_count()
        total_withdrawn = get_total_withdrawn()

        headers = {
            'Content-Type': 'application/json',
            'Auth': SUBGRAM_TOKEN,
            'Accept': 'application/json'
        }
        balance = 0
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://api.subgram.ru/get-balance/', headers=headers) as resp:
                    if resp.status == 200:
                        response_json = await resp.json()
                        balance = response_json.get('balance', 0)
                    else:
                        logging.error(f"Ошибка HTTP при получении баланса SubGram: статус {resp.status}")
        except Exception as e:
            logging.error(f"Ошибка при получении баланса: {e}")

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


@router.message(F.text == "⭐️ Заработать звезды")
async def earn_stars_keyboard_handler(message: Message, bot: Bot):
    user_id = message.from_user.id

    banned = get_banned_user(user_id)
    if banned == 1:
        await message.reply("🚫 Вы заблокированы в боте!", parse_mode='HTML')
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    first_name = message.from_user.first_name
    language_code = message.from_user.language_code
    is_premium = getattr(message.from_user, 'is_premium', None)

    # Проверка SubGram OP (если не админ)
    if chat_id != id_chat:
        if message.chat.id not in admins_id:
            response = await request_op(
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

            # Получаем активные каналы из базы данных
            active_channels_data = get_active_channels()
            active_channel_ids = [row[0] for row in active_channels_data]
            if active_channel_ids and not await check_subscription(user_id, active_channel_ids, bot):
                return

    # Вызываем функцию earn_stars вместо send_main_menu
    await send_earn_stars_menu(user_id, bot, first_name, language_code)


@router.message(F.text == "💰 Купить подписчиков")
async def buy_subscribers_keyboard_handler(message: Message, bot: Bot):
    user_id = message.from_user.id

    banned = get_banned_user(user_id)
    if banned == 1:
        await message.reply("🚫 Вы заблокированы в боте!", parse_mode='HTML')
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    first_name = message.from_user.first_name
    language_code = message.from_user.language_code
    is_premium = getattr(message.from_user, 'is_premium', None)

    # Проверка SubGram OP (если не админ)
    if chat_id != id_chat:
        if message.chat.id not in admins_id:
            response = await request_op(
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

            # Получаем активные каналы из базы данных
            active_channels_data = get_active_channels()
            active_channel_ids = [row[0] for row in active_channels_data]
            if active_channel_ids and not await check_subscription(user_id, active_channel_ids, bot):
                return

    # Вызываем функцию создания задания
    await create_task_menu_call_simulation(message, bot)


async def create_task_menu_call_simulation(message: Message, bot: Bot):
    """Симулирует callback для create_task_menu"""
    user_id = message.from_user.id

    # Получаем балансы пользователя
    regular_balance = get_balance_user(user_id)
    ad_balance = get_ad_balance(user_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои задания", callback_data="my_tasks")
    builder.button(text="➕ Создать задание", callback_data="new_user_task")
    builder.button(text="💰 Пополнить рекламный баланс", callback_data="topup_ad_balance")
    builder.button(text="💫 Перевод звезды", callback_data="transfer_stars")
    builder.button(text="⬅️ В главное меню", callback_data="back_main")
    markup = builder.adjust(1, 1, 1, 1, 1).as_markup()

    caption = (
        f"<b>✨ Покупка подписчиков ✨</b>\n\n"
        f"💰 <b>Баланс:</b> {regular_balance:.2f} ⭐️\n"
        f"💼 <b>Рекламный баланс:</b> {ad_balance:.2f} ⭐️\n\n"
        f"⚠️ <b>Звезды можно выводить только с обычного баланса</b>"
    )

    try:
        photo = FSInputFile("photos/create_task.jpg")
        await bot.send_photo(user_id, photo, caption=caption, parse_mode='HTML', reply_markup=markup)
    except:
        await bot.send_message(user_id, caption, parse_mode='HTML', reply_markup=markup)


@router.callback_query(F.data == "my_tasks")
async def my_tasks_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    tasks = get_user_tasks(user_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="create_task")
    markup = builder.as_markup()

    if not tasks:
        await call.message.edit_text(
            "<b>📋 У вас пока нет созданных заданий</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    text = "<b>📋 Ваши задания:</b>\n\n"
    for task in tasks:
        task_id, post_text, target_subs, current_subs, total_cost, status, created_at = task
        progress = min(100, (current_subs / target_subs) * 100) if target_subs > 0 else 0
        status_emoji = "🟢" if status == "active" else "🔴"

        text += (
            f"{status_emoji} <b>Задание #{task_id}</b>\n"
            f"📊 Прогресс: {current_subs}/{target_subs} ({progress:.1f}%)\n"
            f"💰 Потрачено: {total_cost:.2f} ⭐️\n"
            f"📅 Создано: {created_at}\n"
            "─────────────\n"
        )

    await call.message.edit_text(text, parse_mode='HTML', reply_markup=markup)


@router.callback_query(F.data == "new_user_task")
async def new_user_task_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(
        call.from_user.id,
        "<b>📝 Создание нового задания</b>\n\n"
        "Пожалуйста, перешлите пост из канала, на который нужно привлечь подписчиков:",
        parse_mode='HTML'
    )
    await state.set_state(UserTaskStates.waiting_for_post)


@router.message(UserTaskStates.waiting_for_post)
async def process_forwarded_post(message: Message, state: FSMContext, bot: Bot):
    if not message.forward_from_chat:
        await message.reply(
            "❌ Пожалуйста, перешлите пост из канала. Обычные сообщения не подходят."
        )
        return

    channel_id = message.forward_from_chat.id
    channel_title = message.forward_from_chat.title
    channel_username = message.forward_from_chat.username
    channel_link = None  # Инициализируем переменную

    # Получаем информацию о канале для верификации и создания инвайт-ссылки
    try:
        chat_info = await bot.get_chat(channel_id)
        channel_title = chat_info.title or channel_title

        # Пытаемся создать инвайт-ссылку (бот должен быть админом с правами)
        invite_link_obj = await bot.create_chat_invite_link(chat_id=channel_id, creates_join_request=False)
        channel_link = invite_link_obj.invite_link

    except Exception as e:
        logging.error(f"Ошибка при создании инвайт-ссылки для канала {channel_id}: {e}")
        # Если создать инвайт-ссылку не удалось, сообщаем об этом.
        # Больше не используем фоллбэк на ссылку с username.
        await message.reply(
            "❌ Не удалось создать инвайт-ссылку на канал. Убедитесь, что бот является администратором канала с правом на создание пригласительных ссылок."
        )
        return

    # Если channel_link не был установлен, значит произошла ошибка
    if not channel_link:
        # Эта ветка кода, по идее, не должна быть достигнута благодаря 'return' выше,
        # но для надёжности оставим её.
        await message.reply("❌ Произошла непредвиденная ошибка при создании ссылки.")
        return

    # Сохраняем информацию о задании
    post_text = message.text or message.caption or "Медиа-пост"
    post_entities = json.dumps([{
        'type': entity.type,
        'offset': entity.offset,
        'length': entity.length
    } for entity in (message.entities or [])]) if message.entities else ""

    await state.update_data(
        post_text=post_text,
        post_entities=post_entities,
        channel_id=channel_id,
        channel_link=channel_link,  # Теперь здесь всегда будет инвайт-ссылка
        channel_title=channel_title
    )

    # Проверяем тип канала
    is_public_channel = bool(channel_username)
    channel_type = "🔓 Публичный" if is_public_channel else "🔒 Приватный"

    await message.reply(
        f"✅ Пост принят!\n\n"
        f"📢 Канал: {channel_title}\n"
        f"🏷️ Тип: {channel_type}\n"
        f"🔗 Ссылка на канал: {channel_link}\n"
        f"📋 ID канала: <code>{channel_id}</code>\n\n"
        f"ℹ️ <b>Важно:</b> Пользователи будут переходить по ссылке на канал для подписки\n\n"
        f"Теперь введите количество подписчиков (минимум 50):",
        parse_mode='HTML'
    )
    await state.set_state(UserTaskStates.waiting_for_subscribers)


@router.message(UserTaskStates.waiting_for_subscribers)
async def process_subscribers_count(message: Message, state: FSMContext, bot: Bot):
    try:
        target_subscribers = int(message.text)
        if target_subscribers < 50:
            await message.reply("❌ Минимальное количество подписчиков: 50")
            return
    except ValueError:
        await message.reply("❌ Пожалуйста, введите числовое значение")
        return

    user_id = message.from_user.id
    cost_per_subscriber = 1.0
    total_cost = target_subscribers * cost_per_subscriber
    ad_balance = get_ad_balance(user_id)

    data = await state.get_data()
    channel_title = data.get('channel_title', 'Неизвестный канал')

    if ad_balance < total_cost:
        builder = InlineKeyboardBuilder()
        builder.button(text="💰 Пополнить баланс", callback_data="topup_ad_balance")
        builder.button(text="❌ Отменить", callback_data="create_task")
        markup = builder.adjust(1, 1).as_markup()

        await message.reply(
            f"❌ <b>Недостаточно средств на рекламном балансе!</b>\n\n"
            f"💼 Ваш рекламный баланс: {ad_balance:.2f} ⭐️\n"
            f"💰 Требуется: {total_cost:.2f} ⭐️\n"
            f"📊 Нехватает: {total_cost - ad_balance:.2f} ⭐️",
            parse_mode='HTML',
            reply_markup=markup
        )
        await state.clear()
        return

    await state.update_data(target_subscribers=target_subscribers, total_cost=total_cost)

    # Создаём задание
    await create_user_task_final(message, state, bot)


async def create_user_task_final(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()

    # Списываем средства с рекламного баланса
    total_cost = data['total_cost']
    if not deduct_ad_balance(user_id, total_cost):
        await message.reply("❌ Ошибка при списании средств. Попробуйте позже.")
        await state.clear()
        return

    # Создаём задание в базе данных со статусом pending
    task_id = create_user_task(
        creator_id=user_id,
        post_text=data['post_text'],
        post_entities=data['post_entities'],
        channel_id=data['channel_id'],
        channel_link=data['channel_link'],
        target_subscribers=data['target_subscribers'],
        total_cost=total_cost,
        status='pending'  # Задание ожидает модерации
    )

    # Уведомляем админов о новом задании
    for admin_id in admins_id:
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Одобрить", callback_data=f"approve_task:{task_id}")
        builder.button(text="❌ Отклонить", callback_data=f"reject_task:{task_id}")
        builder.button(text="👤 Профиль создателя", url=f"tg://user?id={user_id}")
        markup = builder.adjust(2, 1).as_markup()

        try:
            chat_info = await bot.get_chat(data['channel_id'])
            channel_title = chat_info.title
            channel_type = "🔓 Публичный" if chat_info.username else "🔒 Приватный"
        except:
            channel_title = data['channel_title']
            channel_type = "❓ Неизвестно"

        await bot.send_message(
            admin_id,
            f"<b>📋 Новое задание на модерацию</b>\n\n"
            f"👤 Создатель: {message.from_user.full_name} (ID: {user_id})\n"
            f"📢 Канал: {channel_title}\n"
            f"🏷️ Тип канала: {channel_type}\n"
            f"🔗 Ссылка: {data['channel_link']}\n"
            f"👥 Целевые подписчики: {data['target_subscribers']}\n"
            f"💰 Потрачено: {total_cost:.2f} ⭐️\n"
            f"🆔 ID задания: {task_id}\n\n"
            f"📝 Текст поста:\n{data['post_text'][:200]}{'...' if len(data['post_text']) > 200 else ''}",
            parse_mode='HTML',
            reply_markup=markup
        )

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои задания", callback_data="my_tasks")
    builder.button(text="⬅️ В главное меню", callback_data="back_main")
    markup = builder.adjust(1, 1).as_markup()

    await message.reply(
        f"✅ <b>Задание отправлено на модерацию!</b>\n\n"
        f"🆔 ID задания: {task_id}\n"
        f"👥 Целевые подписчики: {data['target_subscribers']}\n"
        f"💰 Потрачено: {total_cost:.2f} ⭐️\n\n"
        f"⏳ <b>Ожидайте одобрения администратором</b>\n"
        f"📌 После одобрения задание станет доступным для выполнения",
        parse_mode='HTML',
        reply_markup=markup
    )

    await state.clear()


@router.callback_query(F.data.startswith("approve_task:"))
async def approve_task_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    try:
        task_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Получаем информацию о задании
    task_info = get_task_by_id(task_id)
    if not task_info:
        await call.answer("❌ Задание не найдено", show_alert=True)
        return

    task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status = task_info

    if status != 'pending':
        await call.answer("❌ Задание уже обработано", show_alert=True)
        return

    # Одобряем задание
    approve_user_task(task_id)

    # Создаём ссылку на задание
    bot_username = (await bot.me()).username
    task_link = f"https://t.me/{bot_username}?start=user_task_{task_id}"
    update_user_task_link(task_id, task_link)

    # Уведомляем создателя
    await bot.send_message(
        creator_id,
        f"✅ <b>Ваше задание одобрено!</b>\n\n"
        f"🆔 ID задания: {task_id}\n"
        f"👥 Целевые подписчики: {target_subscribers}\n\n"
        f"📌 Задание теперь доступно для выполнения пользователями",
        parse_mode='HTML'
    )

    # Обновляем сообщение админа
    await call.message.edit_text(
        f"✅ <b>Задание одобрено</b>\n\n"
        f"🆔 ID задания: {task_id}\n"
        f"👤 Создатель: ID {creator_id}\n"
        f"👨‍💼 Одобрил: {call.from_user.full_name}\n"
        f"📅 Время одобрения: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("reject_task:"))
async def reject_task_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    try:
        task_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Получаем информацию о задании
    task_info = get_task_by_id(task_id)
    if not task_info:
        await call.answer("❌ Задание не найдено", show_alert=True)
        return

    task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status = task_info

    if status != 'pending':
        await call.answer("❌ Задание уже обработано", show_alert=True)
        return

    # Получаем стоимость задания для возврата
    task_cost = get_user_task_cost(task_id)

    # Отклоняем задание
    reject_user_task(task_id)

    # Возвращаем средства на рекламный баланс
    if task_cost:
        update_ad_balance(creator_id, task_cost)

    # Уведомляем создателя
    await bot.send_message(
        creator_id,
        f"❌ <b>Ваше задание отклонено</b>\n\n"
        f"🆔 ID задания: {task_id}\n"
        f"💰 Средства возвращены: {task_cost:.2f} ⭐️\n\n"
        f"📞 Для уточнения причины обратитесь к администратору",
        parse_mode='HTML'
    )

    # Обновляем сообщение админа
    await call.message.edit_text(
        f"❌ <b>Задание отклонено</b>\n\n"
        f"🆔 ID задания: {task_id}\n"
        f"👤 Создатель: ID {creator_id}\n"
        f"💰 Возвращено: {task_cost:.2f} ⭐️\n"
        f"👨‍💼 Отклонил: {call.from_user.full_name}\n"
        f"📅 Время отклонения: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "topup_ad_balance")
async def topup_ad_balance_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(
        call.from_user.id,
        "<b>💰 Пополнение рекламного баланса</b>\n\n"
        "Введите количество звезд для пополнения:",
        parse_mode='HTML'
    )
    await state.set_state(UserTaskStates.waiting_for_stars_amount)


@router.message(UserTaskStates.waiting_for_stars_amount)
async def process_stars_amount(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.reply("❌ Количество должно быть больше 0")
            return
    except ValueError:
        await message.reply("❌ Пожалуйста, введите числовое значение")
        return

    await state.update_data(topup_amount=amount)

    builder = InlineKeyboardBuilder()
    builder.button(text="⭐️ Telegram Stars", callback_data="pay_stars")
    builder.button(text="💳 Рубли и Криптовалюта", callback_data="pay_external")
    builder.button(text="🏦 СБП", callback_data="pay_sbp")
    builder.button(text="❌ Отменить", callback_data="create_task")
    markup = builder.adjust(1, 1, 1, 1).as_markup()

    await message.reply(
        f"<b>💳 Выберите способ пополнения на {amount:.2f} ⭐️:</b>",
        parse_mode='HTML',
        reply_markup=markup
    )
    await state.set_state(UserTaskStates.waiting_for_payment_method)


@router.callback_query(F.data == "pay_external")
async def pay_external_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    amount = data['topup_amount']

    await bot.send_message(
        call.from_user.id,
        f"<b>💳 Оплата Рублями и Криптовалютой</b>\n\n"
        f"💰 Сумма для пополнения: {amount:.2f} ⭐️\n\n"
        f"<b>📋 Инструкция по пополнению:</b>\n"
        f"1. Перейдите в наш магазин звезд — @stars_full_buybot\n"
        f"2. Купите нужное количество звезд\n"
        f"3. Вернитесь в бота и пополните баланс методом «Telegram Stars»\n\n"
        f"👉 @stars_full_buybot",
        parse_mode='HTML'
    )
    await state.clear()


@router.callback_query(F.data == "pay_stars")
async def pay_stars_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    amount = data['topup_amount']
    user_id = call.from_user.id

    # Создаём счет в Telegram Stars
    prices = [LabeledPrice(label="XTR", amount=int(amount))]
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Заплатить ⭐{int(amount)}", pay=True)
    builder.button(text="❌ Отменить", callback_data="create_task")
    markup = builder.adjust(1, 1).as_markup()

    await bot.send_invoice(
        user_id,
        title='Пополнение рекламного баланса',
        description=f'Пополнение рекламного баланса на {amount:.2f} звезд',
        prices=prices,
        provider_token="",
        payload=f"ad_balance_topup_{amount}",
        currency="XTR",
        reply_markup=markup
    )


@router.callback_query(F.data == "pay_crypto")
async def pay_crypto_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    amount = data['topup_amount']
    user_id = call.from_user.id

    # Получаем текущие настройки криптовалюты и курса
    crypto_settings = get_crypto_settings()
    exchange_rate = get_exchange_rate()  # Получаем курс (рубли за звезду)

    # Рассчитываем сумму в USDT
    ruble_amount = amount * exchange_rate  # Сумма в рублях
    usdt_rate = 100  # 1 USDT = 100 рублей (можно вынести в настройки)
    usdt_amount = ruble_amount / usdt_rate

    # Сохраняем информацию о платеже
    await state.update_data(usdt_amount=usdt_amount)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я перевел", callback_data="crypto_transferred")
    builder.button(text="❌ Отменить", callback_data="create_task")
    markup = builder.adjust(1, 1).as_markup()

    await bot.send_message(
        call.from_user.id,
        f"<b>💰 Пополнение через криптовалюту</b>\n\n"
        f"💫 Сумма: {amount:.2f} ⭐️\n"
        f"💸 Стоимость: {ruble_amount:.2f} ₽\n"
        f"💵 К оплате: {usdt_amount:.3f} USDT\n\n"
        f"<b>📋 Реквизиты для перевода:</b>\n"
        f"🏦 Сеть: <code>{crypto_settings['network']}</code>\n"
        f"💳 Адрес: <code>{crypto_settings['address']}</code>\n\n"
        f"⚠️ <b>Важно:</b>\n"
        f"• Переводите точную сумму: <b>{usdt_amount:.3f} USDT</b>\n"
        f"• Используйте только сеть {crypto_settings['network']}\n"
        f"• После перевода нажмите 'Я перевел'\n"
        f"• Обработка может занять до 24 часов",
        parse_mode='HTML',
        reply_markup=markup
    )


@router.callback_query(F.data == "crypto_transferred")
async def crypto_transferred_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    amount = data['topup_amount']
    usdt_amount = data['usdt_amount']
    user_id = call.from_user.id

    # Добавляем запрос на криптоплатеж с суммой в USDT
    payment_id = add_crypto_payment(user_id, amount, "crypto", usdt_amount)

    # Получаем текущие настройки криптовалюты
    crypto_settings = get_crypto_settings()

    # Уведомляем админов
    for admin_id in admins_id:
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Подтвердить", callback_data=f"confirm_crypto:{payment_id}")
        builder.button(text="❌ Отклонить", callback_data=f"reject_crypto:{payment_id}")
        markup = builder.adjust(2).as_markup()

        await bot.send_message(
            admin_id,
            f"<b>💰 Новый запрос на пополнение через криптовалюту</b>\n\n"
            f"👤 Пользователь: {call.from_user.full_name} (ID: {user_id})\n"
            f"💰 Сумма: {amount:.2f} ⭐️\n"
            f"💵 Сумма в USDT: {usdt_amount:.3f} USDT\n"
            f"🏦 Сеть: {crypto_settings['network']}\n"
            f"💳 Адрес: <code>{crypto_settings['address']}</code>\n"
            f"🆔 ID платежа: {payment_id}",
            parse_mode='HTML',
            reply_markup=markup
        )

    await call.message.edit_text(
        f"✅ <b>Заявка отправлена!</b>\n\n"
        f"💰 Сумма: {amount:.2f} ⭐️\n"
        f"💵 Переведено: {usdt_amount:.3f} USDT\n"
        f"⏳ Ожидайте подтверждения от администратора",
        parse_mode='HTML'
    )
    await state.clear()


@router.callback_query(F.data == "pay_sbp")
async def pay_sbp_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    amount = data['topup_amount']

    await bot.send_message(
        call.from_user.id,
        f"<b>🏦 Оплата через СБП</b>\n\n"
        f"💰 Сумма для пополнения: {amount:.2f} ⭐️\n\n"
        f"<b>📋 Инструкция по пополнению:</b>\n"
        f"1. Перейдите в наш магазин звезд — @stars_full_buybot\n"
        f"2. Купите нужное количество звезд через СБП\n"
        f"3. Вернитесь в бота и пополните баланс методом «Telegram Stars»\n\n"
        f"👉 @stars_full_buybot",
        parse_mode='HTML'
    )
    await state.clear()


@router.callback_query(F.data.startswith("confirm_crypto:"))
async def confirm_crypto_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    try:
        payment_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Получаем информацию о платеже
    payment_info = get_crypto_payment_by_id(payment_id)

    if not payment_info:
        await call.answer("❌ Платеж не найден", show_alert=True)
        return

    payment_id, user_id, amount, payment_method, usdt_amount, status, created_at = payment_info

    # Подтверждаем платеж
    confirm_crypto_payment(payment_id, call.from_user.id)

    # Пополняем рекламный баланс пользователя
    update_ad_balance(user_id, amount)

    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        f"✅ <b>Пополнение подтверждено!</b>\n\n"
        f"💰 На ваш рекламный баланс зачислено: {amount:.2f} ⭐️\n"
        f"💵 Получено: {usdt_amount:.3f} USDT",
        parse_mode='HTML'
    )

    # Обновляем сообщение админа
    await call.message.edit_text(
        f"✅ <b>Платеж подтвержден</b>\n\n"
        f"👤 Пользователь: ID {user_id}\n"
        f"💰 Сумма: {amount:.2f} ⭐️\n"
        f"💵 USDT: {usdt_amount:.3f}\n"
        f"👨‍💼 Подтвердил: {call.from_user.full_name}",
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("reject_crypto:"))
async def reject_crypto_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    try:
        payment_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Получаем информацию о платеже
    payment_info = get_crypto_payment_by_id(payment_id)

    if not payment_info:
        await call.answer("❌ Платеж не найден", show_alert=True)
        return

    payment_id, user_id, amount, payment_method, usdt_amount, status, created_at = payment_info

    # Отклоняем платеж
    reject_crypto_payment(payment_id, call.from_user.id)

    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        f"❌ <b>Платеж отклонен</b>\n\n"
        f"💰 Сумма: {amount:.2f} ⭐️\n"
        f"💵 USDT: {usdt_amount:.3f}\n"
        f"📞 Обратитесь к администратору для уточнения причины",
        parse_mode='HTML'
    )

    # Обновляем сообщение админа
    await call.message.edit_text(
        f"❌ <b>Платеж отклонен</b>\n\n"
        f"👤 Пользователь: ID {user_id}\n"
        f"💰 Сумма: {amount:.2f} ⭐️\n"
        f"💵 USDT: {usdt_amount:.3f}\n"
        f"👨‍💼 Отклонил: {call.from_user.full_name}",
        parse_mode='HTML'
    )


@router.callback_query(F.data == "transfer_stars")
async def transfer_stars_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = call.from_user.id
    regular_balance = get_balance_user(user_id)

    if regular_balance <= 0:
        await call.answer("❌ У вас недостаточно звезд на обычном балансе", show_alert=True)
        return

    await bot.send_message(
        call.from_user.id,
        f"<b>💫 Перевод звезд</b>\n\n"
        f"💰 Ваш баланс: {regular_balance:.2f} ⭐️\n\n"
        f"Введите количество звезд для перевода на рекламный баланс:",
        parse_mode='HTML'
    )
    await state.set_state(UserTaskStates.transfer_amount)


@router.message(UserTaskStates.transfer_amount)
async def process_transfer_amount(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.reply("❌ Количество должно быть больше 0")
            return
    except ValueError:
        await message.reply("❌ Пожалуйста, введите числовое значение")
        return

    user_id = message.from_user.id
    regular_balance = get_balance_user(user_id)

    if amount > regular_balance:
        await message.reply(f"❌ У вас недостаточно звезд. Доступно: {regular_balance:.2f} ⭐️")
        return

    # Выполняем перевод
    if transfer_to_ad_balance(user_id, amount):
        new_regular_balance = get_balance_user(user_id)
        new_ad_balance = get_ad_balance(user_id)

        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="create_task")
        markup = builder.as_markup()

        await message.reply(
            f"✅ <b>Перевод выполнен успешно!</b>\n\n"
            f"💰 Обычный баланс: {new_regular_balance:.2f} ⭐️\n"
            f"💼 Рекламный баланс: {new_ad_balance:.2f} ⭐️\n"
            f"📊 Переведено: {amount:.2f} ⭐️",
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        await message.reply("❌ Ошибка при переводе. Попробуйте позже.")

    await state.clear()


@router.message(F.content_type == 'successful_payment')
async def successful_payment_handler(message: Message, bot: Bot):
    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
        payment_info = message.successful_payment
        user_id = message.from_user.id
        username = message.from_user.username if message.from_user.username else "Нету"
        amount = payment_info.total_amount
        currency = payment_info.currency
        payload = payment_info.invoice_payload

        if currency == "XTR":
            currency = "⭐️"

        # Проверяем тип платежа
        if payload.startswith("ad_balance_topup_"):
            # Пополнение рекламного баланса
            topup_amount = float(payload.split("_")[-1])
            update_ad_balance(user_id, topup_amount)

            for admin in admins_id:
                await bot.send_message(
                    admin,
                    f"<b>💼 Пополнение рекламного баланса</b>\n\n"
                    f"🆔 Айди: {user_id}\n"
                    f"🚹 Username: {username if username else None}\n"
                    f"💰 Получено: {amount} {currency}",
                    parse_mode='HTML'
                )

            await bot.send_message(
                user_id,
                f"✅ <b>Пополнение выполнено!</b>\n\n"
                f"💼 На ваш рекламный баланс зачислено: {topup_amount:.2f} ⭐️",
                parse_mode='HTML'
            )

        elif payload == "channel_support":
            # Обычный буст (старая логика)
            current_time = datetime.now()
            delta = timedelta(days=15)
            future_time = current_time + delta
            future_timestamp = future_time.timestamp()

            add_or_update_user_boost(user_id, future_timestamp)
            time_until_normal = datetime.fromtimestamp(future_timestamp)

            for admin in admins_id:
                await bot.send_message(
                    admin,
                    f"<b>❤️ Получен платёж за буст.\n\nℹ️ Информация о полученном платеже:\n🆔 Айди: {user_id}\n🚹 Username: {username if username else None}\n💰 Получено: {amount} {currency}</b>",
                    parse_mode='HTML'
                )

            await bot.send_message(
                user_id,
                f"<b>❤️ Получен платёж.\n\n✨ Буст был успешно активирован на 15 дней.</b>\n\n<i>У вас осталось времени буста до: {time_until_normal}</i>",
                parse_mode='HTML'
            )

    except Exception as e:
        logging.error(f"Ошибка при обработке успешного платежа: {e}")
        await bot.send_message(user_id,
                               "<b>Произошла ошибка при обработке платежа. Пожалуйста, свяжитесь с администратором.</b>",
                               parse_mode='HTML')


# ИЗМЕНЕНИЕ 2: Обновленная функция получения следующего пользовательского задания с приоритетом
async def get_next_user_task(user_id: int):
    """Получает следующее доступное пользовательское задание с приоритетом по количеству подписчиков"""
    active_tasks = get_active_user_tasks()  # Только одобренные задания

    # Сортируем задания по количеству целевых подписчиков в убывающем порядке (больше подписчиков = выше приоритет)
    sorted_tasks = sorted(active_tasks, key=lambda task: task[6], reverse=True)  # task[6] = target_subscribers

    for task in sorted_tasks:
        task_id = task[0]
        # Проверяем, не выполнял ли пользователь уже это задание
        if not check_task_subscription(task_id, user_id) and not is_user_task_skipped(task_id, user_id):
            return task

    return None


async def handle_user_task_subscription(message: Message, bot: Bot, task_id: int):
    """Обрабатывает подписку на пользовательское задание через ссылку"""
    user_id = message.from_user.id

    # Проверяем, зарегистрирован ли пользователь
    if not user_exists(user_id):
        await message.reply("❌ Сначала запустите бота командой /start")
        return

    # Получаем информацию о задании
    task_info = get_task_by_id(task_id)
    if not task_info:
        await message.reply("❌ Задание не найдено или неактивно")
        return

    task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status = task_info

    if status != 'active':
        await message.reply("❌ Задание больше не активно")
        return

    if current_subscribers >= target_subscribers * 1.1:
        await message.reply("❌ Задание уже выполнено")
        return

    # Проверяем, не выполнял ли пользователь уже это задание
    if check_task_subscription(task_id, user_id):
        await message.reply("❌ Вы уже выполняли это задание")
        return

    # Показываем задание с единой ссылкой на канал
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подписаться на канал", url=channel_link)
    builder.button(text="🔎 Проверить подписку", callback_data=f"check_user_task:{task_id}")
    builder.button(text="⬅️ В главное меню", callback_data="back_main")
    builder.button(text="➡️ Пропустить", callback_data=f"skip_user_task:{task_id}")

    markup = builder.adjust(1, 1, 2).as_markup()

    reward = task_grant[0]
    await bot.send_message(
        user_id,
        f"<b>✨ Новое задание! ✨</b>\n\n"
        f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
        f"Награда: {reward} ⭐️\n\n"
        f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней \"Проверить подписку\" 👇",
        parse_mode='HTML',
        reply_markup=markup
    )


# Изменения в функции handle_task_callback
@router.callback_query(F.data.startswith('task_check'))
async def handle_task_callback(call: CallbackQuery, bot: Bot):
    try:
        data_parts = call.data.split(":")
        if len(data_parts) < 4:
            await bot.answer_callback_query(call.id, "❌ Неверный формат данных", show_alert=True)
            return

        _, reward, task_id_str, chat_id = data_parts
        task_id = int(task_id_str)
        user_id = call.from_user.id
        reward = float(reward)
    except (ValueError, IndexError):
        await bot.answer_callback_query(call.id, "❌ Ошибка при обработке данных задания", show_alert=True)
        return

    completed_task = get_completed_tasks_for_user(user_id)
    if task_id in completed_task:
        await bot.answer_callback_query(call.id, "❌ Задание уже выполнено.", show_alert=True)
        return

    if chat_id != "None":
        try:
            chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                await bot.answer_callback_query(call.id, "❌ Вы не подписались на канал!")
                return
        except Exception as e:
            print(f"error in check subs in tasks: {e}")

    await bot.answer_callback_query(call.id, f"✅ Задание выполнено. Начислено: {reward}⭐️")
    increment_current_completed(task_id)
    complete_task_for_user(user_id, task_id)
    add_completed_task(user_id)
    increment_stars(user_id, reward)

    # Добавляем отслеживание подписки на 3 дня для обычных заданий
    if chat_id != "None":
        add_task_subscription_tracking(
            user_id=user_id,
            task_id=task_id,
            task_type='regular_task',
            channel_id=int(chat_id),
            reward_amount=reward
        )

    await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)

    # ИЗМЕНЕНИЕ: Вместо отправки в главное меню, показываем следующее задание
    await show_next_task(call, bot)


# Изменения в функции flyer_check_callback
@router.callback_query(F.data.startswith("flyer_check"))
async def flyer_check_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return

    try:
        signature = call.data.split(":")[1]
    except IndexError:
        await bot.answer_callback_query(call.id, "❌ Ошибка при обработке данных", show_alert=True)
        return

    task_hash = hash_flyer_task(signature=signature, user_id=user_id)

    if is_flyer_task_completed(task_hash):
        await bot.answer_callback_query(call.id, "🎯 Задание уже выполнено!", show_alert=True)

    resultat = await check_flyer_task(FLYER_KEY, call.from_user.id, signature=signature)

    if resultat == "complete" or resultat == "waiting":
        await bot.answer_callback_query(call.id, "✅ Спасибо за подписку!", show_alert=True)
        increment_stars(call.from_user.id, task_grant[0])
        add_flyer_task(task_hash)
        add_completed_task(call.from_user.id)

        # ИЗМЕНЕНИЕ: Показываем следующее задание вместо главного меню
        await show_next_task(call, bot)
        return
    else:
        await bot.answer_callback_query(call.id, "❌ Задание не выполнено!", show_alert=True)


@router.callback_query(F.data.startswith("check_user_task:"))
async def check_user_task_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id

    try:
        task_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Получаем информацию о задании
    task_info = get_task_by_id(task_id)
    if not task_info:
        await call.answer("❌ Задание не найдено", show_alert=True)
        return

    task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status = task_info

    # Проверяем подписку на канал по его ID
    try:
        chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if chat_member.status not in ['member', 'administrator', 'creator']:
            await call.answer("❌ Вы не подписались на канал!", show_alert=True)
            return
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки на канал {channel_id}: {e}")
        await call.answer("❌ Ошибка при проверке подписки", show_alert=True)
        return

    # Выдаем награду
    reward = task_grant[0]
    increment_stars(user_id, reward)
    add_task_subscription(task_id, user_id)
    mark_task_subscription_rewarded(task_id, user_id)
    update_task_subscribers(task_id)
    add_completed_task(user_id)

    # Добавляем отслеживание подписки на 3 дня
    add_task_subscription_tracking(
        user_id=user_id,
        task_id=task_id,
        task_type='user_task',
        channel_id=channel_id,
        reward_amount=reward
    )

    await call.answer(f"✅ Задание выполнено! Получено: {reward} ⭐️", show_alert=True)

    # Удаляем текущее сообщение с заданием перед показом следующего
    try:
        await bot.delete_message(user_id, call.message.message_id)
    except TelegramBadRequest as e:
        if "message to delete not found" not in str(e).lower():
            logging.error(f"Ошибка при удалении сообщения с пользовательским заданием: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при удалении сообщения с пользовательским заданием: {e}")

    # Показываем следующее задание
    await show_next_task(call, bot)


# 1. В функции tasks_callback убираем проверку SubGram заданий
@router.callback_query(F.data == "tasks")
async def tasks_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return

    # Проверка подписки на SubGram (если не админ)
    if user_id not in admins_id and button_subgram[0]:
        response = await request_op(
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

    # Удаляем предыдущие задания
    await delete_task_message(bot, user_id)
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении главного сообщения: {e}")

    # УБИРАЕМ ЭТУ ЧАСТЬ - проверка SubGram заданий
    # try:
    #     if button_subgram[0]:
    #         tasks = await request_task(user_id, user_id, first_name, language_code, bot)
    #         if tasks != 'ok':
    #             await show_subgram_task_unified(user_id, first_name, language_code, bot)
    #             return
    # except Exception as e:
    #     logging.error(f"Ошибка при проверке SubGram: {e}")

    # Проверка заданий от Flyer (остается без изменений)
    try:
        tasks_list = await get_flyer_tasks(FLYER_KEY, user_id, limit=10)
        selected_task = None

        for task in tasks_list:
            link = task.get('link')
            signature = task.get('signature')
            if not link or not signature:
                continue

            task_hash = hash_flyer_task(signature, user_id)
            if not is_flyer_task_completed(task_hash) and not is_flyer_task_skipped(task_hash, user_id):
                selected_task = task
                break

        if selected_task:
            link = selected_task.get('link')
            signature = selected_task.get('signature')

            task_text = (
                f'<b>✨ Новое задание! ✨\n\n'
                f'• Подпишитесь на каналы, указанные ниже.\n\n'
                f'Награда: {task_grant[0]} ⭐️</b>\n\n'
                f'📌 Чтобы получить награду полностью, подпишитесь и не отписывайтесь от канала/группы в течение 3-х дней. '
                f'Нажмите "Проверить подписку", чтобы подтвердить!'
            )

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Подписаться на канал", url=link)
            builder.button(text="🔎 Проверить подписку", callback_data=f'flyer_check:{signature}')
            builder.button(text="⬅️ В главное меню", callback_data="back_main")
            builder.button(text="➡️ Пропустить", callback_data=f'skip_flyer_task:{signature}')
            markup = builder.adjust(1, 1, 2).as_markup()

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(call.from_user.id, photo=photo, caption=task_text, parse_mode='HTML',
                                           reply_markup=markup)
            except:
                msg = await bot.send_message(call.from_user.id, task_text, parse_mode='HTML', reply_markup=markup)

            user_task_messages[user_id] = msg.message_id
            return

    except Exception as e:
        logging.error(f"Ошибка при получении заданий от Flyer: {e}")

    # Пользовательские задания (остается без изменений)
    try:
        user_task = await get_next_user_task(user_id)
        if user_task:
            task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = user_task

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Подписаться на канал", url=channel_link)
            builder.button(text="🔎 Проверить подписку", callback_data=f"check_user_task:{task_id}")
            builder.button(text="⬅️ В главное меню", callback_data="back_main")
            builder.button(text="➡️ Пропустить", callback_data=f"skip_user_task:{task_id}")
            markup = builder.adjust(1, 1, 2).as_markup()

            reward = task_grant[0]
            text = (
                f"<b>✨ Новое задание! ✨</b>\n\n"
                f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                f"Награда: {reward} ⭐️\n\n"
                f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней."
            )

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(call.from_user.id, photo=photo, caption=text, parse_mode='HTML',
                                           reply_markup=markup)
            except:
                msg = await bot.send_message(call.from_user.id, text, parse_mode='HTML', reply_markup=markup)

            user_task_messages[user_id] = msg.message_id
            return

    except Exception as e:
        logging.error(f"Ошибка при получении пользовательского задания: {e}")

    # Если нет заданий
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    await bot.send_message(
        call.from_user.id,
        "<b>🎯 На данный момент нет доступных заданий!\n\nВозвращайся позже!</b>",
        parse_mode='HTML',
        reply_markup=markup_back
    )


# 2. В функции send_tasks_menu также убираем проверку SubGram заданий
async def send_tasks_menu(user_id: int, bot: Bot, first_name: str, language_code: str):
    """
    Отправляет меню с заданиями пользователю.
    """
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    try:
        # УБИРАЕМ ЭТУ ЧАСТЬ - проверка SubGram заданий
        # tasks = await request_task(user_id, user_id, first_name, language_code, bot)
        # if tasks == 'ok':
        #     tasks_list = await get_flyer_tasks(FLYER_KEY, user_id, limit=10)
        #     selected_task = None

        # Сразу проверяем задания от Flyer
        tasks_list = await get_flyer_tasks(FLYER_KEY, user_id, limit=10)
        selected_task = None

        if tasks_list:
            for task in tasks_list:
                link = task.get('link')
                signature = task.get('signature')
                if not link or not signature:
                    continue

                task_hash = hash_flyer_task(signature, user_id)
                if not is_flyer_task_completed(task_hash) and not is_flyer_task_skipped(task_hash, user_id):
                    selected_task = task
                    break

        if selected_task:
            # Показываем задание от Flyer
            link = selected_task.get('link')
            signature = selected_task.get('signature')
            task_text = (
                f'<b>✨ Следующее задание! ✨\n\n'
                f'• Подпишитесь на каналы, указанные ниже.\n\n'
                f'Награда: {task_grant[0]} ⭐️</b>\n\n'
                f'📌 Чтобы получить награду полностью, подпишитесь и не отписывайтесь от канала/группы в течение 3-х дней. '
                f'Нажмите "Проверить подписку", чтобы подтвердить!'
            )

            markup_flyer = InlineKeyboardBuilder()
            markup_flyer.button(text="✅ Подписаться на канал", url=link)
            markup_flyer.button(text="🔎 Проверить подписку", callback_data=f'flyer_check:{signature}')
            markup_flyer.button(text="⬅️ В главное меню", callback_data="back_main")
            markup_flyer.button(text="➡️ Пропустить", callback_data=f'skip_flyer_task:{signature}')
            markup_flyer = markup_flyer.adjust(1, 1, 2).as_markup()

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(
                    user_id,
                    photo=photo,
                    caption=task_text,
                    parse_mode='HTML',
                    reply_markup=markup_flyer
                )
            except:
                msg = await bot.send_message(
                    user_id,
                    task_text,
                    parse_mode='HTML',
                    reply_markup=markup_flyer
                )

            # Сохраняем ID нового сообщения
            user_task_messages[user_id] = msg.message_id
            return

        # Пользовательские задания (остается без изменений)
        user_task = await get_next_user_task(user_id)
        if user_task:
            task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = user_task

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Подписаться на канал", url=channel_link)
            builder.button(text="🔎 Проверить подписку", callback_data=f"check_user_task:{task_id}")
            builder.button(text="⬅️ В главное меню", callback_data="back_main")
            builder.button(text="➡️ Пропустить", callback_data=f"skip_user_task:{task_id}")
            markup = builder.adjust(1, 1, 2).as_markup()

            reward = task_grant[0]

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(
                    user_id,
                    photo=photo,
                    caption=f"<b>✨ Следующее задание! ✨</b>\n\n"
                            f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                            f"Награда: {reward} ⭐️\n\n"
                            f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней. Нажмите «Проверить подписку» 👇",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except:
                msg = await bot.send_message(
                    user_id,
                    f"<b>✨ Следующее задание! ✨</b>\n\n"
                    f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                    f"Награда: {reward} ⭐️\n\n"
                    f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней. Нажмите «Проверить подписку» 👇",
                    parse_mode='HTML',
                    reply_markup=markup
                )

            # Сохраняем ID нового сообщения
            user_task_messages[user_id] = msg.message_id
            return

        # Нет заданий — показываем финальное сообщение
        await bot.send_message(
            user_id,
            "<b>🎉 Отлично! Вы выполнили все доступные задания!\n\n"
            "🎯 Возвращайтесь позже за новыми заданиями!</b>",
            parse_mode='HTML',
            reply_markup=markup_back
        )

    except Exception as e:
        logging.error(f"Ошибка при показе следующего задания: {e}")
        await bot.send_message(
            user_id,
            "<b>⚠️ Ошибка при получении следующего задания.</b>",
            parse_mode='HTML',
            reply_markup=markup_back
        )


# 3. В функции show_next_task убираем проверку SubGram заданий
async def show_next_task(call: CallbackQuery, bot: Bot):
    """
    Показывает следующее доступное задание или главное меню, если заданий нет.
    Также удаляет предыдущее сообщение с заданием.
    """
    user_id = call.from_user.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code

    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    # Удаление предыдущего сообщения с заданием
    await delete_task_message(bot, user_id)

    try:
        # Сразу проверяем задания от Flyer
        tasks_list = await get_flyer_tasks(FLYER_KEY, user_id, limit=10)
        selected_task = None

        if tasks_list:
            for task in tasks_list:
                link = task.get('link')
                signature = task.get('signature')
                if not link or not signature:
                    continue

                task_hash = hash_flyer_task(signature, user_id)
                if not is_flyer_task_completed(task_hash) and not is_flyer_task_skipped(task_hash, user_id):
                    selected_task = task
                    break

        if selected_task:
            # Показываем задание от Flyer
            link = selected_task.get('link')
            signature = selected_task.get('signature')
            task_text = (
                f'<b>✨ Следующее задание! ✨\n\n'
                f'• Подпишитесь на каналы, указанные ниже.\n\n'
                f'Награда: {task_grant[0]} ⭐️</b>\n\n'
                f'📌 Чтобы получить награду полностью, подпишитесь и не отписывайтесь от канала/группы в течение 3-х дней. '
                f'Нажмите "Проверить подписку", чтобы подтвердить!'
            )

            markup_flyer = InlineKeyboardBuilder()
            markup_flyer.button(text="✅ Подписаться на канал", url=link)
            markup_flyer.button(text="🔎 Проверить подписку", callback_data=f'flyer_check:{signature}')
            markup_flyer.button(text="⬅️ В главное меню", callback_data="back_main")
            markup_flyer.button(text="➡️ Пропустить", callback_data=f'skip_flyer_task:{signature}')
            markup_flyer = markup_flyer.adjust(1, 1, 2).as_markup()

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(
                    user_id,
                    photo=photo,
                    caption=task_text,
                    parse_mode='HTML',
                    reply_markup=markup_flyer
                )
            except:
                msg = await bot.send_message(
                    user_id,
                    task_text,
                    parse_mode='HTML',
                    reply_markup=markup_flyer
                )

            # Сохраняем ID нового сообщения
            user_task_messages[user_id] = msg.message_id
            return

        # Пользовательские задания (остается без изменений)
        user_task = await get_next_user_task(user_id)
        if user_task:
            task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = user_task

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Подписаться на канал", url=channel_link)
            builder.button(text="🔎 Проверить подписку", callback_data=f"check_user_task:{task_id}")
            builder.button(text="⬅️ В главное меню", callback_data="back_main")
            builder.button(text="➡️ Пропустить", callback_data=f"skip_user_task:{task_id}")
            markup = builder.adjust(1, 1, 2).as_markup()

            reward = task_grant[0]

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(
                    user_id,
                    photo=photo,
                    caption=f"<b>✨ Следующее задание! ✨</b>\n\n"
                            f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                            f"Награда: {reward} ⭐️\n\n"
                            f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней. Нажмите «Проверить подписку» 👇",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except:
                msg = await bot.send_message(
                    user_id,
                    f"<b>✨ Следующее задание! ✨</b>\n\n"
                    f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                    f"Награда: {reward} ⭐️\n\n"
                    f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней. Нажмите «Проверить подписку» 👇",
                    parse_mode='HTML',
                    reply_markup=markup
                )

            # Сохраняем ID нового сообщения
            user_task_messages[user_id] = msg.message_id
            return

        # Нет заданий — показываем финальное сообщение
        await bot.send_message(
            user_id,
            "<b>🎉 Отлично! Вы выполнили все доступные задания!\n\n"
            "🎯 Возвращайтесь позже за новыми заданиями!</b>",
            parse_mode='HTML',
            reply_markup=markup_back
        )

    except Exception as e:
        logging.error(f"Ошибка при показе следующего задания: {e}")
        await bot.send_message(
            user_id,
            "<b>⚠️ Ошибка при получении следующего задания.</b>",
            parse_mode='HTML',
            reply_markup=markup_back
        )


# Временное хранилище ID сообщений с заданиями (user_id: message_id)
user_task_messages = {}


async def delete_task_message(bot: Bot, user_id: int):
    """Безопасно удаляет предыдущее сообщение с заданием для пользователя"""
    if user_id in user_task_messages:
        try:
            await bot.delete_message(chat_id=user_id, message_id=user_task_messages[user_id])
        except TelegramBadRequest as e:
            # Игнорируем ошибки "message to delete not found" и подобные
            if "message to delete not found" in str(e).lower() or "message can't be deleted" in str(e).lower():
                logging.debug(f"Сообщение уже удалено или недоступно для пользователя {user_id}")
            else:
                logging.error(f"Ошибка TelegramBadRequest при удалении сообщения для пользователя {user_id}: {e}")
        except Exception as e:
            logging.error(f"Неожиданная ошибка при удалении сообщения для пользователя {user_id}: {e}")
        finally:
            # Всегда удаляем из словаря, чтобы не пытаться удалить снова
            del user_task_messages[user_id]


@router.callback_query(F.data.startswith("check_user_task:"))
async def check_user_task_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id

    try:
        task_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Получаем информацию о задании
    task_info = get_task_by_id(task_id)
    if not task_info:
        await call.answer("❌ Задание не найдено", show_alert=True)
        return

    task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status = task_info

    # Проверяем подписку на канал по его ID
    try:
        chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if chat_member.status not in ['member', 'administrator', 'creator']:
            await call.answer("❌ Вы не подписались на канал!", show_alert=True)
            return
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки на канал {channel_id}: {e}")
        await call.answer("❌ Ошибка при проверке подписки", show_alert=True)
        return

    # Выдаем награду
    reward = task_grant[0]
    increment_stars(user_id, reward)
    add_task_subscription(task_id, user_id)
    mark_task_subscription_rewarded(task_id, user_id)
    update_task_subscribers(task_id)
    add_completed_task(user_id)

    # Добавляем отслеживание подписки на 3 дня
    add_task_subscription_tracking(
        user_id=user_id,
        task_id=task_id,
        task_type='user_task',
        channel_id=channel_id,
        reward_amount=reward
    )

    await call.answer(f"✅ Задание выполнено! Получено: {reward} ⭐️", show_alert=True)

    await bot.delete_message(user_id, call.message.message_id)

    # ИЗМЕНЕНИЕ: Показываем следующее задание вместо главного меню
    await show_next_task(call, bot)


@router.callback_query(F.data.startswith("skip_user_task:"))
async def skip_user_task_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id

    try:
        task_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Добавляем пользователя в список пропустивших это задание
    add_skipped_user_task(task_id, user_id)

    await bot.answer_callback_query(call.id, "Задание пропущено. Ищем следующее...", show_alert=False)

    # Удаляем текущее сообщение с заданием перед показом следующего
    try:
        await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
    except TelegramBadRequest as e:
        if "message to delete not found" not in str(e).lower():
            logging.error(f"Ошибка при удалении пропущенного пользовательского задания: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при удалении пропущенного пользовательского задания: {e}")

    # Показываем следующее задание
    await show_next_task(call, bot)


@router.callback_query(F.data == "info_promo_codes")
async def info_promo_codes_callback(call: CallbackQuery, bot: Bot):
    promocodes = get_all_promocodes()

    text = "<b>🎟️ Текущие промокоды:</b>\n\n"

    for promo in promocodes:
        status = "🟢 Активен" if promo['is_active'] else "🔴 Неактивен"
        text += (f"<b>ID:</b> {promo['id']}\n"
                 f"<b>Код:</b> {promo['code']}\n"
                 f"<b>Звёзды:</b> {promo['stars']}\n"
                 f"<b>Использовано:</b> {promo['current_uses']} из {promo['max_uses']}\n"
                 f"<b>Статус:</b> {status}\n\n")

    if not promocodes:
        text += "<b>Пусто</b>\n"

    await bot.send_message(call.message.chat.id, text, parse_mode='HTML')


@router.callback_query(F.data == 'dump')
async def dump_callback(call: CallbackQuery, bot: Bot):
    try:
        if call.message.chat.id in admins_id:
            user_ids = get_users_ids()

            if not user_ids:
                await bot.send_message(call.from_user.id, "❌ База данных пользователей пуста")
                return

            text = '\n'.join(str(user_id[0]) for user_id in user_ids)
            document = BufferedInputFile(
                text.encode('utf-8'),
                filename='dumped.txt'
            )
            await bot.send_document(
                chat_id=call.from_user.id,
                document=document,
                caption="📥 Дамп базы (ID)"
            )

    except Exception as e:
        logging.error(f"Dump error: {e}")
        await bot.send_message(call.from_user.id, f"⚠️ Ошибка при создании дампа: {str(e)}")


@router.callback_query(F.data == "utm")
async def utm_main_callback(call: CallbackQuery, bot: Bot):
    if call.message.chat.id in admins_id:
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        builder_utm = InlineKeyboardBuilder()
        builder_utm.button(text='🌐 Добавить ссылку', callback_data='add_utm')
        builder_utm.button(text='📄 Список ссылок', callback_data='list_utm')
        builder_utm.button(text="⬅️ Назад", callback_data="adminpanelka")
        markup_utm = builder_utm.adjust(2, 1).as_markup()
        await bot.send_message(
            call.from_user.id,
            "<b>🪅 Вы вошли в UTM-панель</b>",
            parse_mode='HTML',
            reply_markup=markup_utm
        )


@router.callback_query(F.data.startswith('utm_'))
async def utm_detail_callback(call: CallbackQuery, bot: Bot):
    if call.message.chat.id in admins_id:
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        parts = call.data.split('_')
        if len(parts) < 3:
            await bot.answer_callback_query(call.id, "❌ Неверный формат данных.")
            return

        url1 = parts[1]
        url2 = parts[2]
        if '=' not in url2:
            await bot.answer_callback_query(call.id, "❌ Неверный формат данных (отсутствует '=').")
            return

        url_title_parts = url2.split('=', 1)
        url_title = url_title_parts[1] if len(url_title_parts) > 1 else url_title_parts[0]

        url = f"{url1}_{url2}"
        count_users = users_utm_count(url)
        count_op_users = users_utm_count_op(url)

        utm_link_use = InlineKeyboardBuilder()
        utm_link_use.button(text="❌ Удалить ссылку", callback_data=f"deleter_{url}")
        utm_link_use.button(text="⬅️ Назад", callback_data="list_utm")
        markup_utm_use = utm_link_use.adjust(1, 1).as_markup()

        await bot.send_message(
            call.from_user.id,
            (
                f"<b>🍀 Вы выбрали ссылку <code>#{url_title}</code></b>\n\n"
                f"<blockquote>👤 Все пользователи: {count_users}\n"
                f"👤 Прошли ОП: {count_op_users}</blockquote>\n\n"
                "<i>Счетчик только уникальных пользователей!</i>"
            ),
            parse_mode='HTML',
            reply_markup=markup_utm_use
        )


@router.callback_query(F.data.startswith('deleter_'))
async def utm_delete_callback(call: CallbackQuery, bot: Bot):
    if call.message.chat.id in admins_id:
        parts = call.data.split('_')
        if len(parts) < 2:
            await bot.answer_callback_query(call.id, "❌ Неверный формат данных.")
            return

        url = parts[1]

        try:
            delete_utm(url)
            # await bot.delete_message(call.message.chat.id, call.message.message_id)
            await bot.send_message(
                call.from_user.id,
                f"🌐 Ссылка <code>#{url}</code> была удалена",
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Ошибка при удалении UTM-ссылки: {e}")
            await bot.send_message(call.from_user.id, "❌ Ошибка при удалении UTM-ссылки", parse_mode='HTML')


@router.callback_query(F.data == "delete_utm")
async def delete_utm_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    if call.message.chat.id in admins_id:  # исправлена опечатка здесь
        await state.set_state(AddUtmState.waiting_for_delete)
        await bot.send_message(call.from_user.id, "🌐 Введите название UTM-ссылки:", parse_mode='HTML')


@router.callback_query(F.data == "add_utm")
async def add_utm_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    if call.from_user.id in admins_id:
        await state.set_state(AddUtmState.waiting_for_url)
        await bot.send_message(call.from_user.id, "🌐 Введите название для UTM-ссылки:", parse_mode='HTML')


@router.message(AddUtmState.waiting_for_delete)
async def process_delete_utm(message: Message, state: FSMContext, bot: Bot):
    url_name = message.text
    url = f"https://t.me/{(await bot.me()).username}?start={url_name}"
    try:
        delete_utm(url)
        await bot.send_message(
            message.from_user.id,
            f"✅ UTM-ссылка успешно удалена.\n\n<blockquote>👉 Ссылка: <code>{url}</code></blockquote>",
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка при удалении UTM-ссылки: {e}")
        await bot.send_message(message.from_user.id, "❌ Ошибка при удалении UTM-ссылки", parse_mode='HTML')
    await state.clear()


@router.message(AddUtmState.waiting_for_url)
async def process_add_utm(message: Message, state: FSMContext, bot: Bot):
    url_name = message.text
    url = f"https://t.me/{(await bot.me()).username}?start={url_name}"
    try:
        create_utm(url)
        await bot.send_message(
            message.from_user.id,
            f"✅ UTM-ссылка успешно добавлена.\n\n<blockquote>👉 Ссылка: <code>{url}</code></blockquote>",
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка при добавлении UTM-ссылки: {e}")
        await bot.send_message(message.from_user.id, "❌ Ошибка при добавлении UTM-ссылки", parse_mode='HTML')
    await state.clear()


utm_clicks = {}  # Временное хранилище статистики (в памяти)


@router.callback_query(F.data == "list_utm")
async def list_utm_callback(call: CallbackQuery, bot: Bot):
    if call.message.chat.id in admins_id:
        await bot.delete_message(call.message.chat.id, call.message.message_id)

        utm_links = get_urls_utm()
        builder_utm_links = InlineKeyboardBuilder()

        temp_links = []
        count_links = 0

        for url in utm_links:
            count_links += 1
            name = url.split('=')[1] if '=' in url else url
            callback_data = f"utmstat_{url}"
            button = types.InlineKeyboardButton(text=f"{name}", callback_data=callback_data)
            temp_links.append(button)

            if count_links % 2 == 0:
                builder_utm_links.row(*temp_links)
                temp_links = []

        if temp_links:
            builder_utm_links.row(*temp_links)

        builder_utm_links.row(
            types.InlineKeyboardButton(text="⬅️ Назад", callback_data="utm")
        )

        await bot.send_message(
            call.from_user.id,
            "<b>📦 Список UTM-ссылок:</b>",
            parse_mode='HTML',
            reply_markup=builder_utm_links.as_markup()
        )


@router.callback_query(F.data.startswith("utmstat_"))
async def utm_stat_callback(call: CallbackQuery, bot: Bot):
    utm = call.data.replace("utmstat_", "")

    total = users_utm_count(utm)
    passed = users_utm_count_op(utm)

    await bot.answer_callback_query(call.id)
    await bot.send_message(
        call.from_user.id,
        f"🔗 <b>UTM:</b> <code>{utm}</code>\n"
        f"📈 <b>Запусков:</b> {total}\n"
        f"✅ <b>Прошли ОП:</b> {passed}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_lotery")
async def adminka_lottery(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        builder_lottery = InlineKeyboardBuilder()
        builder_lottery.button(text='🎉 Начать лотерею', callback_data='start_lotery')
        builder_lottery.button(text='🏁 Завершить лотерею', callback_data='finish_lotery')
        builder_lottery.button(text="⬅️ Назад", callback_data="adminpanelka")
        markup_lottery = builder_lottery.adjust(2, 1).as_markup()
        lot_id = get_id_lottery_enabled()
        cash = get_cash_in_lottery()
        ticket_cash = get_ticket_cash_in_lottery()

        try:
            await bot.send_message(call.message.chat.id,
                                   f"<b>🎉 Вы вошли в админ-лотерею\n\n🎰 Активная лотерея: <code>{lot_id}</code>\n💰 Потрачено Stars: <code>{cash}</code>\n💸 Стоимость билета: <code>{ticket_cash}</code></b>",
                                   parse_mode='HTML', reply_markup=markup_lottery)
        except Exception as e:
            logging.error(f"Ошибка при получении статистики для админ-панели: {e}")
    else:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>",
                               parse_mode='HTML')


@router.callback_query(F.data == "finish_lotery")
async def finish_lotery_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        active_lottery = get_active_lottery_id()
        if not active_lottery:
            await bot.send_message(call.message.chat.id, "❌ Нет активной лотереи")
            return
        cash = get_cash_in_lottery()
        cash = float(cash) * 0.6
        markup_exit_to_admin = InlineKeyboardBuilder()
        markup_exit_to_admin.button(text="⬅️ Назад", callback_data="adminpanelka")
        markup_exit_to_admin.adjust(1)
        keyboard = markup_exit_to_admin.as_markup()
        status, win_id = finish_and_update_winner()
        if status:
            try:
                await bot.send_message(call.message.chat.id,
                                       f"<b>🎉 Лотерея завершена</b>\n\n<b>🎁 Выиграл <code>{win_id}</code>\n💰 Сумма: {cash:.2f}</b>",
                                       parse_mode='HTML', reply_markup=keyboard)
                await bot.send_message(win_id,
                                       f"<b>🎉 Вы выиграли лотерею!\n\n💰 Вы забираете 60% со всех звезд в лотерее: {cash:.2f}</b>",
                                       parse_mode='HTML')
                increment_stars(win_id, cash)
            except Exception as e:
                logging.error(f"[LOTTERY] Ошибка при отправке сообщения: {e}")
        else:
            await bot.send_message(call.message.chat.id, "<b>🚫 Нет участников с билетами</b>", parse_mode='HTML',
                                   reply_markup=keyboard)
    else:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>",
                               parse_mode='HTML')


@router.callback_query(F.data == "start_lotery")
async def start_lotery_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        await bot.send_message(call.message.chat.id, "<b>💰 Введите стоимость одного билета: </b>", parse_mode='HTML')
        await state.set_state(LotteryState.ticket_cash)
    else:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>",
                               parse_mode='HTML')


@router.message(StateFilter(LotteryState.ticket_cash))
async def handle_ticket_cash(message: Message, bot: Bot, state: FSMContext):
    try:
        ticket_cash = float(message.text)
    except ValueError:
        await message.reply("❌ Введите число!")
        return

    try:
        await bot.delete_message(message.chat.id, message.message_id)
        await bot.delete_message(message.chat.id, message.message_id - 1)
    except:
        pass

    await asyncio.sleep(1)

    create_lottery(0, ticket_cash)

    markuper = InlineKeyboardBuilder()
    markuper.button(text="⬅️ Назад", callback_data="adminpanelka")
    markuper.adjust(1)
    keyboard = markuper.as_markup()

    lot_id = get_id_lottery_enabled()
    cash = get_cash_in_lottery()

    await bot.send_message(
        chat_id=message.chat.id,
        text=f"<b>🎉 Лотерея началась!\n\n🎰 Активная лотерея: <code>{lot_id}</code>\n💰 Потрачено Stars: <code>{cash}</code>\n💸 Стоимость билета: <code>{ticket_cash}</code></b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )

    await state.clear()


@router.callback_query(F.data == "give_boost")
async def giveboost(call: CallbackQuery, bot: Bot, state: FSMContext):
    if call.from_user.id in admins_id:
        await bot.send_message(call.from_user.id, "Ввдеите ID человека:")
        await state.set_state(AdminState.WAIT_TIME_BOOSTER)


@router.message(AdminState.WAIT_TIME_BOOSTER)
async def handle_time(message: Message, bot: Bot, state: FSMContext):
    id = int(message.text)
    await state.update_data(user_id=id)
    await bot.send_message(message.from_user.id, "Введите количество дней:")
    await state.set_state(AdminState.GIVE_BOOST)


@router.message(AdminState.GIVE_BOOST)
async def handle_give(message: Message, bot: Bot, state: FSMContext):
    try:
        time = int(message.text)
        data = await state.get_data()
        user_id = data["user_id"]

        current_time = datetime.now()
        delta = timedelta(days=time)
        future_time = current_time + delta
        future_timestamp = future_time.timestamp()

        add_or_update_user_boost(user_id, future_timestamp)
        await bot.send_message(message.from_user.id, f"Вы выдали буст {user_id} на {time} дней")
    except Exception as e:
        logging.error(f"Ошибка в мануальной выдаче буста: {e}")
    await state.clear()


def build_admin_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="⚙️ Изменить конфиг", callback_data='change_config'))

    builder.row(
        InlineKeyboardButton(text='🗄️ Дамп базы', callback_data='dump'),
        InlineKeyboardButton(text='🔗 UTM-Ссылки', callback_data='utm'),
        InlineKeyboardButton(text='🎰 Лотерея', callback_data='admin_lotery')
    )

    builder.row(
        InlineKeyboardButton(text='📊 Статистика', callback_data='stats'),
        InlineKeyboardButton(text='👤 Информация о пользователе', callback_data='users_check')
    )

    builder.row(
        InlineKeyboardButton(text='✨ Выдать звёзды', callback_data='add_stars'),
        InlineKeyboardButton(text='💫 Снять звёзды', callback_data='remove_stars')
    )

    builder.row(
        InlineKeyboardButton(text='📤 Рассылка', callback_data='mailing')
    )

    builder.row(
        InlineKeyboardButton(text='🎁 Добавить промокод', callback_data='add_promo_code'),
        InlineKeyboardButton(text='❌ Удалить промокод', callback_data='remove_promo_code')
    )

    builder.row(
        InlineKeyboardButton(text='➕📢 Добавить канал', callback_data='add_channel'),
        InlineKeyboardButton(text='➖📢 Удалить канал', callback_data='remove_channel')
    )

    builder.row(
        InlineKeyboardButton(text='📋 Список промокодов', callback_data='info_promo_codes'),
        InlineKeyboardButton(text='📋 Список каналов', callback_data='info_added_channels')
    )

    builder.row(
        InlineKeyboardButton(text='✅ Задания', callback_data='tasks_menu')
    )

    builder.row(
        InlineKeyboardButton(text='🏆 Топ-50 Баланс', callback_data='top_balance'),
        InlineKeyboardButton(text='🚀 Выдать буст', callback_data='give_boost')
    )

    # Упрощенное управление заданиями и платежами без криптовалюты
    builder.row(
        InlineKeyboardButton(text='🎯 Управление заданиями', callback_data='admin_task_management')
    )

    return builder


@router.callback_query(F.data == "admin_task_management")
async def admin_task_management_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    try:
        await bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    builder = InlineKeyboardBuilder()

    # Управление рекламным балансом
    builder.button(text="💼 Рекламный баланс", callback_data="admin_ad_balance")

    # Активные задания
    builder.button(text="📋 Активные задания", callback_data="active_tasks_management")

    builder.button(text="⬅️ Назад", callback_data="adminpanelka")

    markup = builder.adjust(1, 1, 1, 1).as_markup()

    await bot.send_message(
        call.from_user.id,
        "<b>🎯 Управление заданиями и платежами</b>\n\n"
        "Выберите раздел для управления:",
        parse_mode='HTML',
        reply_markup=markup
    )


@router.callback_query(F.data == "active_tasks_management")
async def active_tasks_management_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    # Получаем все активные задания
    active_tasks = get_active_user_tasks()

    if not active_tasks:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="admin_task_management")
        markup = builder.as_markup()

        await bot.send_message(
            call.from_user.id,
            "📋 <b>Нет активных заданий</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    text = "<b>📋 Активные задания:</b>\n\n"

    for task in active_tasks:
        task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = task
        progress = (current_subscribers / target_subscribers) * 100 if target_subscribers > 0 else 0

        text += (
            f"🟢 <b>Задание #{task_id}</b>\n"
            f"👤 Создатель: {creator_id}\n"
            f"👥 Прогресс: {current_subscribers}/{target_subscribers} ({progress:.1f}%)\n"
            f"🔗 Канал: {channel_link[:50]}...\n"
            f"📊 Приоритет: {target_subscribers} подписчиков\n"
            "─────────────\n"
        )

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Удалить активное задание", callback_data="delete_active_task")
    builder.button(text="📊 Все задания", callback_data="view_user_tasks")
    builder.button(text="⬅️ Назад", callback_data="admin_task_management")
    markup = builder.adjust(1, 1, 1).as_markup()

    await bot.send_message(call.from_user.id, text, parse_mode='HTML', reply_markup=markup)


@router.callback_query(F.data == "delete_active_task")
async def delete_active_task_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    await bot.send_message(
        call.from_user.id,
        "Введите ID активного задания для удаления:\n\n"
        "⚠️ <b>Внимание:</b> Средства создателю НЕ возвращаются!"
    )
    await state.set_state(AdminState.DELETE_ACTIVE_TASK_INPUT)


async def delete_active_task_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        task_id = int(message.text)

        # Получаем информацию о задании
        task_info = get_task_by_id(task_id)
        if not task_info:
            await message.reply("❌ Задание не найдено")
            await state.clear()
            return

        task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status = task_info

        # Проверяем, что задание активно
        if status != 'active':
            await message.reply("❌ Можно удалять только активные задания")
            await state.clear()
            return

        # Удаляем задание
        delete_user_task(task_id)

        # Уведомляем создателя БЕЗ возврата средств
        try:
            await bot.send_message(
                creator_id,
                f"❌ <b>Ваше задание удалено администратором</b>\n\n"
                f"🆔 ID задания: {task_id}\n"
                f"💰 Средства НЕ возвращаются согласно правилам сервиса\n\n"
                f"📞 Для уточнения причины обратитесь к администратору",
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить создателя {creator_id}: {e}")

        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ К активным заданиям", callback_data="active_tasks_management")
        markup = builder.as_markup()

        await message.reply(
            f"✅ <b>Задание удалено</b>\n\n"
            f"🆔 ID задания: {task_id}\n"
            f"👤 Создатель: ID {creator_id}\n"
            f"💰 Средства НЕ возвращены",
            parse_mode='HTML',
            reply_markup=markup
        )

    except ValueError:
        await message.reply("❌ Введите корректный ID задания (число)")
    except Exception as e:
        logging.error(f"Ошибка при удалении активного задания: {e}")
        await message.reply("❌ Произошла ошибка при удалении задания")
    finally:
        await state.clear()


@router.callback_query(F.data == "adminpanelka")
async def adminpanelka_callback(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)

    if call.message.chat.id not in admins_id:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>",
                               parse_mode='HTML')
        return

    builder_admin = build_admin_keyboard()
    markup_admin = builder_admin.as_markup()

    try:
        user_count = get_user_count()
        total_withdrawn = get_total_withdrawn()

        msg_text = (
            f"<b>🎉 Вы вошли в панель администратора</b>\n\n"
            f"👥 Пользователей: {user_count}\n"
            f"💸 Выплачено: {total_withdrawn} ⭐️"
        )

        await bot.send_message(call.message.chat.id, msg_text, parse_mode='HTML', reply_markup=markup_admin)

    except Exception as e:
        logging.error(f"Ошибка при получении статистики для админ-панели: {e}")
        await bot.send_message(call.message.chat.id,
                               "<b>🎉 Вы вошли в панель администратора</b>\n\n⚠️ Ошибка при получении статистики.",
                               parse_mode='HTML', reply_markup=markup_admin)


@router.callback_query(F.data == "change_config")
async def change_config_callback(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)

    subgram_status = "🔴 Выключен" if button_subgram[0] == False else "🟢 Включён"

    builder_config = InlineKeyboardBuilder()

    builder_config.button(text='💎 Subgram: {}'.format(subgram_status), callback_data='subgram_checker')
    builder_config.button(text="👥 Рефералы", callback_data="config_referrals")
    builder_config.button(text="📝 Задания", callback_data="config_tasks")
    builder_config.button(text="🚀 Буст", callback_data="config_boost")
    builder_config.button(text="🖱️ Клик", callback_data="config_click")
    builder_config.button(text="📅 Ежедневка", callback_data="config_daily")
    builder_config.button(text="⬅️ Назад", callback_data="adminpanelka")

    markup_config = builder_config.adjust(1, 2, 2, 1, 1).as_markup()

    await bot.send_message(
        call.message.chat.id,
        "<b>🛠️ Изменить конфиг</b>\n\nВыберите раздел для изменения настроек:",
        parse_mode="HTML",
        reply_markup=markup_config
    )


@router.callback_query(F.data == "subgram_checker")
async def subgram_checker_callback(call: CallbackQuery, bot: Bot):
    if button_subgram[0] == False:
        button_subgram[0] = True
    else:
        button_subgram[0] = False
    # await bot.delete_message(call.message.chat.id, call.message.message_id)
    await change_config_callback(call, bot)


@router.callback_query(F.data == "config_referrals")
async def config_referrals_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    msg_text = (
        "✨ <b>Настройка Рефералов</b> ✨\n\n"
        "Введите новые параметры оплаты для рефералов.\n"
        "Формат: <code>nac_1 nac_2 nac_3 refs_boost refs_noboost</code>\n"
        "Пример: <code>0.8 1.2 1.6 12 18</code>\n\n"
        "<i>🔄 Обновляем настройки...</i>"
    )
    await bot.send_message(call.message.chat.id, msg_text, parse_mode="HTML")
    await state.set_state(ConfigStates.waiting_for_referrals)


@router.message(ConfigStates.waiting_for_referrals)
async def process_referrals(message: Message, state: FSMContext, bot: Bot):
    try:
        parts = message.text.split()
        if len(parts) != 5:
            raise ValueError("Неверное количество параметров. Ожидается 5 значений.")
        new_nac_1, new_nac_2, new_nac_3, new_refs_boost, new_refs_noboost = parts
        nac_1[0] = float(new_nac_1)
        nac_2[0] = float(new_nac_2)
        nac_3[0] = float(new_nac_3)
        refs_boost[0] = int(new_refs_boost)
        refs_noboost[0] = int(new_refs_noboost)
        await bot.send_message(
            message.chat.id,
            "✅ <b>Рефералы</b> успешно обновлены!",
            parse_mode="HTML"
        )
    except Exception as e:
        await bot.send_message(
            message.chat.id,
            f"❌ <b>Ошибка:</b> {e}\nПопробуйте снова.",
            parse_mode="HTML"
        )
    finally:
        await state.clear()


# Задания
@router.callback_query(F.data == "config_tasks")
async def config_tasks_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    msg_text = (
        "✏️ <b>Настройка Заданий</b> ✏️\n\n"
        "Введите новое значение оплаты за выполнение заданий и необходимых для вывода.\n"
        "Формат: <code>0.9 10</code>\n"
        "Пример: <code>0.9 10</code>\n\n"
        "<i>🔄 Обновляем настройки...</i>"
    )
    await bot.send_message(call.message.chat.id, msg_text, parse_mode="HTML")
    await state.set_state(ConfigStates.waiting_for_tasks)


@router.message(ConfigStates.waiting_for_tasks)
async def process_tasks(message: Message, state: FSMContext, bot: Bot):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Неверное количество параметров. Ожидается 2 значения (например, 0.9 10).")

        new_grant = float(parts[0])
        new_needed = int(parts[1])

        task_grant[0] = new_grant
        task_needed[0] = new_needed

        await bot.send_message(
            message.chat.id,
            "✅ <b>Задания</b> успешно обновлены!",
            parse_mode="HTML"
        )
    except Exception as e:
        await bot.send_message(
            message.chat.id,
            f"❌ <b>Ошибка:</b> {e}\nПопробуйте снова.",
            parse_mode="HTML"
        )
    finally:
        await state.clear()


# Буст
@router.callback_query(F.data == "config_boost")
async def config_boost_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    msg_text = (
        "🚀 <b>Настройка Буста</b> 🚀\n\n"
        "Введите новую стоимость буста.\n"
        "Формат: <code>650</code>\n"
        "Пример: <code>650</code>\n\n"
        "<i>🔄 Обновляем настройки...</i>"
    )
    await bot.send_message(call.message.chat.id, msg_text, parse_mode="HTML")
    await state.set_state(ConfigStates.waiting_for_boost)


@router.message(ConfigStates.waiting_for_boost)
async def process_boost(message: Message, state: FSMContext, bot: Bot):
    try:
        new_value = int(message.text)
        boost_cost[0] = new_value
        await bot.send_message(
            message.chat.id,
            "✅ <b>Буст</b> успешно обновлён!",
            parse_mode="HTML"
        )
    except Exception as e:
        await bot.send_message(
            message.chat.id,
            f"❌ <b>Ошибка:</b> {e}\nПопробуйте снова.",
            parse_mode="HTML"
        )
    finally:
        await state.clear()


# Клик
@router.callback_query(F.data == "config_click")
async def config_click_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    msg_text = (
        "🖱️ <b>Настройка Клика</b> 🖱️\n\n"
        "Введите новое значение оплаты за клик.\n"
        "Формат: <code>0.2</code>\n"
        "Пример: <code>0.2</code>\n\n"
        "<i>🔄 Обновляем настройки...</i>"
    )
    await bot.send_message(call.message.chat.id, msg_text, parse_mode="HTML")
    await state.set_state(ConfigStates.waiting_for_click)


@router.message(ConfigStates.waiting_for_click)
async def process_click(message: Message, state: FSMContext, bot: Bot):
    try:
        new_value = float(message.text)
        click_grant[0] = new_value
        await bot.send_message(
            message.chat.id,
            "✅ <b>Клик</b> успешно обновлён!",
            parse_mode="HTML"
        )
    except Exception as e:
        await bot.send_message(
            message.chat.id,
            f"❌ <b>Ошибка:</b> {e}\nПопробуйте снова.",
            parse_mode="HTML"
        )
    finally:
        await state.clear()


# Ежедневка
@router.callback_query(F.data == "config_daily")
async def config_daily_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    msg_text = (
        "📅 <b>Настройка Ежедневного Гифта</b> 📅\n\n"
        "Введите новое значение для ежедневного гифта.\n"
        "Формат: <code>1.5</code>\n"
        "Пример: <code>1.5</code>\n\n"
        "<i>🔄 Обновляем настройки...</i>"
    )
    await bot.send_message(call.message.chat.id, msg_text, parse_mode="HTML")
    await state.set_state(ConfigStates.waiting_for_daily)


@router.message(ConfigStates.waiting_for_daily)
async def process_daily(message: Message, state: FSMContext, bot: Bot):
    try:
        new_value = float(message.text)
        GIFT_AMOUNT[0] = new_value
        await bot.send_message(
            message.chat.id,
            "✅ <b>Ежедневный Гифт</b> успешно обновлён!",
            parse_mode="HTML"
        )
    except Exception as e:
        await bot.send_message(
            message.chat.id,
            f"❌ <b>Ошибка:</b> {e}\nПопробуйте снова.",
            parse_mode="HTML"
        )
    finally:
        await state.clear()


@router.callback_query(F.data == "stats")
async def stats_callback(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    day_clicker = get_clicks_by_period('day')
    week_clicker = get_clicks_by_period('week')
    month_clicker = get_clicks_by_period('month')

    day_users = get_users_by_period('day')
    week_users = get_users_by_period('week')
    month_users = get_users_by_period('month')

    markup_stats = InlineKeyboardBuilder()
    markup_stats.button(text="⬅️ Назад", callback_data="adminpanelka")
    markup_stats.adjust(1)
    markup_stats = markup_stats.as_markup()

    await bot.send_message(call.from_user.id, f"""<b>📊 Статистика

🛎 Клики:
• За день: {day_clicker}
• За неделю: {week_clicker}
• За всё время: {month_clicker}

👤 Пользователи:
• За день: {day_users}
• За неделю: {week_users}
• За всё время: {month_users}</b>
""", parse_mode='HTML', reply_markup=markup_stats)


@router.message(F.text == '/why')
async def why_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    await bot.send_message(user_id, f"""<b>🌟 Звезды —</b> <i>официальная</i> валюта Telegram.

💡 За каждого приглашенного друга вы получаете 1⭐️

✨ Звезды можно:
- Вывести в реальные деньги
- Дарить друзьям подарки
- Использовать для оплаты цифровых товаров/услуг в ботах

<b>💫 Счастливые часы</b>
Иногда запускаются в случайное время ⏰!
В это время ты можешь получать:
• 2⭐️ за каждого друга 👫
• <b>Увеличенные бонусы</b> за выполнение заданий и клики до <b>0.02</b>⭐️📝

✨ Следи за уведомлениями, чтобы не упустить шанс!

<b>🗓️ Вывод звезд</b>
Выдача подарков(звезд) проходит по субботам и в ограниченном количестве.
Подавай заявку заранее, что-бы получить раньше всех!

<b>☎️ По всем вопросам/рекламе/сотрудничеству:</b> {admin_username}
""", parse_mode='HTML')


@router.callback_query(F.data.startswith('withdraw:'))
async def handle_withdraw_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    username = call.from_user.username
    user_full_name = call.from_user.full_name  # Получаем имя профиля

    # Эта проверка на username оставлена, так как она присутствует в вашем исходном коде
    # Если username не является строгим требованием для вывода, эту часть можно убрать.
    if username is None:
        await bot.answer_callback_query(call.id, "⚠️ Для вывода необходимо установить username.", show_alert=True)
        return

    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    # Безопасная обработка callback_data
    try:
        data_parts = call.data.split(':')
        if len(data_parts) < 2:
            await bot.answer_callback_query(call.id, "❌ Неверный формат данных", show_alert=True)
            return

        stars = data_parts[1]
        emoji = data_parts[2] if len(data_parts) > 2 else None
    except (IndexError, ValueError):
        await bot.answer_callback_query(call.id, "❌ Ошибка при обработке данных", show_alert=True)
        return

    count_refs = get_weekly_referrals(call.from_user.id)
    count_tasks = get_tasks_count_by_user_for_week(call.from_user.id)

    try:
        if stars not in ("premium1", "premium2"):
            stars = int(stars)
        elif stars == "premium1":
            stars = 400
        elif stars == "premium2":
            stars = 1100

        if get_balance_user(call.from_user.id) < stars:
            await bot.answer_callback_query(call.id, "❌ У вас недостаточно звезд для вывода!", show_alert=True)
            return
        elif user_id not in admins_id and count_refs < (refs_boost[0] if user_in_booster(user_id) else refs_noboost[0]):
            required_refs = refs_boost[0] if user_in_booster(user_id) else refs_noboost[0]
            await bot.answer_callback_query(call.id,
                                            f"❌ Для вывода надо минимум {required_refs} рефералов за текущую неделю! У тебя {count_refs}",
                                            show_alert=True)
            return
        elif user_id not in admins_id and count_tasks < task_needed[0]:
            await bot.answer_callback_query(call.id,
                                            f"❌ Для вывода надо выполнить минимум {task_needed[0]} заданий за текущую неделю! У тебя {count_tasks}",
                                            show_alert=True)
            return
        else:
            await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
            deincrement_stars(user_id, stars)
            withdrawal_id = add_withdrawal(user_id, stars, username)  # Получаем ID вывода и передаем username

            # Новая логика для автоматического вывода подарков
            if stars not in (400, 1100):
                manager_username = "starsfull_manager"
                kb = InlineKeyboardBuilder()
                kb.button(text="Написать юзерботу", url=f"https://t.me/{manager_username}")
                await bot.send_message(
                    user_id,
                    (
                        "✅ Вывод успешен!\n\n"
                        "Чтобы получить подарок, нажмите кнопку ниже и отправьте менеджеру сообщение: \"Привет\".\n\n"
                        f"Менеджер: @{manager_username}\n"
                        "Подарок придет через 5 минут автоматически."
                    ),
                    reply_markup=kb.as_markup(),
                    parse_mode='HTML'
                )

                emoji_to_gift = {
                    '💝': 5170145012310081615, '🧸': 5170233102089322756, '🎁': 5170250947678437525,
                    '🌹': 5168103777563050263, '🎂': 5170144170496491616, '💐': 5170314324215857265,
                    '🚀': 5170564780938756245, '🏆': 5168043875654172773, '💍': 5170690322832818290,
                    '💎': 5170521118301225164, '🍾': 6028601630662853006,
                }
                gift_id = emoji_to_gift.get(emoji)
                if gift_id:
                    bot_username = (await bot.me()).username
                    schedule_gift(
                        bot=bot,
                        user_id=user_id,
                        username=call.from_user.username,
                        gift_id=gift_id,
                        delay_seconds=300,
                        stars=stars,
                        withdrawal_id=withdrawal_id,
                        user_full_name=user_full_name,
                        bot_username=bot_username
                    )

                # Завершаем, чтобы старая логика не выполнилась
                return

            # Отправка уведомлений админам
            if stars == 400:
                for admin in admins_id:
                    button_refs = InlineKeyboardBuilder()
                    button_refs.button(text="👤 Рефераллы", callback_data=f"refferals:{user_id}")
                    markup_adminser = button_refs.as_markup()
                    # ИСПОЛЬЗУЕМ user_full_name
                    await bot.send_message(admin,
                                           f"<b>❗️❗️❗️\n⚠️ Пользователь {user_full_name} | ID: {user_id} запросил вывод Telegram Premium на 1 месяц</b>",
                                           parse_mode='HTML', reply_markup=markup_adminser)
            elif stars == 1100:
                for admin in admins_id:
                    button_refs = InlineKeyboardBuilder()
                    button_refs.button(text="👤 Рефераллы", callback_data=f"refferals:{user_id}")
                    markup_adminser = button_refs.as_markup()
                    # ИСПОЛЬЗУЕМ user_full_name
                    await bot.send_message(admin,
                                           f"<b>❗️❗️❗️\n⚠️ Пользователь {user_full_name} | ID: {user_id} запросил вывод Telegram Premium на 3 месяца</b>",
                                           parse_mode='HTML', reply_markup=markup_adminser)

            # Отправка сообщения в канал выплат и пользователю
            # Этот блок теперь выполняется только для Premium
            if stars in (400, 1100):
                if stars == 400:
                    level_premium = 1
                    # success, id_v = add_withdrawale(username, user_id, stars) # Эта логика, похоже, устарела или дублируется
                    status = get_status_withdrawal(user_id)
                    pizda = await bot.send_message(channel_viplat_id,
                                                   f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {user_full_name} | ID {user_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>{status}</b>",
                                                   # ИСПОЛЬЗУЕМ user_full_name
                                                   disable_web_page_preview=True, parse_mode='HTML')
                    builder_channel = InlineKeyboardBuilder()
                    # Передаем user_full_name в callback_data
                    builder_channel.button(text="✅ Отправить",
                                           callback_data=f"premium_paid:{withdrawal_id}:{pizda.message_id}:{user_id}:{user_full_name}:{level_premium}")
                    # Передаем user_full_name в callback_data
                    builder_channel.button(text="❌ Отклонить",
                                           callback_data=f"premium_denied:{withdrawal_id}:{pizda.message_id}:{user_id}:{user_full_name}:{level_premium}")
                    builder_channel.button(text="👤 Профиль", url=f"tg://user?id={user_id}")
                    markup_channel = builder_channel.adjust(2, 1).as_markup()
                    await bot.edit_message_text(chat_id=pizda.chat.id, message_id=pizda.message_id,
                                                text=f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {user_full_name} | ID {user_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>{status}</b>",
                                                # ИСПОЛЬЗУЕМ user_full_name
                                                disable_web_page_preview=True, parse_mode='HTML',
                                                reply_markup=markup_channel)
                    await bot.send_message(user_id,
                                           f"<b>✅ Вы успешно отправили заявку на вывод 🎁 Telegram Premium: 1 месяц</b>",
                                           parse_mode='HTML', reply_markup=markup_back)
                elif stars == 1100:
                    level_premium = 3
                    # success, id_v = add_withdrawale(username, user_id, stars) # Эта логика, похоже, устарела или дублируется
                    status = get_status_withdrawal(user_id)
                    pizda = await bot.send_message(channel_viplat_id,
                                                   f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {user_full_name} | ID {user_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>{status}</b>",
                                                   # ИСПОЛЬЗУЕМ user_full_name
                                                   disable_web_page_preview=True, parse_mode='HTML')
                    builder_channel = InlineKeyboardBuilder()
                    # Передаем user_full_name в callback_data
                    builder_channel.button(text="✅ Отправить",
                                           callback_data=f"premium_paid:{withdrawal_id}:{pizda.message_id}:{user_id}:{user_full_name}:{level_premium}")
                    # Передаем user_full_name в callback_data
                    builder_channel.button(text="❌ Отклонить",
                                           callback_data=f"premium_denied:{withdrawal_id}:{pizda.message_id}:{user_id}:{user_full_name}:{level_premium}")
                    builder_channel.button(text="👤 Профиль", url=f"tg://user?id={user_id}")
                    markup_channel = builder_channel.adjust(2, 1).as_markup()
                    await bot.edit_message_text(chat_id=pizda.chat.id, message_id=pizda.message_id,
                                                text=f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {user_full_name} | ID {user_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>{status}</b>",
                                                # ИСПОЛЬЗУЕМ user_full_name
                                                disable_web_page_preview=True, parse_mode='HTML',
                                                reply_markup=markup_channel)
                    await bot.send_message(user_id,
                                           f"<b>✅ Вы успешно отправили заявку на вывод 🎁 Telegram Premium: 3 месяца</b>",
                                           parse_mode='HTML', reply_markup=markup_back)
    except ValueError:
        await bot.answer_callback_query(call.id, "❌ Неверный формат суммы вывода.", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка при обработке вывода: {e}")
        await bot.answer_callback_query(call.id, "❌ Произошла ошибка при обработке вашего запроса на вывод.",
                                        show_alert=True)


@router.callback_query(F.data.startswith('refferals'))
async def handle_refferals_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        return

    try:
        _, user_id_str = call.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await call.answer("Неверный формат callback_data", show_alert=True)
        return

    refferals = get_user_refferals_list_and_username(user_id)

    base_data = [
        ("🆔 ID Пользователя", f"<code>{user_id}</code>"),
        ("🚀 Количество рефералов", f"{len(refferals)}")
    ]

    html_response = [f"<b>{key}: {value}</b>" for key, value in base_data]

    file_lines = [f"{key}: {value}" for key, value in base_data]

    if refferals:
        html_response.append("<b>Список рефералов (ID и username):</b>")
        file_lines.append("Список рефералов (ID и username):")

        for index, (ref_id, username) in enumerate(refferals, 1):
            html_line = f"{index}. ID: {ref_id}, Username: @{username}"
            file_line = f"{index}. ID: {ref_id}, Username: @{username}"

            html_response.append(html_line)
            file_lines.append(file_line)
    else:
        html_response.append("<i>У пользователя нет рефералов</i>")
        file_lines.append("У пользователя нет рефералов")

    html_message = '\n'.join(html_response)
    file_content = '\n'.join(file_lines).encode('utf-8')

    try:
        if len(refferals) < 50:
            await call.message.answer(html_message, parse_mode='HTML')
        else:
            document = BufferedInputFile(
                file_content,
                filename=f'refferals_{user_id}.txt'
            )
            await bot.send_document(
                chat_id=call.from_user.id,
                document=document
            )

        await call.answer()

    except Exception as e:
        error_msg = "Ошибка при отправке сообщения" if len(refferals) < 50 else "Ошибка при отправке файла"
        print(f"Error: {e}")
        await call.answer(error_msg, show_alert=True)


@router.callback_query(F.data.startswith('premium_paid'))
async def handle_premium_paid_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        try:
            data_parts = call.data.split(":")
            if len(data_parts) < 6:
                await call.answer("❌ Неверный формат данных", show_alert=True)
                return

            id_v = int(data_parts[1])
            mesag_id = int(data_parts[2])
            us_id = int(data_parts[3])
            us_full_name = data_parts[4]  # Получаем полное имя
            level_premium = int(data_parts[5])
        except (ValueError, IndexError):
            await call.answer("❌ Ошибка при обработке данных", show_alert=True)
            return

        if level_premium == 1:
            await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id,
                                        text=f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {us_full_name} | ID: {us_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>Подарок отправлен 🎁</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>",
                                        # ИСПОЛЬЗУЕМ us_full_name
                                        parse_mode='HTML', disable_web_page_preview=True)
        elif level_premium == 3:  # Исправлено на 3, как и должно быть
            await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id,
                                        text=f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {us_full_name} | ID: {us_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>Подарок отправлен 🎁</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>",
                                        # ИСПОЛЬЗУЕМ us_full_name
                                        parse_mode='HTML', disable_web_page_preview=True)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")


@router.callback_query(F.data.startswith('premium_denied'))
async def handle_premium_denied_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        try:
            data_parts = call.data.split(":")
            if len(data_parts) < 6:
                await call.answer("❌ Неверный формат данных", show_alert=True)
                return

            id_v = int(data_parts[1])
            mesag_id = int(data_parts[2])
            us_id = int(data_parts[3])
            us_full_name = data_parts[4]  # Получаем полное имя
            level_premium = int(data_parts[5])
        except (ValueError, IndexError):
            await call.answer("❌ Ошибка при обработке данных", show_alert=True)
            return

        if level_premium == 1:
            await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id,
                                        text=f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {us_full_name} | ID: {us_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>Отказано 🚫</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>",
                                        # ИСПОЛЬЗУЕМ us_full_name
                                        parse_mode='HTML', disable_web_page_preview=True)
        elif level_premium == 3:  # Исправлено на 3, как и должно быть
            await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id,
                                        text=f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {us_full_name} | ID: {us_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>Отказано 🚫</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>",
                                        # ИСПОЛЬЗУЕМ us_full_name
                                        parse_mode='HTML', disable_web_page_preview=True)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")


@router.callback_query(F.data.startswith('play_game_with_bet'))
async def handle_game_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    try:
        bet = float(call.data.split(':')[1])
        balance = get_balance_user(user_id)

        if balance >= bet:
            deincrement_stars(user_id, bet)

            if random.random() < 0.30:
                coefficients = [0, 0.5, 1, 1.5, 2, 3, 5, 10]
                weights = [0.35, 0.3, 0.2, 0.08, 0.04, 0.02, 0.005, 0.005]
                coefficient = random.choices(coefficients, weights=weights)[0]
                winnings = bet * coefficient

                if coefficient > 0:
                    await bot.answer_callback_query(call.id, f"🎉 ОГРОМНАЯ ПОБЕДА! Вы выиграли: {winnings:.2f}",
                                                    show_alert=True)
                    chat = await bot.get_chat(user_id)
                    first_name = chat.first_name
                    bot_url = "https://t.me/" + (await bot.me()).username
                    await bot.send_message(
                        id_channel_game,
                        f"<b>🎉 Поздравляем! 🏆</b>\n\nПользователь {first_name}(ID: <code>{user_id}</code>)\n"
                        f"<i>выиграл</i> <b>{winnings:.2f}</b>⭐️ на ставке <b>{bet:.2f}</b>⭐️ 🎲\n\n"
                        f"Коэффициент: <i>{coefficient}</i>✨\n\n"
                        f"<b>🎉 Потрясающий выигрыш! 🏆✨ 🎉</b>\n\n🎯 Не упусти свой шанс! <a href='{bot_url}'>Испытать удачу!🍀</a>",
                        disable_web_page_preview=True,
                        parse_mode='HTML'
                    )
                    increment_stars(user_id, winnings)
                    new_balance = get_balance_user(user_id)

                    builder_game = InlineKeyboardBuilder()
                    builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
                    builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
                    builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
                    builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
                    builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
                    builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
                    builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
                    markup_game = builder_game.adjust(3, 3, 1).as_markup()

                    input_photo_game = FSInputFile("photos/mini_game.jpg")
                    await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
                    await bot.send_photo(user_id, photo=input_photo_game,
                                         caption=f"<b>💰 У тебя на счету:</b> {new_balance}⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}",
                                         parse_mode='HTML', reply_markup=markup_game)
                else:
                    await bot.answer_callback_query(call.id,
                                                    f"😔 Удача была близко, но коэффициент 0.\nВы ничего не выиграли.",
                                                    show_alert=True)
                    new_balance = get_balance_user(user_id)
                    builder_game = InlineKeyboardBuilder()
                    builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
                    builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
                    builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
                    builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
                    builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
                    builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
                    builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
                    markup_game = builder_game.adjust(3, 3, 1).as_markup()
                    input_photo_game_lose = FSInputFile("photos/mini_game.jpg")
                    await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
                    await bot.send_photo(user_id, photo=input_photo_game_lose,
                                         caption=f"<b>💰 У тебя на счету:</b> {new_balance}⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}",
                                         parse_mode='HTML', reply_markup=markup_game)

            else:
                await bot.answer_callback_query(call.id, f"😔 К сожалению, сегодня удача не на вашей стороне.",
                                                show_alert=True)
                new_balance = get_balance_user(user_id)
                builder_game = InlineKeyboardBuilder()
                builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
                builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
                builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
                builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
                builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
                builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
                builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
                markup_game = builder_game.adjust(3, 3, 1).as_markup()
                input_photo_game_no_luck = FSInputFile("photos/mini_game.jpg")
                await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
                await bot.send_photo(user_id, photo=input_photo_game_no_luck,
                                     caption=f"<b>💰 У тебя на счету:</b> {new_balance}⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}",
                                     parse_mode='HTML', reply_markup=markup_game)
        else:
            await bot.answer_callback_query(call.id, "😞 У тебя недостаточно звезд для этой ставки.", show_alert=True)
    except ValueError:
        await bot.answer_callback_query(call.id, "❌ Неверный формат ставки.", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка в мини-игре: {e}")
        await bot.answer_callback_query(call.id, "❌ Произошла ошибка в игре.", show_alert=True)


@router.callback_query(F.data.startswith('task_check'))
async def handle_task_callback(call: CallbackQuery, bot: Bot):
    try:
        data_parts = call.data.split(":")
        if len(data_parts) < 4:
            await bot.answer_callback_query(call.id, "❌ Неверный формат данных", show_alert=True)
            return

        _, reward, task_id_str, chat_id = data_parts
        task_id = int(task_id_str)
        user_id = call.from_user.id
        reward = float(reward)
    except (ValueError, IndexError):
        await bot.answer_callback_query(call.id, "❌ Ошибка при обработке данных задания", show_alert=True)
        return

    completed_task = get_completed_tasks_for_user(user_id)
    if task_id in completed_task:
        await bot.answer_callback_query(call.id, "❌ Задание уже выполнено.", show_alert=True)
        return

    if chat_id != "None":
        try:
            chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                await bot.answer_callback_query(call.id, "❌ Вы не подписались на канал!")
                return
        except Exception as e:
            print(f"error in check subs in tasks: {e}")

    await bot.answer_callback_query(call.id, f"✅ Задание выполнено. Начислено: {reward}⭐️")
    increment_current_completed(task_id)
    complete_task_for_user(user_id, task_id)
    add_completed_task(user_id)
    increment_stars(user_id, reward)

    # Добавляем отслеживание подписки на 3 дня для обычных заданий
    add_task_subscription_tracking(
        user_id=user_id,
        task_id=task_id,
        task_type='regular_task',
        channel_id=int(chat_id),
        reward_amount=reward
    )

    # Удаляем текущее сообщение с заданием перед показом следующего
    try:
        await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
    except TelegramBadRequest as e:
        if "message to delete not found" not in str(e).lower():
            logging.error(f"Ошибка при удалении сообщения с заданием: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при удалении сообщения с заданием: {e}")

    # Показываем следующее задание
    await show_next_task(call, bot)


@router.callback_query(F.data == 'click_star')
async def click_star_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = call.from_user.id
    current_time = time.time()

    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    if chat_id not in admins_id:
        if button_subgram[0] == True:
            response = await request_op(
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

    try:
        last_click_time_db = get_last_click_time(user_id)
        if last_click_time_db:
            time_since_last_click = current_time - last_click_time_db
            if time_since_last_click < DELAY_TIME:
                remaining_time = DELAY_TIME - time_since_last_click
                await bot.answer_callback_query(call.id,
                                                f"⌛️ Подождите еще {int(remaining_time)} секунд перед следующим кликом.",
                                                show_alert=True)
                return
    except Exception as e:
        logging.error(f"Ошибка при проверке времени клика: {e}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при проверке времени. Попробуйте позже.",
                                        show_alert=True)
        return

    try:
        click_count = get_count_clicks(user_id)
        if click_count % 5 == 0:
            await bot.answer_callback_query(call.id,
                                            "⚠️ Обнаружена подозрительная активность, пройдите проверку на бота.")
            if call.message:
                await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
            else:
                logging.warning("call.message is None, cannot delete message.")

            vegetables_emojis = ['🥕', '🍅', '🍆', '🥔', '🥦', '🥬', '🥒', '🧅', '🌽', '🌶️']
            correct_vegetable = random.choice(vegetables_emojis)
            other_vegetables = random.sample([v for v in vegetables_emojis if v != correct_vegetable], 2)
            options = [correct_vegetable] + other_vegetables
            random.shuffle(options)
            markup_captcha = InlineKeyboardBuilder()
            for option in options:
                markup_captcha.button(text=option, callback_data=f'veg_{option}')
            markup_captcha.adjust(3)
            await bot.send_message(user_id, f"<b>Ответ на капчу: {correct_vegetable}</b>",
                                   reply_markup=markup_captcha.as_markup(), parse_mode='HTML')
            await state.update_data(captcha_correct_answer=correct_vegetable)
            await state.set_state(CaptchaClick.waiting_click_captcha)
            return

        update_last_click_time(user_id)

        if user_exists(user_id):
            random_value = click_grant[0]
            reward = random_value * 2.5 if user_in_booster(user_id) else random_value
            increment_stars(user_id, reward)
            update_click_count(user_id)

            await bot.answer_callback_query(call.id, f"🎉 Ты получил {reward}⭐️", show_alert=True)
            await show_advert(call.from_user.id)
        else:
            await bot.answer_callback_query(call.id,
                                            "⚠️ Произошла ошибка. Пожалуйста, перезапустите бота командой /start.",
                                            show_alert=True)

    except Exception as e:
        logging.error(f"Ошибка при обработке клика: {e}, type: {type(e)}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при начислении звезд за клик.", show_alert=True)


@router.callback_query(F.data.startswith('veg_'))
async def handle_captcha_click(call: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = call.from_user.id
    user_answer = call.data.split('_')[1]

    data = await state.get_data()
    correct_answer = data.get('captcha_correct_answer')

    if correct_answer is None:
        logging.error(f"Ошибка: captcha_correct_answer не найден для пользователя {user_id}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка. Пожалуйста, повторите попытку.", show_alert=True)
        await state.clear()
        return

    if correct_answer == user_answer:
        update_last_click_time(user_id)
        if user_exists(user_id):
            random_value = click_grant[0]
            await bot.answer_callback_query(call.id,
                                            f"💫 Вы прошли проверку на бота\n🎉 Ты получил(а) {random_value * 2.5 if user_in_booster(user_id) else random_value}⭐️",
                                            show_alert=True)
            increment_stars(user_id, random_value * 2.5 if user_in_booster(user_id) else random_value)
            update_click_count(user_id)
            await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
            await send_main_menu(user_id, bot)
            await state.clear()
        else:
            await bot.answer_callback_query(call.id,
                                            "⚠️ Произошла ошибка. Пожалуйста, перезапустите бота командой /start.",
                                            show_alert=True)
            await state.clear()
    else:
        await bot.answer_callback_query(call.id, "❌ Неправильно!", show_alert=True)


@router.callback_query(F.data == "users_check")
async def users_check_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите ID пользователя:")
    await state.set_state(AdminState.USERS_CHECK)


@router.callback_query(F.data == "add_stars")
async def admin_add_stars_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(
        call.from_user.id,
        "Для выдачи звезд необходимо написать ID:Количество звезд.\nПример: 123:5"
    )
    await state.set_state(AdminState.ADD_STARS)


@router.callback_query(F.data == "remove_stars")
async def admin_remove_stars_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id,
                           "Для снятия звезд необходимо написать ID:Количество звезд.\nПример: 123:5")
    await state.set_state(AdminState.REMOVE_STARS)


@router.message(AdminState.REMOVE_STARS)
async def admin_remove_stars_process(message: types.Message, bot: Bot, state: FSMContext):
    try:
        user_id, stars = map(int, message.text.split(':'))
        deincrement_stars(user_id, stars)
        await bot.send_message(message.from_user.id, f"Звезды успешно сняты у пользователя {user_id}.")
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка при снятии звезд: {e}")
        await bot.send_message(message.from_user.id,
                               "Ошибка при обработке данных. Убедитесь, что введены ID и количество звезд в формате: 123:5")


@router.callback_query(F.data.startswith("subgram-task"))
async def subgram_task_callback(call: CallbackQuery, bot: Bot):
    try:
        user = call.from_user
        user_id = user.id
        sponsor_count = int(call.data.split(":")[1])

        # Проверка подписки на все каналы
        response = await request_task(
            user_id=user_id,
            chat_id=call.message.chat.id,
            first_name=user.first_name,
            language_code=user.language_code,
            bot=bot
        )
        if response != 'ok':
            await bot.answer_callback_query(call.id, "❌ Вы всё ещё не подписаны на все каналы!", show_alert=True)
            return

        # Проверка уже сохранённых ссылок
        links = [
            button.url
            for row in call.message.reply_markup.inline_keyboard
            for button in row if button.url
        ]
        all_links_id = get_urls_by_id(user_id)
        count_checker = sum(1 for url in links if url in all_links_id)

        if count_checker == sponsor_count:
            await bot.answer_callback_query(call.id, 'Вы уже выполнили задание', show_alert=True)
            return

        # Сохраняем новые URL
        for url in links:
            add_url(user_id, url)

        # Завершение задания
        await bot.answer_callback_query(call.id, 'Спасибо за подписку 👍', show_alert=True)
        increment_stars(user_id, task_grant[0])
        add_completed_task(user_id)
        increment_counter_tasks(user_id, sponsor_count)

        # Удаление текущего сообщения (с кнопками)
        try:
            await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
        except TelegramBadRequest as e:
            if "message to delete not found" not in str(e).lower():
                logging.error(f"Ошибка при удалении сообщения с subgram заданием: {e}")
        except Exception as e:
            logging.error(f"Неожиданная ошибка при удалении сообщения с subgram заданием: {e}")

        # Удаляем также предыдущее сообщение с заданием, если есть
        await delete_task_message(bot, user_id)

        # Показываем следующее задание
        await show_next_task(call, bot)

    except Exception as e:
        logging.error(f"Ошибка при выполнении subgram-задания: {e}")
        await bot.answer_callback_query(
            call.id,
            "⚠️ Произошла ошибка. Пожалуйста, повторите попытку.",
            show_alert=True
        )


@router.callback_query(F.data.startswith("subgram-op"))
async def subgram_op_callback(call: CallbackQuery, bot: Bot):
    try:
        user = call.from_user
        user_id = user.id
        ref_id = None

        args = call.data.split(':')
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
        elif len(args) > 1:
            ref_id = args[1]

        response = await request_op(
            user_id=user_id,
            chat_id=call.message.chat.id,
            first_name=user.first_name,
            language_code=user.language_code,
            bot=bot,
            ref_id=ref_id,
            is_premium=getattr(user, 'is_premium', None)
        )

        if response != 'ok':
            await bot.answer_callback_query(call.id, "❌ Вы всё ещё не подписаны на все каналы!", show_alert=True)
            return

        await bot.answer_callback_query(call.id, 'Спасибо за подписку 👍', show_alert=True)

        if not user_exists(user_id):
            try:
                urls_utm = get_urls_utm()
                for url in urls_utm:
                    parts = url.split('=')
                    if len(parts) >= 2:
                        url_title = parts[1]
                        if str(ref_id) == url_title:
                            users_add_utm_op(url)
                            ref_id = None
                            break
                add_user(user_id, user.username, ref_id)
                await handle_referral_bonus(ref_id, user_id, bot)
            except Exception as e:
                logging.error(f"User registration error: {e}")

        await send_main_menu(user_id, bot)

    except Exception as e:
        logging.error(f"Subgram op error: {e}", exc_info=True)
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при проверке подписки", show_alert=True)


async def handle_referral_bonus(ref_id: Optional[int], new_user_id: int, bot: Bot):
    if not ref_id or not user_exists(ref_id):
        return

    try:
        increment_referrals(ref_id)
        c_refs = get_user_referrals_count(ref_id)
        if c_refs < 50:
            nac = nac_1[0] * 2 if user_in_booster(ref_id) else nac_1[0]
            increment_stars(ref_id, nac)
        elif 50 <= c_refs < 250:
            nac = nac_2[0] * 2 if user_in_booster(ref_id) else nac_2[0]
            increment_stars(ref_id, nac)
        else:
            nac = nac_3[0] * 2 if user_in_booster(ref_id) else nac_3[0]
            increment_stars(ref_id, nac)
        new_ref_link = f"https://t.me/{(await bot.me()).username}?start={ref_id}"
        await bot.send_message(
            ref_id,
            f"🎉 Пользователь <code>{new_user_id}</code> запустил бота по вашей ссылке!\n"
            f"Вы получили +{nac}⭐️ за реферала.\n"
            f"Поделитесь ссылкой ещё раз:\n<code>{new_ref_link}</code>",
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Referral bonus error: {e}")


async def send_main_menu(user_id: int, bot: Bot):
    try:
        total_stars = sum_all_stars()
        total_withdrawn = sum_all_withdrawn()
        stars_str = f"{total_stars:.2f}" if isinstance(total_stars, float) else str(total_stars)
        withdrawn_str = f"{total_withdrawn:.2f}" if isinstance(total_withdrawn, float) else str(total_withdrawn)

        # 1. Сначала отправляем reply-клавиатуру с тремя кнопками
        reply_markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⭐️ Заработать звезды"), KeyboardButton(text="⭐️ Купить звезды")],
                [KeyboardButton(text="💰 Купить подписчиков")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
        await bot.send_message(
            chat_id=user_id,
            text="⭐️",
            reply_markup=reply_markup
        )

        # 2. Затем отправляем основное меню с фото (убираем кнопку "Купить подписчиков")
        builder = InlineKeyboardBuilder()
        builder.add(
            *[
                InlineKeyboardButton(text='📝 Задания', callback_data='tasks'),
                InlineKeyboardButton(text='💸 Заработать звёзды', callback_data='earn_stars'),
                InlineKeyboardButton(text='🎮 Мини-игры', callback_data='mini_games'),
                InlineKeyboardButton(text='🎁 Вывод звёзд', callback_data='withdraw_stars_menu'),
                InlineKeyboardButton(text='👤 Профиль', callback_data='my_balance'),
                InlineKeyboardButton(text='✨ Фармить звёзды', callback_data='click_star'),
                InlineKeyboardButton(text='🏆 Топ', callback_data='leaders')
            ]
        )

        if beta_url and beta_name:
            builder.add(InlineKeyboardButton(text=beta_name, url=beta_url))

        builder.adjust(1, 1, 2, 2, 1, 1)

        photo = FSInputFile("photos/start.jpg")
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=(
                "<b>✨ Добро пожаловать в главное меню ✨</b>\n\n"
                f"<b>♻️ Всего обменяли: <code>{withdrawn_str}</code>⭐️</b>\n\n"
                "<b>Как заработать звёзды?</b>\n"
                "<blockquote>🔸 Кликай, собирай ежедневные награды и вводи промокоды\n"
                "— всё это доступно в разделе «Профиль».\n"
                "🔸 Выполняй задания и приглашай друзей\n"
                "🔸 Испытай удачу в мини-играх\n"
                "— всё это доступно в главном меню.</blockquote>"
            ),
            parse_mode='HTML',
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logging.error(f"Main menu send error: {e}")


@router.message(F.text == "⭐️ Купить звезды")
@router.callback_query(lambda c: c.data == "buy_stars")
async def buy_stars_handler(update: Union[Message, CallbackQuery], bot: Bot):
    if isinstance(update, CallbackQuery):
        await update.answer()
        user_id = update.from_user.id
    else:
        user_id = update.from_user.id

    await bot.send_message(
        chat_id=user_id,
        text=(
            "<b>⭐️ В нашем боте ты можешь бесплатно заработать звезды, "
            "но если тебе лень, можешь их купить у нас дешевле чем в Телеграме!\n\n</b>"
            "👉 @stars_full_buybot\n"
            "👉 @stars_full_buybot\n"
            "👉 @stars_full_buybot"
        ),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "mailing")
async def admin_mailing_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите текст рассылки:")
    await state.set_state(AdminState.MAILING)


@router.callback_query(F.data == "add_promo_code")
async def admin_add_promo_code_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите промокод:награда:макс. пользований")
    await state.set_state(AdminState.ADD_PROMO_CODE)


@router.callback_query(F.data == "remove_promo_code")
async def admin_remove_promo_code_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите промокод:")
    await state.set_state(AdminState.REMOVE_PROMO_CODE)


@router.callback_query(F.data == "top_balance")
async def admin_top_balance_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    top_users_data = get_top_balance()
    text_balance = "<b>🏆 Топ-50 по балансу:</b>\n\n"
    for index, user_data in enumerate(top_users_data):
        username = user_data[0]
        balance = user_data[1]
        if isinstance(balance, float):
            balance_formatted = f"{balance:.2f}"
        else:
            balance_formatted = str(balance)
        text_balance += f"<b>{index + 1}. @{username}</b> - <code>{balance_formatted}</code> ⭐️\n"
    await bot.send_message(call.from_user.id, text_balance, parse_mode='HTML')


@router.message(AdminState.ADD_CHANNEL_LIMIT)
async def add_channel_limit_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        limit = int(message.text)
        if limit <= 0:
            await message.reply("<b>❌ Лимит должен быть положительным числом:</b>", parse_mode='HTML')
            return

        # Получаем сохраненные данные
        data = await state.get_data()
        channel_id = data['channel_id']
        channel_link = data['channel_link']

        # Сохраняем информацию о канале
        success = add_channel(channel_id, channel_link, limit)

        if success:
            await message.reply(
                f"<b>✅ Канал успешно добавлен!</b>\n"
                f"📋 ID: <code>{channel_id}</code>\n"
                f"🔗 Ссылка: {channel_link}\n"
                f"👥 Лимит подписчиков: {limit}\n"
                f"📊 Текущие подписчики: 0\n"
                f"🟢 Статус: Активен",
                parse_mode='HTML'
            )
        else:
            await message.reply(
                "<b>❌ Ошибка при добавлении канала в базу данных</b>",
                parse_mode='HTML'
            )

    except ValueError:
        await message.reply("<b>❌ Неверный формат лимита. Введите число:</b>", parse_mode='HTML')
        return
    finally:
        await state.clear()


async def info_added_channels_callback(call: CallbackQuery, bot: Bot):
    """Показывает список всех добавленных каналов"""
    channels_stats = get_channels_stats()

    text = "⚙️ <b>В данный момент добавлены следующие каналы:</b>\n\n"

    if not channels_stats:
        text += "<b>Нет добавленных каналов</b>\n"
    else:
        for index, channel_data in enumerate(channels_stats, start=1):
            channel_id, channel_link, limit, current, is_active, created_at, updated_at = channel_data
            status = "🟢 Активен" if is_active else "🔴 Неактивен"

            text += (
                f"<b>{index}. ID: <code>{channel_id}</code></b>\n"
                f"🔗 Ссылка: {channel_link}\n"
                f"👥 Подписчиков: {current}/{limit}\n"
                f"📈 Статус: {status}\n"
                f"📅 Создан: {created_at}\n"
                f"─────────────────\n"
            )

    await bot.send_message(call.from_user.id, text, parse_mode='HTML')


@router.callback_query(F.data == "remove_channel")
async def admin_remove_channel_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    """Начинает процесс удаления канала"""
    channels_stats = get_channels_stats()

    if not channels_stats:
        await bot.send_message(
            call.from_user.id,
            "<b>❌ Нет каналов для удаления</b>",
            parse_mode='HTML'
        )
        return

    # Показываем список каналов для удаления
    text = "<b>📋 Выберите канал для удаления:</b>\n\n"
    for index, channel_data in enumerate(channels_stats, start=1):
        channel_id, channel_link, limit, current, is_active, created_at, updated_at = channel_data
        status = "🟢 Активен" if is_active else "🔴 Неактивен"
        text += f"<b>{index}. ID: <code>{channel_id}</code> - {status}</b>\n"

    text += "\n<b>Введите ID канала для удаления:</b>"

    await bot.send_message(call.from_user.id, text, parse_mode='HTML')
    await state.set_state(AdminState.REMOVE_CHANNEL)


@router.message(AdminState.REMOVE_CHANNEL)
async def delete_channel_handler(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает удаление канала"""
    try:
        channel_id = int(message.text.strip())

        # Проверяем, существует ли канал
        channel_info = get_channel_info(channel_id)
        if not channel_info:
            await message.reply(
                "<b>❌ Канал с таким ID не найден!</b>",
                parse_mode='HTML'
            )
            return

        # Удаляем канал из базы данных
        success = delete_channel(channel_id)

        if success:
            await message.reply(
                f"<b>✅ Канал с ID <code>{channel_id}</code> успешно удален!</b>",
                parse_mode='HTML'
            )
        else:
            await message.reply(
                "<b>❌ Ошибка при удалении канала из базы данных</b>",
                parse_mode='HTML'
            )

    except ValueError:
        await message.reply(
            "<b>❌ Неверный формат ID канала. Введите числовой ID:</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка при удалении канала: {e}")
        await message.reply(
            "<b>❌ Произошла ошибка при удалении канала.</b>",
            parse_mode='HTML'
        )
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("paid"))
async def paid_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        try:
            data_parts = call.data.split(":")
            if len(data_parts) < 7:
                await call.answer("❌ Неверный формат данных", show_alert=True)
                return

            id_v = int(data_parts[1])
            mesag_id = int(data_parts[2])
            us_id = int(data_parts[3])
            us_full_name = data_parts[4]  # Получаем полное имя
            strs = int(data_parts[5])
            emoji = data_parts[6]
        except (ValueError, IndexError):
            await call.answer("❌ Ошибка при обработке данных", show_alert=True)
            return

        await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id,
                                    text=f"<b>✅ Запрос на вывод </b>\n\n👤 Пользователь: {us_full_name} | ID: {us_id}\n💫 Количество: <code>{strs}</code>⭐️ \n\n🔄 Статус: <b>Подарок отправлен 🎁</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>",
                                    parse_mode='HTML', disable_web_page_preview=True)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")


async def safe_edit_message(bot, chat_id, message_id, new_text, reply_markup=None):
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )
    except TelegramBadRequest as e:
        print("error")
        if "message is not modified" not in str(e):
            raise


@router.callback_query(F.data.startswith("denied"))
async def denied_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        try:
            data = call.data.split(":")
            if len(data) < 7:
                await call.answer("❌ Неверный формат данных", show_alert=True)
                return

            # us_full_name теперь является 5-м элементом (индекс 4)
            id_v, mesag_id, us_id, us_full_name, strs, emoji = map(str, data[1:7])
        except (ValueError, IndexError):
            await call.answer("❌ Ошибка при обработке данных", show_alert=True)
            return

        reason_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Накрутка",
                                  callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_full_name}:{strs}:{emoji}:narkutka")],
            # Передаем us_full_name
            [InlineKeyboardButton(text="🎫 Не выполнены условия вывода",
                                  callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_full_name}:{strs}:{emoji}:usloviya")],
            # Передаем us_full_name
            [InlineKeyboardButton(text="❌ Черный список",
                                  callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_full_name}:{strs}:{emoji}:black_list")],
            # Передаем us_full_name
            [InlineKeyboardButton(text="⚠️ Багаюз",
                                  callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_full_name}:{strs}:{emoji}:bagous")]
            # Передаем us_full_name
        ])

        text = (
            f"<b>✅ Запрос на вывод </b>\n\n"
            f"👤 Пользователь: {us_full_name} | ID: {us_id}\n"  # ИСПОЛЬЗУЕМ us_full_name
            f"💫 Количество: <code>{strs}</code>⭐️ \n\n"
            f"🔄 Статус: <b>Отказано 🚫</b>\n\n"
            f"<b><a href='{channel_osn}'>Основной канал</a></b> | "
            f"<b><a href='{chater}'>Чат</a></b> | "
            f"<b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>"
        )

        await safe_edit_message(bot, channel_viplat_id, int(mesag_id), text, reason_markup)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")


@router.callback_query(F.data.startswith("balk"))
async def denied_reason_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        try:
            data = call.data.split(":")
            if len(data) < 8:
                await call.answer("❌ Неверный формат данных", show_alert=True)
                return

            # us_full_name теперь является 5-м элементом (индекс 4)
            id_v, mesag_id, us_id, us_full_name, strs, emoji, reason = map(str, data[1:8])
        except (ValueError, IndexError):
            await call.answer("❌ Ошибка при обработке данных", show_alert=True)
            return

        reasons = {
            "narkutka": "🎰 Накрутка",
            "usloviya": "🎫 Отсутствует подписка на канал/чат",
            "black_list": "❌ Черный список",
            "bagous": "⚠️ Багаюз"
        }

        reason_text = reasons.get(reason, "Неизвестная причина")

        text = (
            f"<b>✅ Запрос на вывод </b>\n\n"
            f"👤 Пользователь: {us_full_name} | ID: {us_id}\n"  # ИСПОЛЬЗУЕМ us_full_name
            f"💫 Количество: <code>{strs}</code>⭐️ \n\n"
            f"🔄 Статус: <b>Отказано 🚫</b>\n"
            f"⚠️Причина: {reason_text} \u200B\n\n"
            f"<b><a href='{channel_osn}'>Основной канал</a></b> | "
            f"<b><a href='{chater}'>Чат</a></b> | "
            f"<b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>"
        )

        await safe_edit_message(bot, channel_viplat_id, int(mesag_id), text, None)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")


@router.callback_query(F.data == "donate")
async def donate_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return
    user_is_boost = user_in_booster(call.from_user.id)
    if user_is_boost:
        await bot.answer_callback_query(call.id, f"⚠️ У вас и так есть буст.")
        return
    await bot.delete_message(call.from_user.id, call.message.message_id)
    prices = [LabeledPrice(label="XTR", amount=boost_cost[0])]
    builder_donate = InlineKeyboardBuilder()
    builder_donate.button(text=f"Заплатить ⭐{boost_cost[0]}", pay=True)
    builder_donate.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_donate = builder_donate.adjust(1).as_markup()

    description = (
        "✨ Поддержи проект и получи бонусы!"
        "                                                       "
        "🌟 Множитель x2.5 к кликам на 15 дней."
        "                                                       "
        "🤝 Множитель x2 за рефералов на 15 дней."
    )
    await bot.send_invoice(call.from_user.id, title='Донат💛 ', description=description, prices=prices,
                           provider_token="", payload="channel_support", currency="XTR", reply_markup=markup_donate)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.callback_query(F.data.startswith("check_subs"))
async def check_subs_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    refferal_id = None

    try:
        if ":" in call.data:
            refferal_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        pass

    # Получаем только активные каналы из базы данных
    active_channels_data = get_active_channels()
    active_channel_ids = [row[0] for row in active_channels_data]

    if await check_subscription(user_id, active_channel_ids, bot, refferal_id=refferal_id):
        # Увеличиваем счетчик подписчиков для каждого канала
        for channel_id in active_channel_ids:
            try:
                chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if chat_member.status in ['member', 'administrator', 'creator']:
                    # Увеличиваем счетчик подписчиков в базе данных
                    is_still_active = increment_channel_subscribers(channel_id)
                    if not is_still_active:
                        logging.info(f"Канал {channel_id} деактивирован - достигнут лимит подписчиков")
            except Exception as e:
                logging.error(f"Ошибка при проверке подписки пользователя {user_id} на канал {channel_id}: {e}")

        # Логика для нового пользователя (без изменений)
        if not user_exists(user_id):
            add_user(user_id, call.from_user.username, refferal_id)

            if refferal_id is not None:
                c_refs = get_user_referrals_count(refferal_id)
                if c_refs < 50:
                    nac = nac_1[0] * 2 if user_in_booster(refferal_id) else nac_1[0]
                    increment_stars(refferal_id, nac)
                elif 50 <= c_refs < 250:
                    nac = nac_2[0] * 2 if user_in_booster(refferal_id) else nac_2[0]
                    increment_stars(refferal_id, nac)
                else:
                    nac = nac_3[0] * 2 if user_in_booster(refferal_id) else nac_3[0]
                    increment_stars(refferal_id, nac)

                increment_referrals(refferal_id)
                new_ref_link = f"https://t.me/{(await bot.me()).username}?start={refferal_id}"

                await bot.send_message(
                    refferal_id,
                    f"🎉 Пользователь <code>{user_id}</code> запустил бота по вашей ссылке!\n"
                    f"Вы получили +{nac}⭐️ за реферала.\n"
                    f"Поделитесь ссылкой ещё раз:\n<code>{new_ref_link}</code>",
                    parse_mode='HTML'
                )

        await bot.answer_callback_query(call.id, "🎉 Спасибо за подписку!")

        # ВОСТАНАВЛИВАЕМ КЛАВИАТУРНЫЕ КНОПКИ после успешной проверки
        reply_markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⭐️ Заработать звезды"), KeyboardButton(text="⭐️ Купить звезды")],
                [KeyboardButton(text="💰 Купить подписчиков")]
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )

        await bot.send_message(
            user_id,
            "<b>✅ Вы успешно подписались! Используйте кнопки ниже для навигации.</b>",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

        # Отправляем главное меню
        await send_main_menu(user_id, bot)
    else:
        await bot.answer_callback_query(call.id, "❌ Подписка не найдена")


@router.callback_query(F.data == "mini_games")
async def mini_games_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    if chat_id not in admins_id:
        if button_subgram[0] == True:
            response = await request_op(
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
    builder_games = InlineKeyboardBuilder()
    builder_games.button(text="[🔥] Кража звезд 💰", callback_data="theft_game")
    builder_games.button(text="[🔥] КНБ ✊✌️🖐", callback_data="knb_game")
    builder_games.button(text="Лотерея 🎰", callback_data="lottery_game")
    builder_games.button(text="Все или ничего 🎲", callback_data="play_game")
    builder_games.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_games = builder_games.adjust(1, 1, 2, 1).as_markup()

    with open('photos/mini_game.jpg', 'rb') as photo:
        input_photo_minigames = FSInputFile("photos/mini_game.jpg")
        await bot.send_photo(call.from_user.id, photo=input_photo_minigames,
                             caption="<b>🎮 Добро пожаловать в мини-игры!</b> Выбери игру, чтобы начать:\n\n<b>1️⃣ Испытать удачу</b> — попробуй победить с разными ставками!\n<b>2️⃣ Лотерея</b> — купи билет и выиграй много звезд!\n<b>3️⃣ КНБ</b> — камень ножницы бумага\n<b>4️⃣ Кража звёзд</b> — укради звёзды у своих друзей!",
                             reply_markup=markup_games, parse_mode='HTML')


def generate_password(length: int) -> str:
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


async def send_progress_bar(bot, chat_id, message_id):
    progress_template = ["⬜️"] * 10
    for i in range(10):
        progress_template[i] = "🟩"
        progress_bar = "".join(progress_template)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"<b>[{progress_bar}]</b>\n\n🔑 Кража в процессе...",
            parse_mode="HTML"
        )
        await asyncio.sleep(0.5)


@router.callback_query(F.data == "theft_game")
async def theft_game_starter(call: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = call.from_user.id
    balance = get_balance_user(user_id)

    if balance < 10.0:
        await bot.answer_callback_query(call.id, "❌ У вас недостаточно звёзд!\n\nДля входа в игру необходимо 10 звезд.",
                                        show_alert=True)
        return

    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    builder_theft = InlineKeyboardBuilder()
    builder_theft.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_theft = builder_theft.as_markup()

    input_photo_minigames = FSInputFile("photos/mini_game.jpg")
    await bot.send_photo(
        call.from_user.id,
        photo=input_photo_minigames,
        caption=(
            "<b>🕹 Вы вошли в мини-игру Кража звезд</b>\n\n"
            "<blockquote><b>🎮 Суть игры: </b>\n"
            "<i>После ввода Username человека, у вас начинается кража его Stars-Кошелька, "
            f"при удачной краже — вы получаете 20% баланса другого игрока</i>\n📊 Онлайн статистика краж: {channel_link}</blockquote>\n\n"
            "<blockquote><b>😊 Для начала игры введите Username человека</b></blockquote>"
        ),
        parse_mode='HTML',
        reply_markup=markup_theft
    )
    await state.set_state(TheftGame.waiting_username)


@router.message(TheftGame.waiting_username)
async def theft_game_username(message: Message, bot: Bot, state: FSMContext):
    username = message.text.lstrip('@')
    if username == message.from_user.username:
        await bot.send_message(message.from_user.id, "🚫 Вы не можете играть сам с собой.")
        await state.clear()
        return

    user_id = get_id_from_username(username)
    if user_id is None:
        await bot.send_message(message.from_user.id, "🚫 Пользователь не найден.")
        await state.clear()
        return

    balance = get_balance_user(user_id)
    if balance <= 1.0:
        await bot.send_message(message.from_user.id, "🚫 Stars-Кошелек не имеет больше 1 звезды! Кража невозможна.")
        await state.clear()
        return

    player_balance = get_balance_user(message.from_user.id)
    if player_balance >= 10:
        deincrement_stars(message.from_user.id, 10)
    else:
        await bot.send_message(message.from_user.id, "🚫 У вас недостаточно звезд!")
        await state.clear()
        return

    await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)

    sent_message = await bot.send_message(
        message.from_user.id,
        "<b>[⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️]</b>\n\n🔑 Кража начинается...",
        parse_mode="HTML"
    )

    await send_progress_bar(bot, message.from_user.id, sent_message.message_id)

    password = generate_password(random.randint(5, 10))
    success = random.random() < 0.15

    builder_theft = InlineKeyboardBuilder()
    builder_theft.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_theft = builder_theft.as_markup()

    if success:
        stolen_amount = round(balance * 0.2, 2)
        deincrement_stars(user_id, stolen_amount)
        increment_stars(message.from_user.id, stolen_amount + 10)

        await bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=sent_message.message_id,
            text=(
                f"<b>[{'🟩' * 10}]</b>\n\n"
                f"<b>✅ Кража удалась!</b>\n"
                f"<blockquote>🔑 Пароль найден: <code>{password}</code>\n"
                f"💰 Вы получили {stolen_amount} ⭐ от @{username}!</blockquote>"
            ),
            parse_mode="HTML",
            reply_markup=markup_theft
        )

        await bot.send_message(
            chat_id=user_id,
            text=(
                f"<b>😵 О нет! У вас украли звезды!</b>\n\n"
                f"<blockquote><b>💰 С вашего Stars-Кошелька списали</b> <code>{stolen_amount}</code> ⭐\n"
                f"<b>👤 Вор: @{message.from_user.username}</b></blockquote>"
            ),
            parse_mode='HTML'
        )

        await bot.send_message(
            chat_id=id_channel_game,
            text=(
                f"<b>🥷🏻Среди нас появился вор!</b>"
                f"👣 @{message.from_user.username} успешно украл {stolen_amount}💰 у @{username}!"
            ),
            parse_mode='HTML'
        )
        await state.clear()
    else:
        await bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=sent_message.message_id,
            text=(
                f"<b>[{'🟩' * 10}]</b>\n\n"
                f"❌ Кража не удалась! Пароль не найден.\n"
                f"🔑 Последний найденный пароль: <code>{password}</code>"
            ),
            parse_mode="HTML",
            reply_markup=markup_theft
        )
        await state.clear()


@router.callback_query(F.data == "knb_game")
async def knb_game_starter(call: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы!", show_alert=True)
        return
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    builder_knb = InlineKeyboardBuilder()
    builder_knb.button(text="Назад в меню мини-иг", callback_data="mini_games")
    markup_knb = builder_knb.as_markup()
    input_photo_minigames = FSInputFile("photos/mini_game.jpg")
    await bot.send_photo(call.from_user.id, photo=input_photo_minigames,
                         caption="<b>🕹 Вы вошли в мини-игру КНБ!</b>\n\n<blockquote><b>🎮 Суть игры: </b>\n<i>После ввода Username человека, ставки — вам первым дают на выбор 3 действия: Камень, Ножницы, Бумага. После вашего выбора — выбор переходит к сопернику и система анализирует победителя в игре.</i></blockquote>\n\n<blockquote><b>😊 Для начала игры введите Username человека</b></blockquote>\n\n<blockquote><b>‼️ Передача звезд между аккаунтами - ЧС</b></blockquote>",
                         reply_markup=markup_knb, parse_mode='HTML')
    await state.set_state(KNBGame.waiting_username)


@router.message(KNBGame.waiting_username)
async def knb_game_username(message: Message, bot: Bot, state: FSMContext):
    username = message.text
    balance = get_balance_user(message.from_user.id)
    if balance <= 0:
        await bot.send_message(message.from_user.id, "🚫 У вас баланс меньше или равно 0.")
    if username.startswith('@'):
        username = username[1:]
    if username == (message.from_user.username):
        await bot.send_message(message.from_user.id, "🚫 Вы не можете играть сам с собой.")
        return
    user_id = get_id_from_username(username)
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.send_message(message.from_user.id, "🚫 Пользователь заблокирован.")
        return
    if user_id is None:
        await bot.send_message(message.from_user.id, "🚫 Пользователь не найден.")
        return
    await state.update_data(username=username)
    await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    builder_knb = InlineKeyboardBuilder()
    builder_knb.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_knb = builder_knb.as_markup()
    input_photo_minigames = FSInputFile("photos/mini_game.jpg")
    await bot.send_photo(message.from_user.id, photo=input_photo_minigames,
                         caption=f"<b>🕹 Вы вошли в мини-игру КНБ!</b>\n\n<blockquote><b>👤 Выбран игрок: <code>{username}</code> | <code>{user_id}</code></b></blockquote>\n\n<blockquote><b>💰 Введите ставку:</b></blockquote>",
                         reply_markup=markup_knb, parse_mode='HTML')
    await state.set_state(KNBGame.waiting_stake)


@router.message(KNBGame.waiting_stake)
async def knb_game_stake(message: Message, bot: Bot, state: FSMContext):
    try:
        stake = float(message.text)
        balance_user1 = get_balance_user(message.from_user.id)
        username = await state.get_data()
        username = username['username']
        user_id = get_id_from_username(username)
        balance_user2 = get_balance_user(user_id)
        if balance_user1 < stake:
            await bot.send_message(message.from_user.id, "🚫 У вас недостаточно звезд.")
            return
        elif balance_user2 < stake:
            await bot.send_message(message.from_user.id, "🚫 У игрока недостаточно звезд.")
            return
        elif stake < 0:
            await bot.send_message(message.from_user.id, "🚫 Ставка не может быть отрицательной.")
    except ValueError:
        await bot.send_message(message.from_user.id, "🚫 Пожалуйста, введите число.")
        return
    await state.update_data(stake=stake)
    await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    id = create_knb(message.from_user.id, user_id, bet=stake)
    input_photo_minigames = FSInputFile("photos/mini_game.jpg")
    await bot.send_photo(message.from_user.id, photo=input_photo_minigames,
                         caption=f"<b>🕹 Вы вошли в мини-игру КНБ!</b>\n\n<blockquote><b>👤 Выбран игрок: <code>{username}</code> | <code>{user_id}</code>\n💰 Ставка: <code>{stake}</code></b></blockquote>\n\n<i>Ожидайте, пока пользователь примет игру.</i>",
                         parse_mode='HTML')
    player_builder = InlineKeyboardBuilder()
    player_builder.button(text="✅ Принять игру", callback_data=f"accept_knb:{id}:{stake}:{message.from_user.id}")
    player_builder.button(text="❌ Отказаться", callback_data=f"decline_knb:{id}:{message.from_user.id}")
    player_markup = player_builder.adjust(1, 1).as_markup()
    await bot.send_message(user_id,
                           f"🕹 Вас пригласили в мини-игру КНБ!\n\n<blockquote><b>🆔 Игры: {id}\n👤 Пригласил игрок: <code>{message.from_user.first_name}</code> | <code>{message.from_user.id}</code>\n💰 Ставка: <code>{stake}</code></b></blockquote>",
                           parse_mode='HTML', reply_markup=player_markup)


@router.callback_query(F.data.startswith("accept_knb:"))
async def accept_knb_callback(call: CallbackQuery, bot: Bot):
    try:
        data_parts = call.data.split(':')
        if len(data_parts) < 4:
            await call.answer("❌ Неверный формат данных", show_alert=True)
            return

        id_game = data_parts[1]
        stake = float(data_parts[2])
        use_id = int(data_parts[3])
    except (ValueError, IndexError):
        await call.answer("❌ Ошибка при обработке данных", show_alert=True)
        return

    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "✅ Вы приняли игру.")
    await bot.send_message(call.from_user.id, "⌛️ Ожидайте, пока пользователь сделает свой ход.")

    deincrement_stars(use_id, stake)
    deincrement_stars(call.from_user.id, stake)
    markup_choice = InlineKeyboardBuilder()
    markup_choice.button(text="[✊] Камень", callback_data=f"stone_knb:{id_game}:first_player")
    markup_choice.button(text="[✌️] Ножницы", callback_data=f"scissors_knb:{id_game}:first_player")
    markup_choice.button(text="[✋] Бумага", callback_data=f"paper_knb:{id_game}:first_player")
    markup = markup_choice.adjust(3).as_markup()
    await bot.send_message(
        use_id,
        f"<b>✅ Пользователь {call.from_user.first_name} принял игру.</b>\n\n<blockquote><b>💰 Ставка: {stake}</b></blockquote>",
        parse_mode='HTML', reply_markup=markup
    )


@router.callback_query(F.data.split(":")[2] == "first_player")
async def handle_first_player_choice(call: CallbackQuery, bot: Bot):
    data_parts = call.data.split(":")
    choice_type = data_parts[0].split("_")[0]
    game_id = data_parts[1]

    change_choice(game_id, "first_player", choice_type)

    game = get_knb_game(game_id)
    second_player_id = game[2]
    stake = game[6]

    markup_choice = InlineKeyboardBuilder()
    markup_choice.button(text="✊ Камень", callback_data=f"stone_knb:{game_id}:second_player")
    markup_choice.button(text="✌️ Ножницы", callback_data=f"scissors_knb:{game_id}:second_player")
    markup_choice.button(text="✋ Бумага", callback_data=f"paper_knb:{game_id}:second_player")
    markup = markup_choice.adjust(3).as_markup()
    await bot.send_message(
        second_player_id,
        f"<b>🎲 Ваш ход в игре против {call.from_user.first_name}</b>\n\n"
        f"<blockquote><b>💰 Ставка:</b> <code>{stake}</code></blockquote>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "✅ Вы выбрали свой ход.")


@router.callback_query(F.data.split(":")[2] == "second_player")
async def handle_second_player_choice(call: CallbackQuery, bot: Bot):
    data_parts = call.data.split(":")
    choice_type = data_parts[0].split("_")[0]
    game_id = data_parts[1]

    change_choice(game_id, "second_player", choice_type)

    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "✅ Вы выбрали свой ход.")
    winner_text = ""

    game = get_knb_game(game_id)
    first_player_id = game[1]
    second_player_id = game[2]
    choice_1 = game[3]
    choice_2 = game[4]
    stake = game[6]
    result = set_result(game_id, choice_1, choice_2)

    # Получаем объекты чатов для обоих игроков, чтобы получить их full_name
    first_player_chat = await bot.get_chat(first_player_id)
    second_player_chat = await bot.get_chat(second_player_id)

    if result == "Ничья":
        winner_text = "Ничья! 🟰"
        increment_stars(first_player_id, stake)
        increment_stars(second_player_id, stake)
    else:
        winner_id = first_player_id if result == "Первый игрок победил!" else second_player_id
        winner_chat = await bot.get_chat(winner_id)
        # ИСПОЛЬЗУЕМ full_name победителя
        winner_text = f"Победу одержал {winner_chat.full_name}"

    if choice_1 == "stone":
        choice_1 = "[✊] Камень"
    elif choice_1 == "scissors":
        choice_1 = "[✌️] Ножницы"
    elif choice_1 == "paper":
        choice_1 = "[✋] Бумага"

    if choice_2 == "stone":
        choice_2 = "[✊] Камень"
    elif choice_2 == "scissors":
        choice_2 = "[✌️] Ножницы"
    elif choice_2 == "paper":
        choice_2 = "[✋] Бумага"

    for player_id in [first_player_id, second_player_id]:
        builder_knb = InlineKeyboardBuilder()
        builder_knb.button(text="Назад в меню мини-игр", callback_data="mini_games")
        markup_knb = builder_knb.as_markup()

        await bot.send_message(
            player_id,
            f"<b>🎉 Игра завершена!</b>\n"
            f"<blockquote>➖➖➖➖➖➖➖\n"
            f"<b>👤 Игрок 1 ({first_player_chat.full_name}): {choice_1}\n"  # Ссылка удалена
            f"👤 Игрок 2 ({second_player_chat.full_name}): {choice_2}</b>\n"  # Ссылка удалена
            f"➖➖➖➖➖➖➖\n"
            f"<b>🏆 Результат игры: {winner_text}</b>\n"
            f"<b>💰 Ставка: <code>{stake}</code></b></blockquote>",
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=markup_knb
        )
    await bot.send_message(
        id_channel_game,
        f"<b>🎉 Игра завершена!</b>\n"
        f"<blockquote>➖➖➖➖➖➖➖\n"
        f"<b>👤 Игрок 1 ({first_player_chat.full_name}): {choice_1}\n"  # Ссылка удалена
        f"👤 Игрок 2 ({second_player_chat.full_name}): {choice_2}</b>\n"  # Ссылка удалена
        f"➖➖➖➖➖➖➖\n"
        f"<b>🏆 Результат игры: {winner_text}</b>\n"
        f"<b>💰 Ставка: <code>{stake}</code></b></blockquote>",
        parse_mode='HTML',
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("decline_knb:"))
async def decline_knb_callback(call: CallbackQuery, bot: Bot):
    try:
        data_parts = call.data.split(':')
        if len(data_parts) < 3:
            await call.answer("❌ Неверный формат данных", show_alert=True)
            return

        id_game = data_parts[1]
        use_id = int(data_parts[2])
    except (ValueError, IndexError):
        await call.answer("❌ Ошибка при обработке данных", show_alert=True)
        return

    delete_knb(id_game)
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "🚫 Вы отказались от игры.")
    await bot.send_message(use_id, "❌ Пользователь отказался от игры.")


@router.callback_query(F.data == "lottery_game")
async def lottery_game_callback(call: CallbackQuery, bot: Bot):
    lot_id = get_id_lottery_enabled()
    if lot_id != "Нет.":
        count_tickets_user = get_count_tickets_by_user(lot_id, call.from_user.id)
        if count_tickets_user > 0:
            await bot.answer_callback_query(call.id, "🎉 Вы уже купили билет в данную лотерею.")
            return
        all_cash = get_cash_in_lottery()
        # money_user = get_balance_user(call.from_user.id)
        ticket_cash = get_ticket_cash_in_lottery()
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
        lottery_game = InlineKeyboardBuilder()
        lottery_game.button(text="🎫 Купить билет", callback_data=f"buy_ticket:{lot_id}:{ticket_cash}")
        lottery_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
        markup_lottery_game = lottery_game.adjust(1, 1).as_markup()
        await bot.send_message(call.from_user.id,
                               f"<b>🎉 Вы вошли в лотерею №{lot_id}\n\n💰 Текущий джекпот: {all_cash}\n💵 Стоимость одного билета: {ticket_cash}</b>",
                               parse_mode='HTML', reply_markup=markup_lottery_game)
    else:
        await bot.answer_callback_query(call.id, "😇 В данный момент лотерея не проводится.")


@router.callback_query(F.data.startswith("buy_ticket:"))
async def buy_ticket_callback(call: CallbackQuery, bot: Bot):
    try:
        data_parts = call.data.split(':')
        if len(data_parts) < 3:
            await call.answer("❌ Неверный формат данных", show_alert=True)
            return

        lot_id = data_parts[1]
        ticket_cash = float(data_parts[2])
    except (ValueError, IndexError):
        await call.answer("❌ Ошибка при обработке данных", show_alert=True)
        return

    count_tickets_user = get_count_tickets_by_user(lot_id, call.from_user.id)
    if count_tickets_user > 0:
        await bot.answer_callback_query(call.id, "🎉 Вы уже купили билет в данную лотерею.")
        return

    money_user = get_balance_user(call.from_user.id)
    if ticket_cash > money_user:
        await bot.answer_callback_query(call.id, "❌ У вас недостаточно звезд.")
        return
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    add_lottery_entry(lot_id, call.from_user.id, call.from_user.username, ticket_cash)
    deincrement_stars(call.from_user.id, ticket_cash)
    lottery_back = InlineKeyboardBuilder()
    lottery_back.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_lottery_back = lottery_back.adjust(1).as_markup()
    await bot.send_message(call.from_user.id, f"<b>🎫 Вы купили билет в лотерею №{lot_id}</b>", parse_mode='HTML',
                           reply_markup=markup_lottery_back)


@router.callback_query(F.data == "play_game")
async def play_game_callback(call: CallbackQuery, bot: Bot):
    builder_game = InlineKeyboardBuilder()
    builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
    builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
    builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
    builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
    builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
    builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
    builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_game = builder_game.adjust(3, 3, 1).as_markup()

    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    try:
        balance = get_balance_user(call.from_user.id)
        with open('photos/mini_game.jpg', 'rb') as photo:
            input_photo_playgame = FSInputFile("photos/mini_game.jpg")
            await bot.send_photo(call.from_user.id, photo=input_photo_playgame,
                                 caption=f"<b>💰 У тебя на счету:</b> {balance} ⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}",
                                 parse_mode='HTML', reply_markup=markup_game)
    except Exception as e:
        logging.error(f"Ошибка при получении баланса: {e}")
        await bot.send_message(call.from_user.id,
                               f"<b>⚠️ Ошибка при получении баланса.</b>\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}",
                               parse_mode='HTML', reply_markup=markup_game)


@router.callback_query(F.data == "giftday")
async def giftday_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    try:
        # Сначала проверяем, есть ли реферальная ссылка в профиле пользователя
        ref_link_check = await check_user_profile_for_referral_link(call.from_user, bot)

        if not ref_link_check:
            await bot.answer_callback_query(
                call.id,
                "❌ Сначала поставь свою личную ссылку в описание профиля или измени настройки конфиденциальности в разделе ""о себе"". Проверка занимает до 2 минут ",
                show_alert=True
            )
            return

        # Проверяем время последнего получения подарка
        last_claim_time = get_last_daily_gift_time(user_id)
        current_time = time.time()
        if last_claim_time and (current_time - last_claim_time) < DAILY_COOLDOWN:
            remaining_time = int(DAILY_COOLDOWN - (current_time - last_claim_time))
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            seconds = remaining_time % 60
            await bot.answer_callback_query(call.id,
                                            f"⌛️ Подождите еще {hours} часов, {minutes} минут(ы), {seconds} секунд(ы) перед следующим подарком",
                                            show_alert=True)
        else:
            increment_stars(user_id, GIFT_AMOUNT[0])
            update_last_daily_gift_time(user_id)
            await bot.answer_callback_query(call.id, f"🎉 Вы получили ежедневный подарок в размере {GIFT_AMOUNT[0]}⭐️",
                                            show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка при обработке ежедневного подарка: {e}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при получении ежедневного подарка.",
                                        show_alert=True)


async def check_user_profile_for_referral_link(user, bot: Bot) -> bool:
    """
    Проверяет, содержит ли профиль пользователя его реферальную ссылку
    """
    try:
        # Получаем информацию о пользователе
        chat_info = await bot.get_chat(user.id)

        # Создаем ожидаемую реферальную ссылку
        bot_username = (await bot.me()).username
        expected_ref_link = f"https://t.me/{bot_username}?start={user.id}"
        alternative_ref_link = f"t.me/{bot_username}?start={user.id}"

        # Проверяем описание профиля (bio)
        if hasattr(chat_info, 'bio') and chat_info.bio:
            bio = chat_info.bio.lower()
            logging.info(f"Проверяем bio пользователя {user.id}: {chat_info.bio}")
            if expected_ref_link.lower() in bio or alternative_ref_link.lower() in bio:
                return True
            # Также проверяем наличие ID пользователя в ссылке
            if f"?start={user.id}" in bio and bot_username.lower() in bio:
                return True
        else:
            logging.info(f"У пользователя {user.id} нет bio или bio пустое")

        return False

    except TelegramBadRequest as e:
        if "chat not found" in str(e).lower():
            logging.info(f"Не удалось получить информацию о пользователе {user.id} - приватный профиль")
            # Если профиль приватный, пропускаем проверку
            return True
        logging.error(f"TelegramBadRequest при проверке профиля пользователя {user.id}: {e}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при проверке профиля пользователя {user.id}: {e}")
        # Если не можем проверить профиль (приватные настройки), считаем что проверка пройдена
        return True


@router.callback_query(F.data == "leaders")
async def leaders_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    if user_id not in admins_id:
        if button_subgram[0] == True:
            response = await request_op(
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

    await show_leaderboard(call.message, 'day', bot)


@router.callback_query(F.data == "week")
async def week_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return
    await show_leaderboard(call.message, 'week', bot)


@router.callback_query(F.data == "month")
async def month_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return
    await show_leaderboard(call.message, 'month', bot)


def extract_chat_info(link: str) -> str:
    parts = link.strip().split("/")
    identifier = parts[-1]
    if identifier.startswith("+"):
        return identifier

    return f"@{identifier}"


async def get_flyer_tasks(key: str, user_id: int, limit: int = 10):
    url = "https://api.flyerservice.io/get_tasks"
    headers = {"Content-Type": "application/json"}
    payload = {"key": key, "user_id": user_id, "limit": limit}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if not response.ok:
                    logging.error(f"Ошибка запроса: статус {response.status}")
                    return None

                data = await response.json()
                if 'result' not in data or not data['result']:
                    logging.error("Ответ не содержит заданий")
                    return None

                return data['result']
    except Exception as e:
        logging.exception("Ошибка при получении заданий Flyer:", e)
        return None


async def check_flyer_task(key: str, user_id: int, signature: str):
    url = "https://api.flyerservice.io/check_task"
    headers = {"Content-Type": "application/json"}
    payload = {"key": key, "user_id": user_id, "signature": signature}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if not response.ok:
                    logging.error(f"Ошибка запроса проверки заданий Flyer, статус: {response.status}")
                    return None

                data = await response.json()

                if 'result' not in data or not data['result']:
                    logging.error("Ответ не содержит result")
                    return None

                result = data.get('result')

                return result

    except Exception as e:
        logging.exception("Ошибка проверки заданий Flyer: ", e)
        return None


def hash_flyer_task(signature, user_id):
    hash_object = hashlib.sha256(f"{signature}_{user_id}".encode())
    return hash_object.hexdigest()


@router.callback_query(F.data == 'tasks_menu')
async def tasks_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить задание", callback_data='add_task')
    builder.button(text="📋 Список заданий", callback_data='list_tasks')
    builder.button(text="❌ Удалить задание", callback_data='remove_task')
    builder.button(text="⬅️ Назад", callback_data='adminpanelka')  # Кнопка для возврата в главное меню админ-панели
    markup = builder.adjust(1, 1, 1, 1).as_markup()
    await callback.message.edit_text(
        "<b>✅ Управление заданиями:</b>",
        parse_mode='HTML',
        reply_markup=markup
    )
    await callback.answer()


async def send_tasks_menu(user_id: int, bot: Bot, first_name: str, language_code: str):
    """
    Отправляет меню с заданиями пользователю.
    """
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    try:
        # Сразу проверяем задания от Flyer
        tasks_list = await get_flyer_tasks(FLYER_KEY, user_id, limit=10)
        selected_task = None

        if tasks_list:
            for task in tasks_list:
                link = task.get('link')
                signature = task.get('signature')
                if not link or not signature:
                    continue

                task_hash = hash_flyer_task(signature, user_id)
                if not is_flyer_task_completed(task_hash) and not is_flyer_task_skipped(task_hash, user_id):
                    selected_task = task
                    break

        if selected_task:
            # Показываем задание от Flyer
            link = selected_task.get('link')
            signature = selected_task.get('signature')
            task_text = (
                f'<b>✨ Следующее задание! ✨\n\n'
                f'• Подпишитесь на каналы, указанные ниже.\n\n'
                f'Награда: {task_grant[0]} ⭐️</b>\n\n'
                f'📌 Чтобы получить награду полностью, подпишитесь и не отписывайтесь от канала/группы в течение 3-х дней. '
                f'Нажмите "Проверить подписку", чтобы подтвердить!'
            )

            markup_flyer = InlineKeyboardBuilder()
            markup_flyer.button(text="✅ Подписаться на канал", url=link)
            markup_flyer.button(text="🔎 Проверить подписку", callback_data=f'flyer_check:{signature}')
            markup_flyer.button(text="⬅️ В главное меню", callback_data="back_main")
            markup_flyer.button(text="➡️ Пропустить", callback_data=f'skip_flyer_task:{signature}')
            markup_flyer = markup_flyer.adjust(1, 1, 2).as_markup()

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(
                    user_id,
                    photo=photo,
                    caption=task_text,
                    parse_mode='HTML',
                    reply_markup=markup_flyer
                )
            except:
                msg = await bot.send_message(
                    user_id,
                    task_text,
                    parse_mode='HTML',
                    reply_markup=markup_flyer
                )

            # Сохраняем ID нового сообщения
            user_task_messages[user_id] = msg.message_id
            return

        # Пользовательские задания (остается без изменений)
        user_task = await get_next_user_task(user_id)
        if user_task:
            task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = user_task

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Подписаться на канал", url=channel_link)
            builder.button(text="🔎 Проверить подписку", callback_data=f"check_user_task:{task_id}")
            builder.button(text="⬅️ В главное меню", callback_data="back_main")
            builder.button(text="➡️ Пропустить", callback_data=f"skip_user_task:{task_id}")
            markup = builder.adjust(1, 1, 2).as_markup()

            reward = task_grant[0]

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(
                    user_id,
                    photo=photo,
                    caption=f"<b>✨ Следующее задание! ✨</b>\n\n"
                            f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                            f"Награда: {reward} ⭐️\n\n"
                            f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней. Нажмите «Проверить подписку» 👇",
                    parse_mode='HTML',
                    reply_markup=markup
                )
            except:
                msg = await bot.send_message(
                    user_id,
                    f"<b>✨ Следующее задание! ✨</b>\n\n"
                    f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                    f"Награда: {reward} ⭐️\n\n"
                    f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней. Нажмите «Проверить подписку» 👇",
                    parse_mode='HTML',
                    reply_markup=markup
                )

            # Сохраняем ID нового сообщения
            user_task_messages[user_id] = msg.message_id
            return

        # Нет заданий — показываем финальное сообщение
        await bot.send_message(
            user_id,
            "<b>🎉 Отлично! Вы выполнили все доступные задания!\n\n"
            "🎯 Возвращайтесь позже за новыми заданиями!</b>",
            parse_mode='HTML',
            reply_markup=markup_back
        )

    except Exception as e:
        logging.error(f"Ошибка при показе следующего задания: {e}")
        await bot.send_message(
            user_id,
            "<b>⚠️ Ошибка при получении следующего задания.</b>",
            parse_mode='HTML',
            reply_markup=markup_back
        )


# Админские функции для управления рекламным балансом
@router.callback_query(F.data == "admin_ad_balance")
async def admin_ad_balance_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Выдать рекламный баланс", callback_data="give_ad_balance")
    builder.button(text="🎁 Выдать всем пользователям", callback_data="mass_give_ad_balance")
    builder.button(text="📊 Активные задания пользователей", callback_data="view_user_tasks")
    builder.button(text="⬅️ Назад", callback_data="admin_task_management")
    markup = builder.adjust(1, 1, 1, 1).as_markup()

    await bot.send_message(
        call.from_user.id,
        "<b>💼 Управление рекламным балансом</b>",
        parse_mode='HTML',
        reply_markup=markup
    )


@router.callback_query(F.data == "give_ad_balance")
async def give_ad_balance_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(
        call.from_user.id,
        "Введите ID пользователя и сумму в формате: ID:СУММА\n"
        "Пример: 123456:100"
    )
    await state.set_state(AdminState.ADD_AD_BALANCE)


@router.callback_query(F.data == "mass_give_ad_balance")
async def mass_give_ad_balance_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(
        call.from_user.id,
        "Введите сумму для выдачи всем пользователям:"
    )
    await state.set_state(AdminState.MASS_AD_BALANCE)


async def mass_ad_balance_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.reply("❌ Сумма должна быть больше 0")
            return
    except ValueError:
        await message.reply("❌ Введите числовое значение")
        return

    # Получаем всех пользователей
    all_users = get_users_ids()
    total_users = len(all_users)

    if total_users == 0:
        await message.reply("❌ Нет пользователей в базе данных")
        await state.clear()
        return

    # Отправляем сообщение с прогрессом
    progress_message = await message.reply(
        f"🔄 <b>Выдача рекламного баланса</b>\n\n"
        f"💰 Сумма: {amount:.2f} ⭐️\n"
        f"👥 Пользователей: {total_users}\n"
        f"📊 Прогресс: 0/{total_users} (0%)\n"
        f"⏳ Обработано: 0",
        parse_mode='HTML'
    )

    processed = 0
    success_count = 0

    for user_id_tuple in all_users:
        user_id = user_id_tuple[0]
        try:
            update_ad_balance(user_id, amount)
            success_count += 1

            # Уведомляем пользователя
            try:
                await bot.send_message(
                    user_id,
                    f"🎁 <b>Администратор выдал вам рекламный баланс!</b>\n\n"
                    f"💼 Зачислено: {amount:.2f} ⭐️",
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Не удалось уведомить пользователя {user_id}: {e}")

        except Exception as e:
            logging.error(f"Ошибка при выдаче баланса пользователю {user_id}: {e}")

        processed += 1

        # Обновляем прогресс каждые 10 пользователей или в конце
        if processed % 10 == 0 or processed == total_users:
            progress_percent = (processed / total_users) * 100
            try:
                await progress_message.edit_text(
                    f"🔄 <b>Выдача рекламного баланса</b>\n\n"
                    f"💰 Сумма: {amount:.2f} ⭐️\n"
                    f"👥 Пользователей: {total_users}\n"
                    f"📊 Прогресс: {processed}/{total_users} ({progress_percent:.1f}%)\n"
                    f"✅ Успешно: {success_count}",
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Ошибка обновления прогресса: {e}")

        # Небольшая задержка чтобы не перегружать API
        if processed % 20 == 0:
            await asyncio.sleep(1)

    # Финальное сообщение
    await progress_message.edit_text(
        f"✅ <b>Выдача завершена!</b>\n\n"
        f"💰 Сумма: {amount:.2f} ⭐️\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Успешно обработано: {success_count}\n"
        f"❌ Ошибок: {total_users - success_count}",
        parse_mode='HTML'
    )

    await state.clear()


@router.message(AdminState.ADD_AD_BALANCE)
async def add_ad_balance_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        user_id, amount = message.text.split(':')
        user_id = int(user_id)
        amount = float(amount)

        update_ad_balance(user_id, amount)

        await message.reply(
            f"✅ Выдано {amount:.2f} ⭐️ на рекламный баланс пользователю {user_id}"
        )

        # Уведомляем пользователя
        await bot.send_message(
            user_id,
            f"🎁 <b>Администратор выдал вам рекламный баланс!</b>\n\n"
            f"💼 Зачислено: {amount:.2f} ⭐️",
            parse_mode='HTML'
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")
    finally:
        await state.clear()


@router.callback_query(F.data == "view_user_tasks")
async def view_user_tasks_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        await call.answer("❌ Нет доступа")
        return

    # Показываем все задания (активные, ожидающие, отклоненные)
    all_tasks = get_all_user_tasks_for_admin()

    if not all_tasks:
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="admin_ad_balance")
        markup = builder.as_markup()

        await bot.send_message(
            call.from_user.id,
            "📋 <b>Нет пользовательских заданий</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
        return

    text = "<b>📊 Все пользовательские задания:</b>\n\n"

    for task in all_tasks:
        task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers, status = task
        progress = (current_subscribers / target_subscribers) * 100 if target_subscribers > 0 else 0

        status_emoji = {
            'pending': '🟡',
            'active': '🟢',
            'completed': '🔵',
            'rejected': '🔴'
        }.get(status, '❓')

        status_text = {
            'pending': 'Ожидает модерации',
            'active': 'Активно',
            'completed': 'Завершено',
            'rejected': 'Отклонено'
        }.get(status, 'Неизвестно')

        text += (
            f"{status_emoji} <b>Задание #{task_id}</b>\n"
            f"👤 Создатель: {creator_id}\n"
            f"📊 Статус: {status_text}\n"
            f"📊 Прогресс: {current_subscribers}/{target_subscribers} ({progress:.1f}%)\n"
            f"🔗 Канал: {channel_link}\n"
            "─────────────\n"
        )

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin_ad_balance")
    markup = builder.as_markup()

    await bot.send_message(call.from_user.id, text, parse_mode='HTML', reply_markup=markup)


@router.callback_query(F.data.startswith("skip_flyer_task"))
async def skip_task_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return

    try:
        signature = call.data.split(":")[1]
    except IndexError:
        await bot.answer_callback_query(call.id, "❌ Ошибка при обработке данных", show_alert=True)
        return

    task_hash = hash_flyer_task(signature=signature, user_id=user_id)

    # Помечаем задание как пропущенное
    add_skipped_flyer_task(task_hash, user_id)

    await bot.answer_callback_query(call.id, "Задание пропущено. Ищем следующее...", show_alert=False)

    # Удаляем текущее сообщение с заданием перед показом следующего
    try:
        await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
    except TelegramBadRequest as e:
        if "message to delete not found" not in str(e).lower():
            logging.error(f"Ошибка при удалении пропущенного flyer задания: {e}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка при удалении пропущенного flyer задания: {e}")

    # Показываем следующее задание
    await show_next_task(call, bot)


@router.callback_query(F.data.startswith("flyer_check"))
async def flyer_check_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return

    try:
        signature = call.data.split(":")[1]
    except IndexError:
        await bot.answer_callback_query(call.id, "❌ Ошибка при обработке данных", show_alert=True)
        return

    task_hash = hash_flyer_task(signature=signature, user_id=user_id)

    if is_flyer_task_completed(task_hash):
        await bot.answer_callback_query(call.id, "🎯 Задание уже выполнено!", show_alert=True)
        return

    resultat = await check_flyer_task(FLYER_KEY, call.from_user.id, signature=signature)

    if resultat == "complete" or resultat == "waiting":
        await bot.answer_callback_query(call.id, "✅ Спасибо за подписку!", show_alert=True)
        increment_stars(call.from_user.id, task_grant[0])
        add_flyer_task(task_hash)
        add_completed_task(call.from_user.id)

        # Удаляем текущее сообщение с заданием перед показом следующего
        try:
            await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
        except TelegramBadRequest as e:
            if "message to delete not found" not in str(e).lower():
                logging.error(f"Ошибка при удалении сообщения с flyer заданием: {e}")
        except Exception as e:
            logging.error(f"Неожиданная ошибка при удалении сообщения с flyer заданием: {e}")

        # Показываем следующее задание
        await show_next_task(call, bot)
        return
    else:
        await bot.answer_callback_query(call.id, "❌ Задание не выполнено!", show_alert=True)


@router.callback_query(F.data == "withdraw_stars_menu")
async def withdraw_stars_menu_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    if user_id not in admins_id:
        if button_subgram[0] == True:
            response = await request_op(
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

    builder_stars = InlineKeyboardBuilder()
    builder_stars.button(text="15 ⭐️(🧸)", callback_data="withdraw:15:🧸")
    builder_stars.button(text="15 ⭐️(💝)", callback_data="withdraw:15:💝")
    builder_stars.button(text="25 ⭐️(🌹)", callback_data="withdraw:25:🌹")
    builder_stars.button(text="25 ⭐️(🎁)", callback_data="withdraw:25:🎁")
    builder_stars.button(text="50 ⭐️(🍾)", callback_data="withdraw:50:🍾")
    builder_stars.button(text="50 ⭐️(🚀)", callback_data="withdraw:50:🚀")
    builder_stars.button(text="50 ⭐️(💐)", callback_data="withdraw:50:💐")
    builder_stars.button(text="50 ⭐️(🎂)", callback_data="withdraw:50:🎂")
    builder_stars.button(text="100 ⭐️(🏆)", callback_data="withdraw:100:🏆")
    builder_stars.button(text="100 ⭐️(💍)", callback_data="withdraw:100:💍")
    builder_stars.button(text="100 ⭐️(💎)", callback_data="withdraw:100:💎")
    builder_stars.button(text="Telegram Premium 1мес. (400 ⭐️)", callback_data="withdraw:premium1")
    builder_stars.button(text="Telegram Premium 3мес. (1100 ⭐️)", callback_data="withdraw:premium2")
    builder_stars.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_stars = builder_stars.adjust(2, 2, 2, 2, 2, 1, 1, 1).as_markup()

    try:
        balance = str(get_balance_user(call.from_user.id))
        with open('photos/withdraw_stars.jpg', 'rb') as photo:
            input_photo_withdraw = FSInputFile("photos/withdraw_stars.jpg")
            await bot.send_photo(call.from_user.id, photo=input_photo_withdraw,
                                 caption=f'<b>🔸 У тебя на счету: {balance[:balance.find(".") + 2]}⭐️</b>\n\n<b>❗️ Важно!</b> Для получения выплаты (подарка) нужно быть подписанным на:\n<a href="{channel_osn}">Основной канал</a> | <a href="{chater}">Чат</a> | <a href="{channel_viplat}">Канал выплат</a>\n\n<blockquote>‼️ Если не будет подписки в момент отправки подарка - выплата будет удалена, звёзды не возвращаются!</blockquote>\n\n<b>Выбери количество звёзд, которое хочешь обменять, из доступных вариантов ниже:</b>',
                                 parse_mode='HTML', reply_markup=markup_stars)
    except Exception as e:
        logging.error(f"Ошибка при отображении меню вывода: {e}")
        await bot.send_message(call.from_user.id, "<b>⚠️ Ошибка при отображении меню вывода.</b>", parse_mode='HTML',
                               reply_markup=markup_stars)


@router.callback_query(F.data == "my_balance")
async def my_balance_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    if user_id not in admins_id:
        if button_subgram[0] == True:
            response = await request_op(
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
    builder_profile = InlineKeyboardBuilder()
    builder_profile.button(text='🎁 Ежедневка', callback_data='giftday')
    builder_profile.button(text="🎫 Промокод", callback_data="promocode")
    builder_profile.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_profile = builder_profile.adjust(2, 1).as_markup()

    # Экранирование с помощью стандартной библиотеки
    nickname = html.escape(call.from_user.first_name)
    user_id = html.escape(str(call.from_user.id))

    try:
        balance = float(get_balance_user(call.from_user.id))
        count_refs = get_user_referrals_count(call.from_user.id)

        with open('photos/profile.jpg', 'rb') as photo:
            input_photo_profile = FSInputFile("photos/profile.jpg")
            if user_in_booster(call.from_user.id):
                time_until = get_time_until_boost(call.from_user.id)
                time_until_str = html.escape(datetime.fromtimestamp(time_until).strftime("%d"))
                caption = (
                    f"<b>✨ Профиль\n──────────────\n👤 Имя: {nickname}\n🆔 ID: <code>{user_id}</code>\n"
                    f"──────────────\n💰 Баланс:</b> {html.escape(f'{balance:.2f}')}⭐️\n"
                    f"<b>👥 Рефералов:</b> {html.escape(str(count_refs))}\n"
                    f"<b>──────────────</b>\n<b>⏳ Дней до окончания буста</b>: {time_until_str}\n"
                    f"<b>──────────────</b>\n⬇️ <i>Используй кнопки ниже для действий.</i>"
                )
                await bot.send_photo(
                    call.from_user.id,
                    photo=input_photo_profile,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=markup_profile
                )
            else:
                caption = (
                    f"<b>✨ Профиль\n──────────────\n👤 Имя: {nickname}\n🆔 ID: <code>{user_id}</code>\n"
                    f"──────────────\n💰 Баланс:</b> {html.escape(f'{balance:.2f}')}⭐️\n"
                    f"<b>👥 Рефералов:</b> {html.escape(str(count_refs))}\n"
                    f"<b>──────────────</b>\n⬇️ <i>Используй кнопки ниже для действий.</i>"
                )
                await bot.send_photo(
                    call.from_user.id,
                    photo=input_photo_profile,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=markup_profile
                )
    except Exception as e:
        logging.error(f"Ошибка при отображении профиля: {e}")
        error_message = (
            f"<b>Профиль: {nickname} | ID: <code>{user_id}</code></b>\n\n"
            f"<b>⚠️ Ошибка при получении данных профиля.\n"
            f"Пропишите /start для перезагрузки статистики</b>"
        )
        await bot.send_message(
            call.from_user.id,
            error_message,
            parse_mode='HTML',
            reply_markup=markup_profile
        )


@router.callback_query(F.data == "promocode")
async def promocode_callback_query(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.from_user.id, call.message.message_id)
    with open('photos/promocode.jpg', 'rb') as photo:
        input_photo_promo = FSInputFile("photos/promocode.jpg")
        await bot.send_photo(call.from_user.id, photo=input_photo_promo,
                             caption=f"✨ Для получения звезд на ваш баланс введите промокод:\n*<i>Найти промокоды можно в <a href='{channel_osn}'>канале</a> и <a href='{chater}'>чате</a></i>",
                             parse_mode='HTML')
    await state.set_state(AdminState.PROMOCODE_INPUT)


async def send_promocode_menu(user_id: int, bot: Bot, state: FSMContext):
    try:
        with open('photos/promocode.jpg', 'rb') as photo:
            input_photo_promo = FSInputFile("photos/promocode.jpg")
            await bot.send_photo(user_id, photo=input_photo_promo,
                                 caption=f"✨ Для получения звезд на ваш баланс введите промокод:\n*<i>Найти промокоды можно в <a href='{channel_osn}'>канале</a> и <a href='{chater}'>чате</a></i>",
                                 parse_mode='HTML')
        await state.set_state(AdminState.PROMOCODE_INPUT)
    except Exception as e:
        logging.error(f"Ошибка при отправке меню промокода: {e}")
        # Можно добавить отправку сообщения об ошибке пользователю, если нужно
        await bot.send_message(user_id, "<b>⚠️ Произошла ошибка при загрузке страницы промокода.</b>",
                               parse_mode='HTML')


# --- НОВАЯ вспомогательная функция для отправки меню "Заработать звёзды" ---
async def send_earn_stars_menu(user_id: int, bot: Bot, first_name: str, language_code: str):
    user_is_booster = user_in_booster(user_id)
    c_refs = get_user_referrals_count(user_id)

    stars = 0
    level = 0
    if c_refs < 50:
        stars = nac_1[0]
        level = 1
    elif c_refs >= 50 and c_refs < 250:
        stars = nac_2[0]
        level = 2
    else:
        stars = nac_3[0]
        level = 3

    blockquote_text = f"""
    <blockquote>🔹 <b>Ваш текущий уровень: {level}</b>

🔹 <b>Уровни и награды:</b>
- <b>1 уровень:</b> {nac_1[0] * 2 if user_is_booster else nac_1[0]} звезд ⭐️ (до 50 приглашений)
- <b>2 уровень:</b> {nac_2[0] * 2 if user_is_booster else nac_2[0]} звезда ⭐️ (от 50 до 250 приглашений)
- <b>3 уровень:</b> {nac_3[0] * 2 if user_is_booster else nac_3[0]} звезды ⭐️ (250+ приглашений)
    </blockquote>
    """

    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"  # Получаем username бота динамически

    builder_earn = InlineKeyboardBuilder()
    builder_earn.button(text="👉 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}")
    builder_earn.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_earn = builder_earn.adjust(1).as_markup()

    with open("photos/get_url.jpg", "rb") as photo_file:  # Использовать photo_file, чтобы избежать конфликта имени
        input_photo_earn = FSInputFile("photos/get_url.jpg")
        await bot.send_photo(user_id, photo=input_photo_earn,
                             caption=f'<b>🎉 Приглашай друзей и получай звёзды! ⭐️\n\n🚀 Как использовать свою реферальную ссылку?\n</b><i>• Отправь её друзьям в личные сообщения 👥\n• Поделись ссылкой в своём Telegram-канале 📢\n• Оставь её в комментариях или чатах 🗨️\n• Распространяй ссылку в соцсетях: TikTok, Instagram, WhatsApp и других 🌍</i>\n\n<b>💎 Что ты получишь?</b>\nЗа каждого друга, который перейдет по твоей ссылке, ты получаешь +<b>{stars * 2 if user_is_booster else stars}⭐️</b>!\n{blockquote_text}\n\n<b>🔗 Твоя реферальная ссылка:\n<code>{ref_link}</code>\n\nДелись и зарабатывай уже сейчас! 🚀</b>',
                             parse_mode='HTML', reply_markup=markup_earn)


@router.callback_query(F.data == "earn_stars")
async def earn_stars_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    if user_id not in admins_id:
        if button_subgram[0] == True:
            response = await request_op(
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

    ref_link = f"https://t.me/{(await bot.me()).username}?start={call.from_user.id}"
    builder_earn = InlineKeyboardBuilder()
    builder_earn.button(text="👉 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}")
    builder_earn.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_earn = builder_earn.adjust(1).as_markup()
    c_refs = get_user_referrals_count(call.from_user.id)
    user_is_booster = user_in_booster(call.from_user.id)
    stars = 0
    level = 0
    if c_refs < 50:
        stars = nac_1[0]
        level = 1
    elif c_refs >= 50 and c_refs < 250:
        stars = nac_2[0]
        level = 2
    else:
        stars = nac_3[0]
        level = 3

    blockquote_text = f"""
    <blockquote>🔹 <b>Ваш текущий уровень: {level}</b>

🔹 <b>Уровни и награды:</b>
- <b>1 уровень:</b> {nac_1[0] * 2 if user_is_booster else nac_1[0]} звезд ⭐️ (до 50 приглашений)
- <b>2 уровень:</b> {nac_2[0] * 2 if user_is_booster else nac_2[0]} звезда ⭐️ (от 50 до 250 приглашений)
- <b>3 уровень:</b> {nac_3[0] * 2 if user_is_booster else nac_3[0]} звезды ⭐️ (250+ приглашений)
    </blockquote>
    """

    with open("photos/get_url.jpg", "rb") as photo:
        input_photo_earn = FSInputFile("photos/get_url.jpg")
        await bot.send_photo(call.from_user.id, photo=input_photo_earn,
                             caption=f'<b>🎉 Приглашай друзей и получай звёзды! ⭐️\n\n🚀 Как использовать свою реферальную ссылку?\n</b><i>• Отправь её друзьям в личные сообщения 👥\n• Поделись ссылкой в своём Telegram-канале 📢\n• Оставь её в комментариях или чатах 🗨️\n• Распространяй ссылку в соцсетях: TikTok, Instagram, WhatsApp и других 🌍</i>\n\n<b>💎 Что ты получишь?</b>\nЗа каждого друга, который перейдет по твоей ссылке, ты получаешь +<b>{stars * 2 if user_is_booster else stars}⭐️</b>!\n{blockquote_text}\n\n<b>🔗 Твоя реферальная ссылка:\n<code>{ref_link}</code>\n\nДелись и зарабатывай уже сейчас! 🚀</b>',
                             parse_mode='HTML', reply_markup=markup_earn)


# Обновляем функцию back_main_callback (убираем кнопку "Купить подписчиков")
@router.callback_query(F.data == "back_main")
async def back_main_callback(call: CallbackQuery, bot: Bot):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    builder_start = InlineKeyboardBuilder()
    buttons = [
        ('📝 Задания', 'tasks'),
        ('💸 Заработать звёзды', 'earn_stars'),
        ('🎮 Мини-игры', 'mini_games'),
        ('🎁 Вывод звёзд', 'withdraw_stars_menu'),
        ('👤 Профиль', 'my_balance'),
        ('✨ Фармить звёзды', 'click_star'),
        ('🏆 Топ', 'leaders')
    ]
    for text, callback_data in buttons:
        builder_start.button(text=text, callback_data=callback_data)

    # Убираем кнопку "Купить подписчиков" из inline-меню

    if beta_url and beta_name:
        builder_start.button(text=beta_name, url=beta_url)
    builder_start.adjust(1, 1, 2, 2, 1, 1)
    markup_start = builder_start.as_markup()

    try:
        all_stars = str(sum_all_stars())
        withdrawed = str(sum_all_withdrawn())
        with open('photos/start.jpg', 'rb') as photo:
            input_photo_back_main = FSInputFile("photos/start.jpg")
            await bot.send_photo(call.from_user.id, photo=input_photo_back_main,
                                 caption=f"<b>✨ Добро пожаловать в главное меню ✨</b>\n\n<b></b><b>♻️ Всего обменяли: <code>{withdrawed[:withdrawed.find('.') + 2] if '.' in withdrawed else withdrawed}</code>⭐️</b>\n\n<b>Как заработать звёзды?</b>\n<blockquote>🔸 <i>Кликай, собирай ежедневные награды и вводи промокоды</i>\n— всё это доступно в разделе «Профиль».\n🔸 <i>Выполняй задания и приглашай друзей</i>\n🔸 <i>Испытай удачу в увлекательных мини-играх</i>\n— всё это доступно в главном меню.</blockquote>",
                                 parse_mode='HTML', reply_markup=markup_start)
    except Exception as e:
        logging.error(f"Ошибка при отображении главного меню: {e}")
        await bot.send_message(call.from_user.id, "<b>⚠️ Ошибка при отображении главного меню.</b>", parse_mode='HTML',
                               reply_markup=markup_start)


@router.message(AdminState.USERS_CHECK)
async def users_check_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        from datetime import datetime, timezone
        user_id = int(message.text)
        balance = get_balance_user(user_id)
        usname = get_username(user_id)
        count_ref = get_user_referrals_count(user_id)
        ref_id = get_id_refferer(user_id)
        withdrawd = get_withdrawn(user_id)
        reg_time = get_normal_time_registration(user_id)
        reg_time = datetime.fromtimestamp(reg_time, tz=timezone.utc).strftime('%d/%m/%Y %H:%M')
        click_count = get_count_clicks(user_id)
        banned = get_banned_user(user_id)
        count_task = get_tasks_count_by_user_for_week(user_id)

        markup = InlineKeyboardBuilder()
        markup.button(text="❌ Заблокировать", callback_data=f"block_user:{user_id}")
        markup.button(text="🟢 Разблокировать", callback_data=f"unblock_user:{user_id}")
        markup.button(text="⚠️ Удалить", callback_data=f"delete_user:{user_id}")
        markup.button(text="⬅️ В админ меню", callback_data="adminpanelka")
        markup.adjust(1, 1, 1)
        markup_check = markup.as_markup()
        await bot.send_message(
            message.from_user.id,
            f"🧾<b>Информация о пользователе:</b>\n\n"
            f"👤 <b>ID пользователя:</b> <code>{user_id}</code>\n"
            f"📛 <b>Имя пользователя:</b> @{usname}\n"
            f"⭐️<b>Звёзды:</b> {balance}\n"
            f"<b>────────────────────────────────────────</b>\n"
            f"👥 <b>Количество рефералов:</b> {count_ref}\n"
            f"🔗 <b>ID реферера:</b> {ref_id}\n"
            f"<b>────────────────────────────────────────</b>\n"
            f"💰 <b>Выведено:</b> {withdrawd}\n"
            f"🌍 <b>Язык:</b> ru\n"
            f"<b>────────────────────────────────────────</b>\n"
            f"⏰ <b>Дата регистрации:</b> {reg_time}\n"
            f"🪞 <b>Количество кликов:</b> {click_count}\n"
            f"📄 <b>Количество выполненных заданий за неделю:</b> {count_task}\n"
            f"<b>────────────────────────────────────────</b>\n"
            f"<b>Статус:</b> {'🟩 Не заблокирован' if banned == 0 else '❌ Заблокирован'}\n\n"
            f"📊 <i>Информация актуальна на момент запроса.</i>",
            parse_mode='HTML',
            reply_markup=markup_check
        )
    except Exception as e:
        logging.error(f"Ошибка при проверке пользователя: {e}")
        await bot.send_message(message.from_user.id,
                               "<b>⚠️ Ошибка при проверке пользователя. Возможно пользователь удален или не найден в базе данных.</b>",
                               parse_mode='HTML')
    except ValueError:
        await bot.send_message(message.from_user.id, "<b>⚠️ Ошибка при проверке пользователя.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.callback_query(F.data.startswith('delete_user:'))
async def delete_user_callback(call: CallbackQuery, bot: Bot):
    try:
        user_id = int(call.data.split(":")[1])
        delete_user(user_id)
        await bot.answer_callback_query(call.id, "✅ Пользователь удален!", show_alert=True)
    except ValueError:
        await bot.answer_callback_query(call.id, "⚠️ Ошибка при удалении пользователя!", show_alert=True)


async def block_user_callback(call: CallbackQuery, bot: Bot):
    try:
        user_id = int(call.data.split(":")[1])
        banned = get_banned_user(user_id)
        if banned == 1:
            await bot.answer_callback_query(call.id, "⚠️ Пользователь уже заблокирован!", show_alert=True)
            return
        set_banned_user(user_id, 1)
        await bot.answer_callback_query(call.id, "✅ Пользователь заблокирован!", show_alert=True)
    except ValueError:
        await bot.answer_callback_query(call.id, "⚠️ Ошибка при блокировке пользователя!", show_alert=True)


@router.callback_query(F.data.startswith('unblock_user:'))
async def unblock_user_callback(call: CallbackQuery, bot: Bot):
    try:
        user_id = int(call.data.split(":")[1])
        banned = get_banned_user(user_id)
        if banned == 0:
            await bot.answer_callback_query(call.id, "⚠️ Пользователь не заблокирован!", show_alert=True)
            return
        set_banned_user(user_id, 0)
        await bot.answer_callback_query(call.id, "✅ Пользователь разблокирован!", show_alert=True)
    except ValueError:
        await bot.answer_callback_query(call.id, "⚠️ Ошибка при разблокировке пользователя!", show_alert=True)


@router.message(AdminState.ADD_STARS)
async def add_stars_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        new = message.text.split(":")
        user_id = int(new[0])
        stars = float(new[1])

        balance_prev = get_balance_user(user_id)
        ensure_user_exists(user_id)
        increment_stars(user_id, stars)
        balance_after = get_balance_user(user_id)

        await bot.send_message(
            message.from_user.id,
            f"<b>✅ Звезды успешно добавлены!</b>\n\n"
            f"<b>💰 Предыдущий баланс:</b> {balance_prev:.2f}⭐️\n"
            f"<b>💰 Новый баланс:</b> {balance_after:.2f}⭐️",
            parse_mode='HTML'
        )
        await bot.send_message(
            user_id,
            "<b>✅ Администратор выдал вам звезды.</b>",
            parse_mode='HTML'
        )
    except ValueError:
        await message.reply(
            "<b>❌ Неверный формат ввода. Используйте ID:Количество звезд (числа).</b>",
            parse_mode='HTML'
        )
    except Exception as e:
        logging.error(f"Ошибка в add_stars: {e}")
        await message.reply(
            "<b>❌ Произошла ошибка при добавлении звезд.</b>",
            parse_mode='HTML'
        )
    finally:
        await state.clear()


async def send_message_with_retry(
        bot: Bot,
        chat_id: int,
        text: str,
        parse_mode: str = None,
        reply_markup=None,
        photo_file_id: Optional[str] = None,
        sticker_file_id: Optional[str] = None,
        attempt: int = 0
):
    try:
        if photo_file_id:
            await bot.send_photo(
                chat_id,
                photo=photo_file_id,
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        elif sticker_file_id:  # Добавлена логика для стикера
            await bot.send_sticker(
                chat_id,
                sticker=sticker_file_id,
                reply_markup=reply_markup
            )
        else:
            await bot.send_message(
                chat_id,
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        return True
    except (TelegramForbiddenError, TelegramNotFound) as e:
        logging.error(f"Сообщение запрещено/пользователь не найден: {chat_id}. Причина: {e}")
        return False
    except TelegramMigrateToChat as e:
        logging.info(f"Чат перенесён. Новый ID: {e.migrate_to_chat_id}")
        return await send_message_with_retry(
            bot, e.migrate_to_chat_id, text, parse_mode, reply_markup, photo_file_id, attempt + 1
        )
    except TelegramRetryAfter as e:
        logging.warning(f"Ожидаем {e.retry_after} сек. из-за лимитов.")
        await asyncio.sleep(e.retry_after)
        return await send_message_with_retry(
            bot, chat_id, text, parse_mode, reply_markup, photo_file_id, attempt + 1
        )
    except Exception as e:
        logging.exception(f"Ошибка отправки: {e}")
        return False


async def update_progress(
        progress_message: types.Message,
        current: int,
        total_users: int,
        success: int,
        semaphore_value: int,
        speed_stats: dict
):
    percent = (current / total_users) * 100
    filled = int(percent / 10)
    progress_bar = '🟩' * filled + '⬜️' * (10 - filled)

    # Скорость отправки в сообщениях в секунду и в минуту
    current_speed = speed_stats["current_speed"]
    avg_speed = speed_stats["avg_speed"]

    try:
        await progress_message.edit_text(
            f"Прогресс: {progress_bar} {percent:.1f}%\n"
            f"Обработано: {current}/{total_users}\n"
            f"Успешно: {success}\n"
            f"Активные задачи: {semaphore_value}\n"
            f"Скорость: {current_speed:.1f} сообщ/сек ({current_speed * 60:.1f} сообщ/мин)\n"
            f"Средняя скорость: {avg_speed:.1f} сообщ/сек ({avg_speed * 60:.1f} сообщ/мин)"
        )
    except Exception as e:
        logging.error(f"Ошибка обновления прогресса: {e}")


async def broadcast(
        bot: Bot,
        start_msg: types.Message,
        users: List[Tuple[int]],
        text: str = None,  # Теперь текст необязателен
        photo_file_id: str = None,
        sticker_file_id: str = None,  # Добавлен параметр для ID стикера
        keyboard=None,
        max_concurrent: int = 25
):
    total_users = len(users)
    if not total_users:
        await start_msg.reply("<b>❌ Нет пользователей для рассылки.</b>", parse_mode="HTML")
        return

    progress_message = await start_msg.reply(
        "<b>📢 Статус рассылки:</b>\n\n"
        "Прогресс: <code>🟩⬜⬜⬜⬜⬜⬜⬜⬜⬜</code> <b>0%</b>\n"
        "Обработано: <b>0</b>/<b>{}</b>\n"
        "✅ Успешно: <b>0</b>\n"
        "⚡ Активные задачи: <b>0</b>\n"
        "📊 Скорость: <b>0.0</b> сообщ/сек (<b>0.0</b> сообщ/мин)\n"
        "📉 Средняя скорость: <b>0.0</b> сообщ/сек (<b>0.0</b> сообщ/мин)".format(total_users),
        parse_mode="HTML"
    )

    semaphore = asyncio.Semaphore(max_concurrent)
    progress_lock = asyncio.Lock()

    processed = 0
    success = 0
    tasks = []

    start_time = time.time()
    message_timestamps = deque(maxlen=100)
    speed_stats = {
        "current_speed": 0.0,
        "avg_speed": 0.0,
        "last_update": start_time
    }

    def calculate_speed():
        now = time.time()

        if len(message_timestamps) >= 2:
            time_span = message_timestamps[-1] - message_timestamps[0]
            if time_span > 0:
                current_speed = (len(message_timestamps) - 1) / time_span
            else:
                current_speed = 0
        else:
            current_speed = 0

        elapsed = now - start_time
        if elapsed > 0 and processed > 0:
            avg_speed = processed / elapsed
        else:
            avg_speed = 0

        return {
            "current_speed": current_speed,
            "avg_speed": avg_speed,
            "last_update": now
        }

    async def process_user(user_id):
        nonlocal processed, success

        async with semaphore:
            result = await send_message_with_retry(
                bot, user_id, text, "HTML", keyboard, photo_file_id, sticker_file_id
            )

            async with progress_lock:
                processed += 1
                if result:
                    success += 1

                message_timestamps.append(time.time())

                now = time.time()
                if (now - speed_stats["last_update"] > 2 or processed % 50 == 0):
                    speed_stats.update(calculate_speed())

                progress_percentage = processed / total_users * 100
                progress_blocks = int(progress_percentage // 10)
                progress_bar = "🟩" * progress_blocks + "⬜" * (10 - progress_blocks)

                if processed % max(1, total_users // 20) == 0 or processed == total_users:
                    active_tasks = len(tasks) - sum(task.done() for task in tasks)
                    await progress_message.edit_text(
                        "<b>📢 Статус рассылки:</b>\n\n"
                        f"Прогресс: <code>{progress_bar}</code> <b>{progress_percentage:.1f}%</b>\n"
                        f"Обработано: <b>{processed}</b>/<b>{total_users}</b>\n"
                        f"✅ Успешно: <b>{success}</b>\n"
                        f"⚡ Активные задачи: <b>{active_tasks}</b>\n"
                        f"📊 Скорость: <b>{speed_stats['current_speed']:.1f}</b> сообщ/сек "
                        f"(<b>{speed_stats['current_speed'] * 60:.1f}</b> сообщ/мин)\n"
                        f"📉 Средняя скорость: <b>{speed_stats['avg_speed']:.1f}</b> сообщ/сек "
                        f"(<b>{speed_stats['avg_speed'] * 60:.1f}</b> сообщ/мин)",
                        parse_mode="HTML"
                    )

    for user_id, in users:
        task = asyncio.create_task(process_user(user_id))
        tasks.append(task)

    await asyncio.gather(*tasks)

    elapsed_time = time.time() - start_time
    final_speed = processed / elapsed_time if elapsed_time > 0 else 0

    await progress_message.edit_text(
        "<b>✅ Рассылка завершена!</b>\n\n"
        f"📨 Успешно отправлено: <b>{success}</b>/<b>{total_users}</b> "
        f"(<b>{success / total_users * 100:.1f}%</b>)\n"
        f"⏳ Время выполнения: <b>{elapsed_time:.1f}</b> сек\n"
        f"🚀 Средняя скорость: <b>{final_speed:.1f}</b> сообщ/сек "
        f"(<b>{final_speed * 60:.1f}</b> сообщ/мин)",
        parse_mode="HTML"
    )

    logging.info(
        f"Рассылка завершена. Отправлено {success}/{total_users} сообщений за {elapsed_time:.1f} сек. "
        f"Средняя скорость: {final_speed:.1f} сообщ/сек"
    )


@router.message(AdminState.MAILING)
async def mailing_handler(message: types.Message, state: FSMContext):
    photo_file_id = None
    sticker_file_id = None
    text = ""
    entities = []  # Инициализируем entities пустым списком

    # Определяем тип контента и сохраняем его ID
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        text = message.caption or ""  # Подпись к фото
        entities = message.caption_entities or []
    elif message.sticker:
        sticker_file_id = message.sticker.file_id
        # Для стикера мы предложим добавить кнопки отдельным шагом
        await message.reply(
            "Отлично, стикер принят! Теперь, если хотите добавить кнопки к этому стикеру, отправьте текст с кнопками в формате `{текст кнопки}:{ссылка}`. Если кнопки не нужны, просто отправьте `/done`.")
        # Сохраняем ID стикера в состоянии для последующей рассылки
        await state.update_data(sticker_file_id=sticker_file_id)
        await state.set_state(AdminState.WAITING_FOR_BUTTONS_AFTER_STICKER)
        return
    else:  # Если ни фото, ни стикера, то это просто текстовое сообщение
        text = message.text or ""
        entities = message.entities or []

    # Если это не стикер, обрабатываем рассылку сразу
    users = get_users_ids()
    buttons = re.findall(r"\{([^{}]+)\}:([^{}]+)", text)
    keyboard = None

    if buttons:
        kb = InlineKeyboardBuilder()
        for btn_text, btn_url in buttons:
            kb.button(text=btn_text.strip(), url=btn_url.strip())
        kb.adjust(1)
        keyboard = kb.as_markup()
        # Удаляем кнопки из текста, чтобы они не отображались в сообщении
        # Используем message.html_text для получения текста с сохранением форматирования,
        # затем удаляем из него блоки с кнопками.
        text = re.sub(r"\{[^{}]+\}:([^{}]+)", "", message.html_text if message.html_text else text).strip()
    else:
        # Если кнопок нет, используем html_text для сохранения форматирования
        text = message.html_text if message.html_text else text

    logging.info(f"Начало рассылки для {len(users)} пользователей")

    await broadcast(
        message.bot,
        message,
        users,
        text,  # Теперь text уже содержит форматирование и без кнопок
        photo_file_id,
        sticker_file_id,  # Будет None, если это не стикер, и заполнен, если это стикер, обработанный на этом шаге
        keyboard
    )
    await state.clear()


@router.message(AdminState.WAITING_FOR_BUTTONS_AFTER_STICKER)
async def handle_buttons_for_sticker(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sticker_file_id = data.get("sticker_file_id")

    if not sticker_file_id:
        await message.reply(
            "Произошла ошибка: не удалось найти стикер для рассылки. Пожалуйста, начните заново, отправив стикер.")
        await state.clear()
        return

    text_with_buttons = message.text
    keyboard = None
    buttons_extracted = False

    if text_with_buttons and text_with_buttons.lower() != "/done":
        buttons = re.findall(r"\{([^{}]+)\}:([^{}]+)", text_with_buttons)
        if buttons:
            kb = InlineKeyboardBuilder()
            for btn_text, btn_url in buttons:
                kb.button(text=btn_text.strip(), url=btn_url.strip())
            kb.adjust(1)
            keyboard = kb.as_markup()
            buttons_extracted = True
            # Так как стикеры не имеют подписи, текст с кнопками не будет отображаться
            # Удаляем кнопки из текста, чтобы избежать путаницы, если вдруг текст будет выведен
            text_with_buttons = re.sub(r"\{[^{}]+\}:([^{}]+)", "", text_with_buttons).strip()
        else:
            await message.reply(
                "Некорректный формат кнопок. Пожалуйста, используйте `{текст кнопки}:{ссылка}`. Или отправьте `/done`, если кнопки не нужны.")
            return  # Остаемся в этом состоянии, ожидая правильный формат или /done
    elif message.text.lower() == "/done":
        # Если прислали /done, то кнопки не нужны
        pass
    else:
        # Если прислали что-то другое, не кнопки и не /done
        await message.reply("Я ожидаю либо текст с кнопками, либо команду `/done`. Пожалуйста, попробуйте еще раз.")
        return

    users = get_users_ids()
    logging.info(f"Начало рассылки стикеров с кнопками для {len(users)} пользователей")

    # Для стикеров текст всегда пустой, кнопки будут прикреплены к стикеру
    await broadcast(
        message.bot,
        message,
        users,
        text=None,  # Текст для стикера всегда None
        photo_file_id=None,
        sticker_file_id=sticker_file_id,
        keyboard=keyboard
    )
    await state.clear()


def apply_html_formatting(text, entities):
    if not text:
        return ""

    if not entities:
        return html.escape(text)

    escaped_text = html.escape(text)

    tag_map = {
        "bold": ("<b>", "</b>"),
        "italic": ("<i>", "</i>"),
        "underline": ("<u>", "</u>"),
        "strikethrough": (" ", " "),
        "spoiler": ("<span class='tg-spoiler'>", "</span>"),
        "code": ("<code>", "</code>"),
        "pre": ("<pre>", "</pre>"),
        "blockquote": ("<blockquote>", "</blockquote>"),
    }

    operations = []

    for entity in entities:
        if entity.type in tag_map:
            start_tag, end_tag = tag_map[entity.type]
            operations.append((entity.offset, start_tag, "open", entity.type))
            operations.append((entity.offset + entity.length, end_tag, "close", entity.type))

    operations.sort(key=lambda x: (x[0], x[2] == "open"))

    result = []
    open_tags = []
    last_pos = 0

    for pos, tag, tag_type, entity_type in operations:
        result.append(escaped_text[last_pos:pos])
        last_pos = pos

        if tag_type == "close":
            while open_tags:
                last_tag = open_tags.pop()
                result.append(last_tag[1])
                if last_tag[0] == entity_type:
                    break
        else:
            result.append(tag)
            open_tags.append((entity_type, tag_map[entity_type][1]))

    result.append(escaped_text[last_pos:])

    while open_tags:
        result.append(open_tags.pop()[1])

    return "".join(result)


def safe_apply_html_formatting(text, entities):
    if not text:
        return ""

    if not entities:
        return html.escape(text)

    escaped_text = html.escape(text)
    positions = {}

    tag_map = {
        "bold": "b",
        "italic": "i",
        "underline": "u",
        "strikethrough": "s",
        "spoiler": "tg-spoiler",
        "code": "code",
        "pre": "pre",
        "blockquote": "blockquote",
    }

    # Заполняем позиции тегами
    for entity in entities:
        if entity.type in tag_map:
            tag = tag_map[entity.type]
            start, end = entity.offset, entity.offset + entity.length

            positions.setdefault(start, []).append((tag, True))
            positions.setdefault(end, []).append((tag, False))

    result = []
    open_tags = []

    for i in range(len(escaped_text) + 1):
        if i in positions:
            closing_tags = [t for t, open_ in positions[i] if not open_]

            while closing_tags:
                if open_tags:
                    last_opened = open_tags.pop()
                    result.append(f"</{last_opened}>")
                    closing_tags.remove(last_opened)

            opening_tags = [t for t, open_ in positions[i] if open_]
            for tag in opening_tags:
                result.append(f"<{tag}>")
                open_tags.append(tag)

        if i < len(escaped_text):
            result.append(escaped_text[i])

    while open_tags:
        result.append(f"</{open_tags.pop()}>")

    return "".join(result)


@router.message(AdminState.ADD_CHANNEL)
async def add_channel_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        channel_id = message.text
        required_subscription.append(int(channel_id))
        await message.reply(f"<b>✅ Канал успешно добавлен!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при добавлении канала: {e}")
        await message.reply("<b>❌ Произошла ошибка при добавлении канала.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.REMOVE_CHANNEL)
async def delete_channel_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        channel_id = message.text
        required_subscription.remove(int(channel_id))
        await message.reply(f"<b>✅ Канал успешно удален!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при удалении канала: {e}")
        await message.reply("<b>❌ Произошла ошибка при удалении канала.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.PROMOCODE_INPUT)
async def promocode_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    markup_back_inline = InlineKeyboardBuilder()
    markup_back_inline.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = markup_back_inline.as_markup()

    promocode_text = message.text
    try:
        success, result = use_promocode(promocode_text, message.from_user.id)
        if success:
            await message.reply(f"<b>✅ Промокод успешно активирован!\nВам начислено {result} ⭐️</b>", parse_mode='HTML',
                                reply_markup=markup_back)
            await send_main_menu(user_id, bot)
        else:
            await message.reply(f"<b>❌ Ошибка: {result}</b>", parse_mode='HTML')
            await send_main_menu(user_id, bot)
    except Exception as e:
        logging.error(f"Ошибка при активации промокода: {e}")
        await message.reply("<b>❌ Произошла ошибка при активации промокода.</b>", parse_mode='HTML')
        await send_main_menu(user_id, bot)
    finally:
        await state.clear()


@router.message(AdminState.ADD_PROMO_CODE)
async def add_promo_code_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        promocode, stars_str, max_uses_str = message.text.split(":")
        stars = int(stars_str)
        max_uses = int(max_uses_str)
        add_promocode(promocode, stars, max_uses)
        await message.reply(f"<b>✅ Промокод успешно добавлен!</b>", parse_mode='HTML')
    except ValueError:
        await message.reply("<b>❌ Неверный формат ввода. Используйте промокод:награда:макс. пользований (числа).</b>",
                            parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при добавлении промокода: {e}")
        await message.reply("<b>❌ Произошла ошибка при добавлении промокода.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.REMOVE_PROMO_CODE)
async def delete_promo_code_handler(message: Message, state: FSMContext, bot: Bot):
    promocode = message.text
    try:
        deactivate_promocode(promocode)
        await message.reply(f"<b>✅ Промокод успешно удален!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при удалении промокода: {e}")
        await message.reply("<b>❌ Произошла ошибка при удалении промокода.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.ADD_TASK_CHANNEL)
async def add_task_channel_handler(message: Message, state: FSMContext, bot: Bot):
    channel_id_private = int(message.text)
    data = await state.get_data()
    text = data.get('task_text')
    stars = data.get('task_reward')
    channel = data.get('task_channel')
    boter = str(data.get('task_bot'))
    max_compl = data.get('task_max_compl')
    try:
        await state.clear()
        add_tasker(text, stars, channel, boter if boter.lower() == "да" else "none", int(max_compl), channel_id_private)
        await message.reply(f"<b>✅ Задание успешно добавлено!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при добавлении задания: {e}")
        await message.reply("<b>❌ Произошла ошибка при добавлении задания.</b>", parse_mode='HTML')


async def show_leaderboard(message: Message, period, bot: Bot):
    user_id = message.chat.id
    try:
        await bot.delete_message(user_id, message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    try:
        top_referrals = get_top_referrals_formatted(period)
        user_rank = get_user_referral_rank_formatted(user_id, period)
        builder = InlineKeyboardBuilder()
        if period == "day":
            builder.button(text="📅 Топ за месяц", callback_data="month")
            builder.button(text="📅 Топ за неделю", callback_data="week")
        elif period == "week":
            builder.button(text="📅 Топ за день", callback_data="leaders")
            builder.button(text="📅 Топ за месяц", callback_data="month")
        elif period == "month":
            builder.button(text="📅 Топ за день", callback_data="leaders")
            builder.button(text="📅 Топ за неделю", callback_data="week")
        builder.button(text="⬅️ В главное меню", callback_data="back_main")
        markup = builder.adjust(2, 1).as_markup()

        if isinstance(top_referrals, str):
            text = f"<b>⚠️ Ошибка при получении списка лидеров за {get_period_name(period)}:</b>\n\n{top_referrals}"
        else:
            text = f"<b>Топ 5 рефералов за {get_period_name(period)}:</b>\n\n"
            for line in top_referrals:
                text += line + "\n"
            text += "\n" + user_rank

        with open('photos/leaders.jpg', 'rb') as photo:
            input_photo_leaders = FSInputFile("photos/leaders.jpg")
            await bot.send_photo(user_id, photo=input_photo_leaders, caption=text, parse_mode='HTML',
                                 reply_markup=markup)

    except Exception as e:
        logging.error(f"Ошибка при получении топа рефералов за {period}: {e}")
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ В главное меню", callback_data="back_main")
        markup = builder.as_markup()
        await bot.send_message(user_id, f"<b>⚠️ Ошибка при получении списка лидеров за {get_period_name(period)}.</b>",
                               parse_mode='HTML', reply_markup=markup)


def get_period_name(period):
    if period == 'day':
        return "24 часа"
    elif period == 'week':
        return "неделю"
    elif period == 'month':
        return "месяц"
    return period


async def on_startup(bot: Bot):
    # Создаем таблицу для отслеживания подписок при запуске
    create_task_subscriptions_table()


async def show_subgram_task_unified(user_id: int, first_name: str, language_code: str, bot: Bot):
    """Показывает SubGram задания через единую систему сообщений"""

    # Получаем задания SubGram заново для получения ссылок
    headers = {
        'Content-Type': 'application/json',
        'Auth': f'{SUBGRAM_TOKEN}',
        'Accept': 'application/json',
    }
    data = {'UserId': user_id, 'ChatId': user_id, 'action': 'task', 'MaxOP': 1}

    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.subgram.ru/request-op-tokenless/', headers=headers, json=data) as response:
            if response.ok and response.status == 200:
                response_json = await response.json()

                if response_json.get('status') == 'warning':
                    links = response_json.get("links", [])

                    # Создаем задание через единую систему
                    markup = InlineKeyboardBuilder()
                    temp_row = []
                    sponsor_count = 0

                    for url in links:
                        urls = get_urls_by_id(user_id)
                        if url in urls:
                            continue
                        sponsor_count += 1
                        name = f'✅ Подписаться на канал №{sponsor_count}'
                        button = types.InlineKeyboardButton(text=name, url=url)
                        temp_row.append(button)

                        if sponsor_count % 2 == 0:
                            markup.row(*temp_row)
                            temp_row = []

                    if temp_row:
                        markup.row(*temp_row)

                    if sponsor_count > 0:
                        item1 = types.InlineKeyboardButton(text='🔎 Проверить подписку',
                                                           callback_data=f'subgram-task:{sponsor_count}')
                        skip_task = types.InlineKeyboardButton(text='➡️ Пропустить', callback_data='skip_subgram_task')
                        back_to_main = types.InlineKeyboardButton(text='⬅️ В главное меню', callback_data='back_main')
                        markup.row(item1)
                        markup.row(skip_task, back_to_main)

                        try:
                            photo = FSInputFile("photos/task.jpg")
                            msg = await bot.send_photo(
                                user_id,
                                photo=photo,
                                caption=f"<b>✨ Следующее задание! ✨</b>\n\n• Подпишитесь на каналы, которые указаны ниже.\n\nНаграда: {task_grant[0]} ⭐️\n\n📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней \"Проверить подписку\" 👇",
                                parse_mode='HTML',
                                reply_markup=markup.as_markup()
                            )
                        except:
                            msg = await bot.send_message(
                                user_id,
                                f"<b>✨ Следующее задание! ✨</b>\n\n• Подпишитесь на каналы, которые указаны ниже.\n\nНаграда: {task_grant[0]} ⭐️\n\n📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней \"Проверить подписку\" 👇",
                                parse_mode='HTML',
                                reply_markup=markup.as_markup()
                            )

                        # Сохраняем ID сообщения
                        user_task_messages[user_id] = msg.message_id
                        return True

    return False


@router.callback_query(F.data == "tasks")
async def tasks_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    first_name = call.from_user.first_name
    language_code = call.from_user.language_code
    is_premium = getattr(call.from_user, 'is_premium', None)

    banned = get_banned_user(user_id)
    if banned == 1:
        await bot.answer_callback_query(call.id, "🚫 Вы заблокированы в боте!", show_alert=True)
        return

    # Проверка подписки на SubGram (если не админ)
    if user_id not in admins_id and button_subgram[0]:
        response = await request_op(
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

    # Удаляем предыдущие задания
    await delete_task_message(bot, user_id)
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении главного сообщения: {e}")

    # УБИРАЕМ ЭТУ ЧАСТЬ - проверка SubGram заданий
    # try:
    #     if button_subgram[0]:
    #         tasks = await request_task(user_id, user_id, first_name, language_code, bot)
    #         if tasks != 'ok':
    #             await show_subgram_task_unified(user_id, first_name, language_code, bot)
    #             return
    # except Exception as e:
    #     logging.error(f"Ошибка при проверке SubGram: {e}")

    # Проверка заданий от Flyer (остается без изменений)
    try:
        tasks_list = await get_flyer_tasks(FLYER_KEY, user_id, limit=10)
        selected_task = None

        for task in tasks_list:
            link = task.get('link')
            signature = task.get('signature')
            if not link or not signature:
                continue

            task_hash = hash_flyer_task(signature, user_id)
            if not is_flyer_task_completed(task_hash) and not is_flyer_task_skipped(task_hash, user_id):
                selected_task = task
                break

        if selected_task:
            link = selected_task.get('link')
            signature = selected_task.get('signature')

            task_text = (
                f'<b>✨ Новое задание! ✨\n\n'
                f'• Подпишитесь на каналы, указанные ниже.\n\n'
                f'Награда: {task_grant[0]} ⭐️</b>\n\n'
                f'📌 Чтобы получить награду полностью, подпишитесь и не отписывайтесь от канала/группы в течение 3-х дней. '
                f'Нажмите "Проверить подписку", чтобы подтвердить!'
            )

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Подписаться на канал", url=link)
            builder.button(text="🔎 Проверить подписку", callback_data=f'flyer_check:{signature}')
            builder.button(text="⬅️ В главное меню", callback_data="back_main")
            builder.button(text="➡️ Пропустить", callback_data=f'skip_flyer_task:{signature}')
            markup = builder.adjust(1, 1, 2).as_markup()

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(call.from_user.id, photo=photo, caption=task_text, parse_mode='HTML',
                                           reply_markup=markup)
            except:
                msg = await bot.send_message(call.from_user.id, task_text, parse_mode='HTML', reply_markup=markup)

            user_task_messages[user_id] = msg.message_id
            return

    except Exception as e:
        logging.error(f"Ошибка при получении заданий от Flyer: {e}")

    # Пользовательские задания (остается без изменений)
    try:
        user_task = await get_next_user_task(user_id)
        if user_task:
            task_id, creator_id, post_text, post_entities, channel_id, channel_link, target_subscribers, current_subscribers = user_task

            builder = InlineKeyboardBuilder()
            builder.button(text="✅ Подписаться на канал", url=channel_link)
            builder.button(text="🔎 Проверить подписку", callback_data=f"check_user_task:{task_id}")
            builder.button(text="⬅️ В главное меню", callback_data="back_main")
            builder.button(text="➡️ Пропустить", callback_data=f"skip_user_task:{task_id}")
            markup = builder.adjust(1, 1, 2).as_markup()

            reward = task_grant[0]
            text = (
                f"<b>✨ Новое задание! ✨</b>\n\n"
                f"• Подпишитесь на каналы, которые указаны ниже.\n\n"
                f"Награда: {reward} ⭐️\n\n"
                f"📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней."
            )

            try:
                photo = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(call.from_user.id, photo=photo, caption=text, parse_mode='HTML',
                                           reply_markup=markup)
            except:
                msg = await bot.send_message(call.from_user.id, text, parse_mode='HTML', reply_markup=markup)

            user_task_messages[user_id] = msg.message_id
            return

    except Exception as e:
        logging.error(f"Ошибка при получении пользовательского задания: {e}")

    # Если нет заданий
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    await bot.send_message(
        call.from_user.id,
        "<b>🎯 На данный момент нет доступных заданий!\n\nВозвращайся позже!</b>",
        parse_mode='HTML',
        reply_markup=markup_back
    )


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.message.middleware(AntiFloodMiddleware(limit=1))
    dp.callback_query.middleware(AntiFloodMiddleware(limit=1))
    dp.startup.register(on_startup)
    dp.include_router(router)

    # Запускаем юзербота
    await start_userbot()

    # Регистрируем обработчик для корректной остановки юзербота
    dp.shutdown.register(stop_userbot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_remove_expired_boosts, 'interval', minutes=10)
    # Добавляем задачу для проверки подписок каждые 6 часов
    scheduler.add_job(check_user_subscriptions_and_penalize, 'interval', hours=6, args=[bot])
    # Добавляем задачу для проверки валидности пользовательских заданий каждые 2 часа
    scheduler.add_job(check_user_tasks_validity, 'interval', hours=2, args=[bot])
    scheduler.start()
    create_utm_stats_table()
    create_skipped_tasks_table()
    logging.info("Таблица skipped_tasks проверена/создана.")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())