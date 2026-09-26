from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from payments import PLANS, ZAINCASH

router = Router()

class PaymentStates(StatesGroup):
    waiting_transaction = State()

def plans_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 مجاني — 3 أشهر", callback_data="pay:free")],
        [InlineKeyboardButton(text="💵 3 أشهر — $15", callback_data="pay:3m")],
        [InlineKeyboardButton(text="💵 سنة — $40", callback_data="pay:1y")],
    ])

def payment_method_keyboard(plan):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💚 Zain Cash", callback_data=f"method:zaincash:{plan}")],
        [InlineKeyboardButton(text="↩️ رجوع", callback_data="pay:back")]
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ إلغاء", callback_data="pay:cancel")]
    ])

async def show_plans(message: Message):
    await message.answer(
        "💳 <b>الاشتراكات</b>\n\n"
        "اختر الباقة التي تريدها:",
        reply_markup=plans_keyboard(), parse_mode="HTML"
    )

@router.message(Command("subscribe"))
async def subscribe_cmd(message: Message):
    await show_plans(message)

@router.callback_query(F.data == "pay:back")
async def back(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text("💳 <b>اختر الباقة:</b>", reply_markup=plans_keyboard(), parse_mode="HTML")

@router.callback_query(F.data.startswith("pay:"))
async def choose_plan(call: CallbackQuery):
    plan=call.data.split(":")[1]
    await call.answer()
    if plan == "free":
        await call.message.answer(
            "🆓 الباقة المجانية مدتها <b>3 أشهر</b>.\n"
            "لا تحتاج إلى دفع. يمكن تفعيلها من لوحة إدارة البوت.",
            parse_mode="HTML"
        )
        return
    if plan not in PLANS:
        await call.message.answer("الباقة غير متاحة.")
        return
    await call.message.edit_text(
        f"الباقة: <b>{PLANS[plan]['name']}</b>\n"
        f"السعر: <b>${PLANS[plan]['price_usd']}</b>\n\n"
        "اختر طريقة الدفع:",
        reply_markup=payment_method_keyboard(plan), parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("method:zaincash:"))
async def zaincash_method(call: CallbackQuery, state: FSMContext):
    plan=call.data.split(":")[-1]
    await call.answer()
    # order creation is delegated to app.payment_service
    service=getattr(call.bot, "payment_service", None)
    if service is None:
        await call.message.answer("نظام الدفع غير مهيأ في الخادم.")
        return
    bot_id=getattr(call.bot, "factory_bot_id", None)
    if not bot_id:
        await call.message.answer("تعذر تحديد البوت. أعد المحاولة من بوت الإدارة.")
        return
    order=await service.create_order(call.from_user.id, bot_id, plan, "zaincash")
    await state.set_state(PaymentStates.waiting_transaction)
    await state.update_data(order_id=order["order_id"])
    await call.message.answer(
        "💚 <b>الدفع عبر Zain Cash</b>\n\n"
        f"الباقة: <b>{order['plan']}</b>\n"
        f"المبلغ: <b>${order['amount_usd']}</b>\n\n"
        f"📱 رقم المحفظة:\n<code>{order['wallet']}</code>\n\n"
        "بعد التحويل، أرسل <b>رقم عملية التحويل</b> في رسالة واحدة.\n"
        "يمكنك أيضاً إرفاق صورة الإيصال بعد إرسال الرقم.",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )

@router.message(PaymentStates.waiting_transaction, F.text)
async def transaction_number(message: Message, state: FSMContext):
    data=await state.get_data()
    order_id=data.get("order_id")
    service=getattr(message.bot, "payment_service", None)
    if not order_id or service is None:
        await state.clear()
        await message.answer("انتهت جلسة الدفع. أعد إنشاء طلب جديد عبر /subscribe.")
        return
    ok=await service.submit_receipt(order_id, message.text.strip())
    if ok:
        await state.clear()
        await message.answer(
            "✅ تم إرسال طلب الدفع للمراجعة.\n"
            f"رقم الطلب: <code>{order_id}</code>\n\n"
            "سيتم تفعيل الاشتراك بعد تأكيد عملية التحويل من الإدارة.",
            parse_mode="HTML"
        )
    else:
        await message.answer("تعذر تسجيل العملية. تأكد من رقم العملية وحاول مرة أخرى.")

@router.callback_query(F.data == "pay:cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("تم إلغاء عملية الدفع.")
    await call.message.edit_text("تم إلغاء عملية الدفع. يمكنك البدء من جديد عبر /subscribe.")
