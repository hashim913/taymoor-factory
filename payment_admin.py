from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

def build_payment_admin_router(session_factory, service, admin_ids):
    r=APIRouter(prefix="/admin/payments",tags=["admin-payments"])

    def allowed(request: Request):
        uid=getattr(request.state,"user_id",None)
        return uid is not None and (not admin_ids or int(uid) in admin_ids)

    @r.get("")
    async def list_orders(request: Request, status: str = "review", limit: int = 100):
        if not allowed(request): raise HTTPException(403,"admin only")
        async with session_factory() as s:
            rows=(await s.execute(text("""
              SELECT p.order_id,p.user_id,p.bot_id,p.plan,p.provider,p.amount_usd,p.currency,
                     p.status,p.transaction_ref,p.receipt_file,p.created_at,p.submitted_at
              FROM payment_orders p
              WHERE (:status='' OR p.status=:status)
              ORDER BY p.created_at DESC LIMIT :limit
            """),{"status":status,"limit":min(max(limit,1),500)})).mappings().all()
        return {"items":[dict(x) for x in rows]}

    @r.post("/{order_id}/approve")
    async def approve(order_id: str, request: Request):
        if not allowed(request): raise HTTPException(403,"admin only")
        uid=int(request.state.user_id)
        ok=await service.review(order_id,True,uid,"Approved by admin")
        if not ok: raise HTTPException(400,"Order is not awaiting review")
        return {"ok":True}

    @r.post("/{order_id}/reject")
    async def reject(order_id: str, request: Request):
        if not allowed(request): raise HTTPException(403,"admin only")
        uid=int(request.state.user_id)
        ok=await service.review(order_id,False,uid,"Rejected by admin")
        if not ok: raise HTTPException(400,"Order is not awaiting review")
        return {"ok":True}
    return r
