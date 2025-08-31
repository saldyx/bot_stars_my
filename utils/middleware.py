"""
Middleware для бота
"""
import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import types, BaseMiddleware


class AntiFloodMiddleware(BaseMiddleware):
    """Middleware для защиты от флуда"""
    
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