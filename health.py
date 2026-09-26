
from fastapi import FastAPI
from redis.asyncio import Redis
from config import REDIS_URL

app = FastAPI(title="Bot Factory Health")

@app.get("/health")
async def health():
    r = Redis.from_url(REDIS_URL)
    try:
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    finally:
        await r.aclose()
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
