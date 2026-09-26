from payments import PLANS
def test_v10_prices_and_free_period():
    assert PLANS["free"]["days"] == 90
    assert PLANS["3m"]["price_usd"] == 15
    assert PLANS["1y"]["price_usd"] == 40
