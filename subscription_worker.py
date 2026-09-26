import asyncio
from sqlalchemy import text

async def expire_subscriptions(session_factory, queue):
    async with session_factory() as s:
        rows=(await s.execute(text("""
          SELECT id,user_id FROM bots
          WHERE running=1
            AND subscription_expires_at IS NOT NULL
            AND subscription_expires_at <= CURRENT_TIMESTAMP
        """))).all()
        for bot_id,user_id in rows:
            await s.execute(text("UPDATE bots SET running=0 WHERE id=:id"),{"id":bot_id})
            await queue.enqueue({"type":"stop","bot_id":int(bot_id)})
        await s.commit()
    return len(rows)

async def loop(session_factory, queue, interval=300):
    while True:
        try:
            await expire_subscriptions(session_factory, queue)
        except Exception:
            pass
        await asyncio.sleep(interval)
