import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

user_last_message: Dict[int, float] = {}

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, throttle_time_sec: int = 5):
        self.throttle_time = throttle_time_sec

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        
        last_time = user_last_message.get(user_id)
        
        if last_time and (time.time() - last_time) < self.throttle_time:
            return
        
        user_last_message[user_id] = time.time()
        return await handler(event, data)