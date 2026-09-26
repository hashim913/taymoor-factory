from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

FREE_DAYS = 90
PLANS = {
    "free": {"name": "مجاني", "price_usd": Decimal("0.00"), "days": FREE_DAYS},
    "3m": {"name": "3 أشهر", "price_usd": Decimal("15.00"), "days": 90},
    "1y": {"name": "سنة", "price_usd": Decimal("40.00"), "days": 365},
}

@dataclass(frozen=True)
class WalletPaymentConfig:
    provider: str
    wallet_number: str
    currency: str = "USD"

ZAINCASH = WalletPaymentConfig("Zain Cash", "+9647881313006")

def expiry_from(start: datetime, plan: str):
    return start + timedelta(days=PLANS[plan]["days"])

def validate_plan(plan: str):
    if plan not in PLANS:
        raise ValueError("Invalid plan")
    return PLANS[plan]
