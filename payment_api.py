from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

class ReceiptIn(BaseModel):
    order_id: str
    transaction_ref: str
    receipt_file: str | None = None

class ReviewIn(BaseModel):
    approved: bool
    note: str = ""

def build_payment_router(service, admin_ids):
    r=APIRouter(prefix="/payments",tags=["payments"])

    @r.post("/receipt")
    async def receipt(body: ReceiptIn):
        ok=await service.submit_receipt(body.order_id,body.transaction_ref,body.receipt_file)
        if not ok: raise HTTPException(400,"Invalid or already submitted order")
        return {"ok":True}

    @r.post("/admin/{order_id}/review")
    async def review(order_id: str, body: ReviewIn, admin_id: int):
        if admin_ids and admin_id not in admin_ids: raise HTTPException(403,"admin only")
        ok=await service.review(order_id,body.approved,admin_id,body.note)
        if not ok: raise HTTPException(400,"Order is not awaiting review")
        return {"ok":True}
    return r
