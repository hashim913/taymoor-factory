
from datetime import datetime, timezone
from sqlalchemy import (
    String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Text,
    select, func, text
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from config import DATABASE_URL, DEFAULT_BOT_LIMIT


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_limit: Mapped[int] = mapped_column(Integer, default=DEFAULT_BOT_LIMIT)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    subscription_status: Mapped[str] = mapped_column(String(50), default="active")
    subscription_interval: Mapped[str] = mapped_column(String(50), default="none")
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Bot(Base):
    __tablename__ = "bots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(Text)  # encrypted in V5
    username: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    template: Mapped[str] = mapped_column(String(50), default="welcome")
    is_running: Mapped[bool] = mapped_column(Boolean, default=False)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BotSetting(Base):
    __tablename__ = "bot_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("bots.id"), unique=True, index=True)
    welcome_message: Mapped[str] = mapped_column(Text, default="👋 أهلاً بك! استخدم /start للبدء.")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(100))
    monthly_price: Mapped[int] = mapped_column(Integer, default=0)
    yearly_price: Mapped[int] = mapped_column(Integer, default=0)
    bot_limit: Mapped[int] = mapped_column(Integer, default=3)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    plan: Mapped[str] = mapped_column(String(50))
    interval: Mapped[str] = mapped_column(String(50))
    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    provider: Mapped[str] = mapped_column(String(50), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Database:
    def __init__(self):
        self.engine = create_async_engine(DATABASE_URL, future=True)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for table, column in [("users", "telegram_id"), ("payments", "telegram_id")]:
                try:
                    await conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE BIGINT"))
                except Exception:
                    pass
        await self.seed_plans()

    async def close(self):
        await self.engine.dispose()

    async def seed_plans(self):
        async with self.session() as s:
            existing = (await s.execute(select(SubscriptionPlan))).scalars().all()
            if existing:
                return
            s.add_all([
                SubscriptionPlan(code="free", title="Free", monthly_price=0, yearly_price=0, bot_limit=3),
                SubscriptionPlan(code="pro", title="Pro", monthly_price=500, yearly_price=5000, bot_limit=10),
                SubscriptionPlan(code="business", title="Business", monthly_price=1500, yearly_price=15000, bot_limit=50),
            ])
            await s.commit()

    async def get_or_create_user(self, telegram_id, username=None, first_name=None):
        async with self.session() as s:
            result = await s.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    bot_limit=DEFAULT_BOT_LIMIT,
                )
                s.add(user)
            else:
                user.username = username
                user.first_name = first_name
            await s.commit()
            return user

    async def get_user(self, telegram_id):
        async with self.session() as s:
            return (await s.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()

    async def list_users(self):
        async with self.session() as s:
            return (await s.execute(select(User).order_by(User.id.desc()))).scalars().all()

    async def set_user_limit(self, telegram_id, limit):
        async with self.session() as s:
            user = (await s.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
            if not user:
                return False
            user.bot_limit = limit
            await s.commit()
            return True

    async def set_user_blocked(self, telegram_id, blocked):
        async with self.session() as s:
            user = (await s.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
            if not user:
                return False
            user.is_blocked = blocked
            await s.commit()
            return True

    async def set_plan(self, telegram_id, plan, bot_limit=None, status="active", interval="none", expires_at=None):
        async with self.session() as s:
            user = (await s.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
            if not user:
                return False
            user.plan = plan
            user.subscription_status = status
            user.subscription_interval = interval
            user.subscription_expires_at = expires_at
            if bot_limit is not None:
                user.bot_limit = bot_limit
            await s.commit()
            return True

    async def get_plan(self, code):
        async with self.session() as s:
            return (await s.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code))).scalar_one_or_none()

    async def list_plans(self):
        async with self.session() as s:
            return (await s.execute(select(SubscriptionPlan).where(SubscriptionPlan.active == True))).scalars().all()

    async def create_payment(self, telegram_id, plan, interval, amount, currency="USD", provider="manual", external_id=None):
        async with self.session() as s:
            p = Payment(
                telegram_id=telegram_id, plan=plan, interval=interval,
                amount=amount, currency=currency, provider=provider,
                external_id=external_id, status="pending"
            )
            s.add(p)
            await s.commit()
            return p.id

    async def set_payment_status(self, payment_id, status):
        async with self.session() as s:
            p = await s.get(Payment, payment_id)
            if not p:
                return False
            p.status = status
            await s.commit()
            return True

    async def user_bot_count(self, telegram_id):
        async with self.session() as s:
            return (await s.execute(
                select(func.count(Bot.id)).join(User, Bot.user_id == User.id)
                .where(User.telegram_id == telegram_id)
            )).scalar_one()

    async def add_bot(self, telegram_id, token, username, first_name, template):
        async with self.session() as s:
            user = (await s.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one()
            bot = Bot(user_id=user.id, token=token, username=username, first_name=first_name, template=template)
            s.add(bot)
            await s.flush()
            s.add(BotSetting(bot_id=bot.id))
            await s.commit()
            return bot

    async def get_bot(self, bot_id):
        async with self.session() as s:
            return await s.get(Bot, bot_id)

    async def get_bot_for_user(self, bot_id, telegram_id):
        async with self.session() as s:
            return (await s.execute(
                select(Bot).join(User, Bot.user_id == User.id)
                .where(Bot.id == bot_id, User.telegram_id == telegram_id)
            )).scalar_one_or_none()

    async def list_user_bots(self, telegram_id):
        async with self.session() as s:
            return (await s.execute(
                select(Bot).join(User, Bot.user_id == User.id)
                .where(User.telegram_id == telegram_id).order_by(Bot.id.desc())
            )).scalars().all()

    async def list_running_bots(self):
        async with self.session() as s:
            return (await s.execute(select(Bot).where(Bot.is_running == True))).scalars().all()

    async def set_running(self, bot_id, running):
        async with self.session() as s:
            bot = await s.get(Bot, bot_id)
            if bot:
                bot.is_running = running
                if running:
                    bot.last_started_at = utcnow()
                await s.commit()

    async def update_template(self, bot_id, template):
        async with self.session() as s:
            bot = await s.get(Bot, bot_id)
            if bot:
                bot.template = template
                await s.commit()

    async def get_setting(self, bot_id):
        async with self.session() as s:
            return (await s.execute(select(BotSetting).where(BotSetting.bot_id == bot_id))).scalar_one_or_none()

    async def update_welcome(self, bot_id, message):
        async with self.session() as s:
            setting = (await s.execute(select(BotSetting).where(BotSetting.bot_id == bot_id))).scalar_one_or_none()
            if not setting:
                s.add(BotSetting(bot_id=bot_id, welcome_message=message))
            else:
                setting.welcome_message = message
            await s.commit()

    async def delete_bot(self, bot_id):
        async with self.session() as s:
            bot = await s.get(Bot, bot_id)
            if bot:
                setting = (await s.execute(select(BotSetting).where(BotSetting.bot_id == bot_id))).scalar_one_or_none()
                if setting:
                    await s.delete(setting)
                await s.delete(bot)
                await s.commit()

    async def increment_message(self, bot_id, new_user=False):
        async with self.session() as s:
            bot = await s.get(Bot, bot_id)
            if bot:
                bot.total_messages += 1
                if new_user:
                    bot.total_users += 1
                await s.commit()

    async def stats(self):
        async with self.session() as s:
            return {
                "users": (await s.execute(select(func.count(User.id)))).scalar_one(),
                "bots": (await s.execute(select(func.count(Bot.id)))).scalar_one(),
                "running": (await s.execute(select(func.count(Bot.id)).where(Bot.is_running == True))).scalar_one(),
                "messages": (await s.execute(select(func.coalesce(func.sum(Bot.total_messages), 0)))).scalar_one(),
            }

    async def user_dashboard(self, telegram_id):
        async with self.session() as s:
            user = (await s.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
            if not user:
                return None
            bots = (await s.execute(select(Bot).where(Bot.user_id == user.id).order_by(Bot.id.desc()))).scalars().all()
            return user, bots
