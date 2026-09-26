
import asyncio, time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from database import Database
from security import decrypt_token
from queue import TaskQueue
from cluster import Cluster
from metrics import TASKS_TOTAL, BOT_EVENTS, WORKER_LOAD, TASK_LATENCY, start_metrics
from config import WORKER_ID, WEB_BASE_URL, WEBHOOK_PATH_PREFIX, WEBHOOK_SECRET_TOKEN, HEALTHCHECK_INTERVAL, MAX_BOTS_PER_WORKER

class BotWorker:
    def __init__(self):
        self.db = Database()
        self.queue = TaskQueue()
        self.cluster = Cluster()
        self.registry = {}
        self.running = True

    def webhook_url(self, bot_id):
        return f"{WEB_BASE_URL}{WEBHOOK_PATH_PREFIX}/{bot_id}"

    async def build(self, row):
        bot = Bot(decrypt_token(row.token))
        dp = Dispatcher()

        @dp.message(CommandStart())
        async def start_handler(message: Message):
            setting = await self.db.get_setting(row.id)
            welcome = setting.welcome_message if setting else "👋 أهلاً بك!"
            name = message.from_user.first_name if message.from_user else "صديقي"
            await message.answer(welcome.replace("{name}", name))
            await self.db.increment_message(row.id, new_user=True)

        @dp.message(F.text)
        async def text_handler(message: Message):
            if row.template == "echo":
                await message.answer(f"🔁 {message.text}")
            elif row.template == "support":
                await message.answer("🎫 تم استلام رسالتك. سيتم التعامل معها من خلال نظام الدعم.")
            else:
                await message.answer("👋 أهلاً بك! أرسل /start لرؤية رسالة الترحيب.")
            await self.db.increment_message(row.id)

        return bot, dp

    async def start_bot(self, bot_id):
        if bot_id in self.registry:
            return True, "already running"
        if len(self.registry) >= MAX_BOTS_PER_WORKER:
            return False, "worker capacity reached"

        lock_name = f"bot:{bot_id}:lifecycle"
        if not await self.cluster.acquire_lock(lock_name):
            return False, "lifecycle locked by another worker"

        try:
            row = await self.db.get_bot(bot_id)
            if not row:
                return False, "bot not found"

            bot, dp = await self.build(row)
            kwargs = {"secret_token": WEBHOOK_SECRET_TOKEN} if WEBHOOK_SECRET_TOKEN else {}
            await bot.set_webhook(self.webhook_url(bot_id), **kwargs)

            self.registry[bot_id] = (bot, dp)
            await self.cluster.assign_bot(bot_id, WORKER_ID)
            await self.db.set_running(bot_id, True)
            BOT_EVENTS.labels("started").inc()
            return True, "started"
        finally:
            await self.cluster.release_lock(lock_name)

    async def stop_bot(self, bot_id):
        lock_name = f"bot:{bot_id}:lifecycle"
        if not await self.cluster.acquire_lock(lock_name):
            return False, "lifecycle locked"
        try:
            item = self.registry.pop(bot_id, None)
            if item:
                bot, _ = item
                try:
                    await bot.delete_webhook(drop_pending_updates=False)
                finally:
                    await bot.session.close()
            await self.cluster.release_bot(bot_id)
            await self.db.set_running(bot_id, False)
            BOT_EVENTS.labels("stopped").inc()
            return True, "stopped"
        finally:
            await self.cluster.release_lock(lock_name)

    async def process_task(self, task):
        started = time.perf_counter()
        action = task["action"]
        try:
            if action == "start":
                ok, msg = await self.start_bot(task["bot_id"])
            elif action == "stop":
                ok, msg = await self.stop_bot(task["bot_id"])
            elif action == "restart":
                await self.stop_bot(task["bot_id"])
                ok, msg = await self.start_bot(task["bot_id"])
            else:
                raise RuntimeError(f"unknown action {action}")
            TASKS_TOTAL.labels(action, "success" if ok else "skipped").inc()
            return ok, msg
        except Exception as e:
            TASKS_TOTAL.labels(action, "error").inc()
            await self.queue.fail(task, e)
            return False, str(e)
        finally:
            TASK_LATENCY.labels(action).observe(time.perf_counter() - started)

    async def task_loop(self):
        while self.running:
            task = await self.queue.next_task(timeout=5)
            if task:
                await self.process_task(task)

    async def heartbeat_loop(self):
        while self.running:
            load = len(self.registry)
            await self.cluster.heartbeat(WORKER_ID, load)
            WORKER_LOAD.labels(WORKER_ID).set(load)
            await asyncio.sleep(20)

    async def health_loop(self):
        while self.running:
            for bot_id, (bot, _) in list(self.registry.items()):
                try:
                    await bot.get_me()
                except Exception as e:
                    await self.stop_bot(bot_id)
                    await self.queue.enqueue("start", bot_id, reason=f"healthcheck: {e}")
            await asyncio.sleep(HEALTHCHECK_INTERVAL)

    async def boot_existing(self):
        rows = await self.db.list_running_bots()
        for row in rows:
            await self.queue.enqueue("start", row.id, reason="worker_boot")

    async def run(self):
        await self.db.init()
        start_metrics()
        await self.boot_existing()
        try:
            await asyncio.gather(self.task_loop(), self.heartbeat_loop(), self.health_loop())
        finally:
            for bot_id in list(self.registry):
                await self.stop_bot(bot_id)
            await self.cluster.close()
            await self.queue.close()
            await self.db.close()

if __name__ == "__main__":
    asyncio.run(BotWorker().run())
