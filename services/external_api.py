"""
Сервис для работы с внешними API
"""
import logging
import aiohttp
from typing import Optional
from aiogram import Bot


class SubgramService:
    """Сервис для работы с SubGram API"""
    
    @staticmethod
    async def request_op(user_id: int, chat_id: int, first_name: str, language_code: str, 
                        bot: Bot, ref_id: Optional[int] = None, gender: Optional[str] = None, 
                        is_premium: Optional[bool] = None) -> str:
        """Запрос обязательной подписки через SubGram"""
        from settings import SUBGRAM_TOKEN
        
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
                        from handlers.subscription_handler import show_op
                        await show_op(chat_id, response_json.get("links", []), bot, ref_id=ref_id)
                    else:
                        from handlers.subscription_handler import show_op
                        await show_op(chat_id, response_json.get("links", []), bot)
                elif response_json.get('status') == 'gender':
                    if ref_id:
                        from handlers.subscription_handler import show_gender
                        await show_gender(chat_id, bot, ref_id=ref_id)
                    else:
                        from handlers.subscription_handler import show_gender
                        await show_gender(chat_id, bot)
                return response_json.get("status")
    
    @staticmethod
    async def request_task(user_id: int, chat_id: int, first_name: str, language_code: str, bot: Bot) -> str:
        """Запрос заданий через SubGram"""
        from settings import SUBGRAM_TOKEN
        
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
                    from handlers.task_handler import show_task
                    await show_task(chat_id, response_json.get("links", []), bot)
                return response_json.get("status")
    
    @staticmethod
    async def get_balance() -> float:
        """Получает баланс SubGram"""
        from settings import SUBGRAM_TOKEN
        
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
        
        return balance


class GramAdsService:
    """Сервис для работы с GramAds"""
    
    @staticmethod
    async def show_advert(user_id: int):
        """Показывает рекламу пользователю"""
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