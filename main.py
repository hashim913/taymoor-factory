
import asyncio
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MAIN_BOT_TOKEN, ADMIN_IDS, TOKEN_ENCRYPTION_KEY
from mandatory_subscription import CHANNELS, enabled as subscription_enabled, missing_channels, prompt_text, subscription_keyboard
from database import Database
from bot_manager import BotManager
from security import encrypt_token
from queue import TaskQueue
from cluster import Cluster


db = Database()
manager = BotManager(db)
queue = TaskQueue()
cluster = Cluster()


class AddBotState(StatesGroup):
    waiting_token = State()
    waiting_template = State()


class SettingsState(StatesGroup):
    waiting_welcome = State()


def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ إنشاء بوت", callback_data="add")
    kb.button(text="🤖 بوتاتي", callback_data="mybots")
    kb.button(text="💳 خطتي", callback_data="plans")
    kb.button(text="ℹ️ حسابي", callback_data="account")
    kb.adjust(2)
    return kb.as_markup()


def templates_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="👋 بوت ترحيب", callback_data="template:welcome")
    kb.button(text="💬 بوت ردود", callback_data="template:echo")
    kb.button(text="🎫 بوت دعم", callback_data="template:support")
    kb.button(text="↩️ إلغاء", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


def plans_keyboard(plans):
    kb = InlineKeyboardBuilder()
    for p in plans:
        kb.button(text=f"{p.title} — {p.monthly_price/100:.2f}$ / شهر", callback_data=f"plan:{p.code}:monthly")
    kb.adjust(1)
    return kb.as_markup()


def bot_keyboard(bot_id, running):
    kb = InlineKeyboardBuilder()
    kb.button(text="⏹ إيقاف" if running else "▶️ تشغيل", callback_data=f"toggle:{bot_id}")
    kb.button(text="⚙️ إعدادات", callback_data=f"settings:{bot_id}")
    kb.button(text="🗑 حذف", callback_data=f"delete:{bot_id}")
    kb.adjust(1)
    return kb.as_markup()


def settings_keyboard(bot_id):
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ رسالة الترحيب", callback_data=f"welcome:{bot_id}")
    kb.button(text="🔄 تغيير القالب", callback_data=f"change_template:{bot_id}")
    kb.button(text="↩️ رجوع", callback_data="mybots")
    kb.adjust(1)
    return kb.as_markup()


async def show_bots(message, user_id):
    bots = await db.list_user_bots(user_id)
    if not bots:
        await message.answer("لا توجد لديك بوتات حالياً.", reply_markup=main_keyboard())
        return
    for row in bots:
        status = "🟢 يعمل" if row.is_running else "🔴 متوقف"
        await message.answer(
            f"🤖 @{row.username}\n🆔 {row.id}\n📦 {row.template}\n"
            f"📊 {row.total_messages} رسالة\n👥 {row.total_users} مستخدم\n{status}",
            reply_markup=bot_keyboard(row.id, row.is_running),
        )


async def main():
    if not TOKEN_ENCRYPTION_KEY:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is missing. Generate one with "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    await db.init()
    bot = Bot(MAIN_BOT_TOKEN)
    dp = Dispatcher()

    @dp.update.outer_middleware()
    async def required_subscription_gate(handler, event, data):
        # /start has its own gate and the verification callback must remain accessible.
        if not subscription_enabled():
            return await handler(event, data)
        if isinstance(event, Message) and getattr(event, "text", "") and event.text.startswith("/start"):
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "check_required_subscription":
            return await handler(event, data)
        if not await ensure_required_subscription(event, bot):
            return None
        return await handler(event, data)

    async def ensure_required_subscription(event, bot: Bot) -> bool:
        if not subscription_enabled():
            return True
        user_id = event.from_user.id
        missing = await missing_channels(bot, user_id)
        if not missing:
            return True
        text = prompt_text(missing)
        markup = subscription_keyboard(missing)
        if isinstance(event, CallbackQuery):
            await event.answer("اشترك في القنوات المطلوبة أولاً.", show_alert=True)
            if event.message:
                await event.message.answer(text, reply_markup=markup)
        else:
            await event.answer(text, reply_markup=markup)
        return False

    @dp.message(CommandStart())
    async def start(message: Message, state: FSMContext):
        await state.clear()
        if not await ensure_required_subscription(message, bot):
            return
        user = await db.get_or_create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        if user.is_blocked:
            await message.answer("🚫 حسابك محظور.")
            return
        await message.answer(
            "🚀 أهلاً بك في Telegram Bot Factory V5\n\n"
            f"الخطة: {user.plan}\n"
            f"الحد: {user.bot_limit} بوت",
            reply_markup=main_keyboard(),
        )

    @dp.callback_query(F.data == "check_required_subscription")
    async def check_required_subscription(call: CallbackQuery):
        if not subscription_enabled():
            await call.answer("تم التحقق.", show_alert=False)
            return
        missing = await missing_channels(bot, call.from_user.id)
        if missing:
            await call.answer("❌ ما زلت غير مشترك في جميع القنوات المطلوبة.", show_alert=True)
            await call.message.answer(prompt_text(missing), reply_markup=subscription_keyboard(missing))
            return
        await call.answer("✅ تم التحقق بنجاح.", show_alert=True)
        await call.message.answer(
            "✅ تم التحقق من اشتراكك. أهلاً بك في مصنع تيمور!",
            reply_markup=main_keyboard(),
        )

    @dp.callback_query(F.data == "account")
    async def account(call):
        u = await db.get_user(call.from_user.id)
        await call.message.answer(
            f"👤 الحساب\n\nID: {u.telegram_id}\n"
            f"الخطة: {u.plan}\nالحد: {u.bot_limit}\n"
            f"الحالة: {u.subscription_status}\n"
            f"الانتهاء: {u.subscription_expires_at or 'غير محدد'}"
        )
        await call.answer()

    @dp.callback_query(F.data == "plans")
    async def plans(call):
        plans = await db.list_plans()
        text = "💳 الخطط المتاحة:\n\n"
        for p in plans:
            text += (
                f"• {p.title}: {p.monthly_price/100:.2f}$ شهرياً، "
                f"{p.yearly_price/100:.2f}$ سنوياً — حتى {p.bot_limit} بوت\n"
            )
        await call.message.answer(text, reply_markup=plans_keyboard(plans))
        await call.answer()

    @dp.callback_query(F.data.startswith("plan:"))
    async def plan_request(call):
        _, code, interval = call.data.split(":")
        plan = await db.get_plan(code)
        if not plan:
            await call.answer("الخطة غير موجودة.", show_alert=True)
            return
        amount = plan.monthly_price if interval == "monthly" else plan.yearly_price
        payment_id = await db.create_payment(
            call.from_user.id, code, interval, amount, "USD", "manual"
        )
        await call.message.answer(
            f"🧾 طلب اشتراك #{payment_id}\n\n"
            f"الخطة: {plan.title}\n"
            f"المدة: {'شهري' if interval == 'monthly' else 'سنوي'}\n"
            f"المبلغ: {amount/100:.2f} USD\n\n"
            "⚠️ بوابة الدفع الآلية ستُربط في النسخة التالية. "
            "حالياً الطلب يُسجل كـ pending."
        )
        await call.answer()

    @dp.callback_query(F.data == "add")
    async def add_start(call, state):
        user = await db.get_user(call.from_user.id)
        count = await db.user_bot_count(call.from_user.id)
        if user.is_blocked:
            await call.answer("🚫 حسابك محظور.", show_alert=True)
            return
        if count >= user.bot_limit:
            await call.answer(f"وصلت إلى حد {user.bot_limit} بوت.", show_alert=True)
            return
        await state.set_state(AddBotState.waiting_token)
        await call.message.answer("أرسل Token البوت من @BotFather.")
        await call.answer()

    @dp.message(AddBotState.waiting_token)
    async def receive_token(message, state):
        token = (message.text or "").strip()
        try:
            me = await manager.validate_token(token)
        except Exception:
            await message.answer("❌ Token غير صالح.")
            return
        await state.update_data(
            token=token, username=me.username or str(me.id), first_name=me.first_name or ""
        )
        await state.set_state(AddBotState.waiting_template)
        await message.answer("✅ تم التحقق. اختر القالب:", reply_markup=templates_keyboard())

    @dp.callback_query(AddBotState.waiting_template, F.data.startswith("template:"))
    async def choose_template(call, state):
        data = await state.get_data()
        template = call.data.split(":", 1)[1]

        if data.get("change_bot_id"):
            bot_id = data["change_bot_id"]
            row = await db.get_bot_for_user(bot_id, call.from_user.id)
            if not row:
                await state.clear()
                await call.answer("غير مصرح.", show_alert=True)
                return
            await db.update_template(bot_id, template)
            await state.clear()
            await call.message.answer("✅ تم تغيير القالب.", reply_markup=main_keyboard())
            await call.answer()
            return

        user = await db.get_user(call.from_user.id)
        if await db.user_bot_count(call.from_user.id) >= user.bot_limit:
            await state.clear()
            await call.answer("تم الوصول إلى الحد الأقصى.", show_alert=True)
            return

        # Encrypt token before database storage.
        encrypted = encrypt_token(data["token"])
        row = await db.add_bot(
            call.from_user.id, encrypted, data["username"], data["first_name"], template
        )
        await state.clear()
        await queue.enqueue("start", row.id)
        await call.message.answer(
            f"✅ تم إنشاء @{row.username}\n🟡 تمت إضافة البوت إلى طابور التشغيل.",
            reply_markup=main_keyboard(),
        )
        await call.answer()

    @dp.callback_query(F.data == "cancel")
    async def cancel(call, state):
        await state.clear()
        await call.message.answer("تم الإلغاء.", reply_markup=main_keyboard())
        await call.answer()

    @dp.callback_query(F.data == "mybots")
    async def mybots(call):
        await show_bots(call.message, call.from_user.id)
        await call.answer()

    @dp.callback_query(F.data.startswith("toggle:"))
    async def toggle(call):
        bot_id = int(call.data.split(":")[1])
        row = await db.get_bot_for_user(bot_id, call.from_user.id)
        if not row:
            await call.answer("غير مصرح.", show_alert=True)
            return
        if row.is_running:
            await queue.enqueue("stop", bot_id)
            await call.answer("🟡 تم إرسال طلب الإيقاف للعامل.", show_alert=True)
        else:
            await queue.enqueue("start", bot_id)
            await call.answer("🟡 تم إرسال طلب التشغيل للعامل.", show_alert=True)

    @dp.callback_query(F.data.startswith("settings:"))
    async def settings(call):
        bot_id = int(call.data.split(":")[1])
        row = await db.get_bot_for_user(bot_id, call.from_user.id)
        if not row:
            await call.answer("غير مصرح.", show_alert=True)
            return
        await call.message.answer(f"⚙️ إعدادات @{row.username}", reply_markup=settings_keyboard(bot_id))
        await call.answer()

    @dp.callback_query(F.data.startswith("welcome:"))
    async def welcome_edit(call, state):
        bot_id = int(call.data.split(":")[1])
        row = await db.get_bot_for_user(bot_id, call.from_user.id)
        if not row:
            await call.answer("غير مصرح.", show_alert=True)
            return
        await state.update_data(bot_id=bot_id)
        await state.set_state(SettingsState.waiting_welcome)
        await call.message.answer("أرسل رسالة الترحيب الجديدة. استخدم {name} للاسم.")
        await call.answer()

    @dp.message(SettingsState.waiting_welcome)
    async def save_welcome(message, state):
        data = await state.get_data()
        row = await db.get_bot_for_user(data.get("bot_id"), message.from_user.id)
        if not row:
            await state.clear()
            await message.answer("غير مصرح.")
            return
        await db.update_welcome(row.id, message.text or "")
        await state.clear()
        await message.answer("✅ تم الحفظ.", reply_markup=main_keyboard())

    @dp.callback_query(F.data.startswith("change_template:"))
    async def change_template(call, state):
        bot_id = int(call.data.split(":")[1])
        row = await db.get_bot_for_user(bot_id, call.from_user.id)
        if not row:
            await call.answer("غير مصرح.", show_alert=True)
            return
        await state.update_data(change_bot_id=bot_id)
        await state.set_state(AddBotState.waiting_template)
        await call.message.answer("اختر القالب الجديد:", reply_markup=templates_keyboard())
        await call.answer()

    @dp.callback_query(F.data.startswith("delete:"))
    async def delete(call):
        bot_id = int(call.data.split(":")[1])
        row = await db.get_bot_for_user(bot_id, call.from_user.id)
        if not row:
            await call.answer("غير مصرح.", show_alert=True)
            return
        await queue.enqueue("stop", bot_id)
        await cluster.release_bot(bot_id)
        await db.delete_bot(bot_id)
        await call.message.answer("🗑 تم حذف البوت.")
        await call.answer()

    # Admin commands
    @dp.message(Command("admin"))
    async def admin(message):
        if message.from_user.id not in ADMIN_IDS:
            return
        st = await db.stats()
        await message.answer(
            f"🛠 Admin\nالمستخدمون: {st['users']}\nالبوتات: {st['bots']}\n"
            f"العاملة: {st['running']}\nالرسائل: {st['messages']}"
        )

    @dp.message(Command("activate"))
    async def activate(message):
        if message.from_user.id not in ADMIN_IDS:
            return
        parts = (message.text or "").split()
        if len(parts) < 3 or not parts[1].isdigit():
            await message.answer("الاستخدام: /activate USER_ID PLAN [days]")
            return
        uid, plan_code = int(parts[1]), parts[2]
        plan = await db.get_plan(plan_code)
        if not plan:
            await message.answer("الخطة غير موجودة.")
            return
        days = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 30
        expires = datetime.now(timezone.utc) + timedelta(days=days)
        await db.set_plan(uid, plan.code, plan.bot_limit, "active", "manual", expires)
        await message.answer("✅ تم تفعيل الخطة.")

    @dp.message(Command("users"))
    async def users(message):
        if message.from_user.id not in ADMIN_IDS:
            return
        users = await db.list_users()
        await message.answer("\n".join(
            f"{u.telegram_id} | @{u.username or '-'} | {u.plan} | limit={u.bot_limit}"
            for u in users[:50]
        ) or "لا يوجد مستخدمون.")

    print("Telegram Bot Factory V5 started.")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await queue.close()
        await cluster.close()


if __name__ == "__main__":
    asyncio.run(main())
