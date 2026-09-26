
import asyncio
import json
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from database import Database
from security import decrypt_token
from task_queue import TaskQueue
from webhook_router import WebhookRegistry
from config import WORKER_ID

class WebhookWorker:
    def __init__(self):
        self.db = Database()
        self.queue = TaskQueue()
        self.registry = WebhookRegistry()

    async def ensure_bot(self, bot_id):
        if bot_id in self.registry.bots:
            return
        row = await self.db.get_bot(bot_id)
        if not row:
            return
        bot = Bot(decrypt_token(row.token))
        dp = Dispatcher()

        @dp.message()
        async def all_messages(message):
            if row.template == "echo" and message.text:
                await message.answer(f"🔁 {message.text}")
            elif row.template == "support":
                await message.answer("🎫 تم استلام رسالتك.")
            elif message.text and message.text.startswith("/start"):
                setting = await self.db.get_setting(row.id)
                welcome = setting.welcome_message if setting else "👋 أهلاً بك!"
                name = message.from_user.first_name if message.from_user else "صديقي"
                await message.answer(welcome.replace("{name}", name))
            await self.db.increment_message(row.id)

        self.registry.register(bot_id, bot, dp)

    async def run(self):
        await self.db.init()
        while True:
            item = await self.queue.redis.blpop(f"factory:webhook:{WORKER_ID}", timeout=5)
            if not item:
                continue
            try:
                _, raw = item
                data = json.loads(raw)
                bot_id = int(data.get("bot_id", 0))
                # The generic web endpoint currently cannot embed bot_id into payload
                # in Redis; production reverse proxy should route directly to worker.
                # This file is kept as an extension point for direct worker routing.
            except Exception as e:
                print("webhook error:", e)

if __name__ == "__main__":
    asyncio.run(WebhookWorker().run())
