from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def renewal_keyboard(bot_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="نعم ✅", callback_data=f"renew:yes:{bot_id}")],
        [InlineKeyboardButton(text="لا ❌", callback_data=f"renew:no:{bot_id}")]
    ])

RENEWAL_TEXT = (
    "🔔 انتهى اشتراك البوت.\n\n"
    "هل تريد تجديد تفعيل البوت؟"
)
