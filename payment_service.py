import uuid
from datetime import datetime, timezone
from sqlalchemy import text

class PaymentService:
    """Manual wallet payment flow; gateway/API can replace this service later."""

    def __init__(self, session_factory, queue=None):
        self.session_factory = session_factory
        self.queue = queue

    async def create_order(self, user_id: int, bot_id: int, plan: str, provider: str = "zaincash"):
        from payments import PLANS, ZAINCASH
        if plan not in PLANS or plan == "free":
            raise ValueError("Paid plan required")
        order_id = uuid.uuid4().hex
        p = PLANS[plan]
        async with self.session_factory() as s:
            await s.execute(text("""
              INSERT INTO payment_orders
              (order_id,user_id,bot_id,plan,provider,amount_usd,currency,status,created_at)
              VALUES (:oid,:uid,:bid,:plan,:provider,:amount,'USD','pending',CURRENT_TIMESTAMP)
            """), dict(oid=order_id,uid=user_id,bid=bot_id,plan=plan,
                       provider=provider,amount=str(p["price_usd"])))
            await s.commit()
        return {
            "order_id": order_id,
            "plan": p["name"],
            "amount_usd": str(p["price_usd"]),
            "wallet": ZAINCASH.wallet_number if provider == "zaincash" else None,
        }

    async def submit_receipt(self, order_id: str, transaction_ref: str, receipt_file: str | None = None):
        async with self.session_factory() as s:
            result = await s.execute(text("""
              UPDATE payment_orders
              SET transaction_ref=:ref, receipt_file=:file, status='review',
                  submitted_at=CURRENT_TIMESTAMP
              WHERE order_id=:oid AND status='pending'
            """), {"ref": transaction_ref.strip(), "file": receipt_file, "oid": order_id})
            await s.commit()
            return result.rowcount == 1

    async def review(self, order_id: str, approved: bool, admin_id: int, note: str = ""):
        async with self.session_factory() as s:
            row = (await s.execute(text("""
              SELECT bot_id,user_id,plan,status FROM payment_orders WHERE order_id=:oid
            """), {"oid": order_id})).mappings().first()
            if not row or row["status"] != "review":
                return False
            status = "approved" if approved else "rejected"
            await s.execute(text("""
              UPDATE payment_orders
              SET status=:status, reviewed_by=:admin, reviewed_at=CURRENT_TIMESTAMP, review_note=:note
              WHERE order_id=:oid
            """), {"status":status,"admin":admin_id,"note":note,"oid":order_id})
            if approved:
                from payments import PLANS
                days=PLANS[row["plan"]]["days"]
                await s.execute(text("""
                  UPDATE bots
                  SET subscription_expires_at =
                    CASE
                      WHEN subscription_expires_at IS NOT NULL
                           AND subscription_expires_at > CURRENT_TIMESTAMP
                      THEN subscription_expires_at + (:days || ' days')::interval
                      ELSE CURRENT_TIMESTAMP + (:days || ' days')::interval
                    END,
                    running=1
                  WHERE id=:bid AND user_id=:uid
                """), {"days":days,"bid":row["bot_id"],"uid":row["user_id"]})
            await s.commit()
        if approved and self.queue:
            await self.queue.enqueue({"type":"start","bot_id":int(row["bot_id"])})
        return True
