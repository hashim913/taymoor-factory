from payments import PLANS, expiry_from
from datetime import datetime, timezone

def test_plans():
    assert PLANS["free"]["days"] == 90
    assert str(PLANS["3m"]["price_usd"]) == "15.00"
    assert str(PLANS["1y"]["price_usd"]) == "40.00"

def test_expiry():
    now=datetime.now(timezone.utc)
    assert (expiry_from(now,"3m")-now).days==90
