from dataclasses import dataclass
from typing import Iterable

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import REQUIRED_CHANNELS


@dataclass(frozen=True)
class RequiredChannel:
    chat_id: str
    url: str
    title: str


def parse_required_channels(raw: str = REQUIRED_CHANNELS) -> list[RequiredChannel]:
    """Parse REQUIRED_CHANNELS.

    Format per channel: chat_id|url|title
    Example: @mychannel|https://t.me/mychannel|قناة الأخبار
    Multiple channels are separated by commas.
    The title is optional.
    """
    result = []
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        parts = [p.strip() for p in item.split('|')]
        chat_id = parts[0]
        url = parts[1] if len(parts) > 1 and parts[1] else (
            f"https://t.me/{chat_id.lstrip('@')}" if chat_id.startswith('@') else "https://t.me/"
        )
        title = parts[2] if len(parts) > 2 and parts[2] else chat_id
        result.append(RequiredChannel(chat_id=chat_id, url=url, title=title))
    return result


CHANNELS = parse_required_channels()


def subscription_keyboard(channels: Iterable[RequiredChannel]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for ch in channels:
        kb.button(text=f"📢 {ch.title}", url=ch.url)
    kb.button(text="✅ تحقّق من الاشتراك", callback_data="check_required_subscription")
    kb.adjust(1)
    return kb.as_markup()


async def missing_channels(bot: Bot, user_id: int) -> list[RequiredChannel]:
    missing = []
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(ch.chat_id, user_id)
            status = getattr(member, "status", "")
            is_member = getattr(member, "is_member", False)
            if status not in {"member", "administrator", "creator"} and not (status == "restricted" and is_member):
                missing.append(ch)
        except Exception:
            # If Telegram cannot verify the channel, keep the user blocked rather than bypassing the gate.
            missing.append(ch)
    return missing


def enabled() -> bool:
    return bool(CHANNELS)


def prompt_text(channels: Iterable[RequiredChannel]) -> str:
    names = "\n".join(f"• {ch.title}" for ch in channels)
    return (
        "🔒 يجب الاشتراك في القنوات التالية قبل استخدام مصنع تيمور:\n\n"
        f"{names}\n\n"
        "بعد الاشتراك اضغط «تحقّق من الاشتراك»."
    )
