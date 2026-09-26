
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from database import Database
from security import decrypt_token


class BotManager:
    def __init__(self, db: Database):
        self.db = db
        self.tasks = {}
        self.bots = {}

    async def validate_token(self, token):
        bot = Bot(token)
        try:
            return await bot.get_me()
        finally:
            await bot.session.close()

    async def start_bot(self, bot_id):
        if bot_id in self.tasks and not self.tasks[bot_id].done():
            return False, "البوت يعمل بالفعل."

        row = await self.db.get_bot(bot_id)
        if not row:
            return False, "البوت غير موجود."

        try:
            bot = Bot(decrypt_token(row.token))
            me = await bot.get_me()
        except Exception as e:
            try:
                await bot.session.close()
            except Exception:
                pass
            return False, f"فشل الاتصال: {e}"

        dp = Dispatcher()

        @dp.message(CommandStart())
        async def start_handler(message: Message):
            setting = await self.db.get_setting(bot_id)
            welcome = setting.welcome_message if setting else "👋 أهلاً بك!"
            name = message.from_user.first_name if message.from_user else "صديقي"
            await message.answer(welcome.replace("{name}", name))
            await self.db.increment_message(bot_id, new_user=True)

        @dp.message(F.text)
        async def text_handler(message: Message):
            if row.template == "echo":
                await message.answer(f"🔁 {message.text}")
            elif row.template == "support":
                await message.answer("🎫 تم استلام رسالتك. سيتم التعامل معها من خلال نظام الدعم.")
            else:
                await message.answer("👋 أهلاً بك! أرسل /start لرؤية رسالة الترحيب.")
            await self.db.increment_message(bot_id)

        await self.db.set_running(bot_id, True)
        self.bots[bot_id] = bot
        task = asyncio.create_task(self._poll(bot_id, bot, dp))
        self.tasks[bot_id] = task
        return True, f"تم تشغيل @{me.username or me.id}"

    async def _poll(self, bot_id, bot, dp):
        try:
            await dp.start_polling(bot)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Bot {bot_id}] polling error: {e}")
        finally:
            await self.db.set_running(bot_id, False)
            self.bots.pop(bot_id, None)
            try:
                await bot.session.close()
            except Exception:
                pass

    async def stop_bot(self, bot_id):
        task = self.tasks.get(bot_id)
        if not task or task.done():
            await self.db.set_running(bot_id, False)
            return False, "البوت متوقف بالفعل."
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        self.tasks.pop(bot_id, None)
        await self.db.set_running(bot_id, False)
        return True, "تم إيقاف البوت."

    async def delete_bot(self, bot_id):
        await self.stop_bot(bot_id)
        await self.db.delete_bot(bot_id)

    async def restore_running(self):
        rows = await self.db.list_running_bots()
        for row in rows:
            await self.start_bot(row.id)
