
from typing import Dict
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.exceptions import TelegramBadRequest

class WebhookRegistry:
    """
    In-memory registry for bot instances owned by this worker.
    DB remains the source of truth; Redis is used to route ownership.
    """
    def __init__(self):
        self.bots: Dict[int, Bot] = {}
        self.dispatchers: Dict[int, Dispatcher] = {}

    def register(self, bot_id, bot, dp):
        self.bots[bot_id] = bot
        self.dispatchers[bot_id] = dp

    async def handle(self, bot_id: int, update: Update):
        dp = self.dispatchers.get(bot_id)
        bot = self.bots.get(bot_id)
        if not dp or not bot:
            return False
        await dp.feed_update(bot, update)
        return True

    async def remove(self, bot_id):
        bot = self.bots.pop(bot_id, None)
        self.dispatchers.pop(bot_id, None)
        if bot:
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except Exception:
                pass
            await bot.session.close()
        return True
