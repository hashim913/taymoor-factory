
import hashlib
import hmac
import time
from urllib.parse import parse_qsl
from config import MAIN_BOT_TOKEN


def verify_telegram_login(data: dict, max_age: int = 86400) -> bool:
    """
    Verifies Telegram Login Widget data.
    Telegram's hash = HMAC-SHA256(data_check_string, SHA256(bot_token)).
    """
    received_hash = data.get("hash")
    auth_date = data.get("auth_date")
    if not received_hash or not auth_date:
        return False

    try:
        if abs(time.time() - int(auth_date)) > max_age:
            return False
    except ValueError:
        return False

    check_pairs = []
    for key, value in data.items():
        if key != "hash":
            check_pairs.append((key, str(value)))
    check_pairs.sort()
    data_check_string = "\n".join(f"{k}={v}" for k, v in check_pairs)

    secret_key = hashlib.sha256(MAIN_BOT_TOKEN.encode()).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculated, received_hash)
