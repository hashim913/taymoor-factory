from sqlalchemy import text
from payments import PLANS

async def activate_free(session_factory, queue, user_id: int, bot_id: int):
    async with session_factory() as s:
        row=(await s.execute(text("""
          SELECT subscription_expires_at FROM bots
          WHERE id=:bid AND user_id=:uid
        """),{"bid":bot_id,"uid":user_id})).first()
        if not row:
            return False
        await s.execute(text("""
          UPDATE bots
          SET subscription_expires_at=CURRENT_TIMESTAMP + INTERVAL '90 days',
              running=1
          WHERE id=:bid AND user_id=:uid
        """),{"bid":bot_id,"uid":user_id})
        await s.commit()
    await queue.enqueue({"type":"start","bot_id":bot_id})
    return True
