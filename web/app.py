import json

from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config import WEB_SECRET_KEY, ADMIN_IDS, TELEGRAM_LOGIN_BOT_USERNAME, PAYMENT_WEBHOOK_SECRET
from database import Database
from bot_manager import BotManager
from queue import TaskQueue
from cluster import Cluster
from aiogram.types import Update
from config import WEBHOOK_PATH_PREFIX, WEBHOOK_SECRET_TOKEN
from web.telegram_auth import verify_telegram_login


app = FastAPI(title="Telegram Bot Factory V5")
app.add_middleware(SessionMiddleware, secret_key=WEB_SECRET_KEY)
templates = Jinja2Templates(directory="web/templates")
db = Database()
manager = BotManager(db)
queue = TaskQueue()
cluster = Cluster()


@app.on_event("startup")
async def startup():
    await db.init()


@app.on_event("shutdown")
async def shutdown():
    await db.close()
    await queue.close()
    await cluster.close()


def uid(request: Request):
    return request.session.get("telegram_id")


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "bot_username": TELEGRAM_LOGIN_BOT_USERNAME},
    )


@app.get("/auth/telegram")
async def telegram_auth(request: Request):
    data = dict(request.query_params)
    if not verify_telegram_login(data):
        raise HTTPException(403, "Telegram authentication failed")
    telegram_id = int(data["id"])
    user = await db.get_or_create_user(
        telegram_id,
        data.get("username"),
        data.get("first_name"),
    )
    if user.is_blocked:
        raise HTTPException(403, "User blocked")
    request.session["telegram_id"] = telegram_id
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    data = await db.user_dashboard(user_id)
    if not data:
        request.session.clear()
        return RedirectResponse("/login", status_code=303)
    user, bots = data
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "bots": bots},
    )


@app.post("/bots/{bot_id}/toggle")
async def toggle(request: Request, bot_id: int):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    row = await db.get_bot_for_user(bot_id, user_id)
    if not row:
        raise HTTPException(404)
    if row.is_running:
        await queue.enqueue("stop", bot_id)
    else:
        worker = await cluster.bot_worker(bot_id) or (await cluster.choose_worker() or {}).get("worker_id")
        if not worker:
            raise HTTPException(503, "No worker capacity available")
        await cluster.assign_bot(bot_id, worker)
        await queue.enqueue("start", bot_id)
    return RedirectResponse("/", status_code=303)


@app.post("/bots/{bot_id}/delete")
async def delete(request: Request, bot_id: int):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    row = await db.get_bot_for_user(bot_id, user_id)
    if not row:
        raise HTTPException(404)
    await manager.delete_bot(bot_id)
    return RedirectResponse("/", status_code=303)


@app.get("/bots/{bot_id}", response_class=HTMLResponse)
async def bot_details(request: Request, bot_id: int):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    row = await db.get_bot_for_user(bot_id, user_id)
    if not row:
        raise HTTPException(404)
    setting = await db.get_setting(bot_id)
    return templates.TemplateResponse(
        "bot.html", {"request": request, "bot": row, "setting": setting}
    )


@app.post("/bots/{bot_id}/welcome")
async def welcome(request: Request, bot_id: int, welcome_message: str = Form(...)):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    row = await db.get_bot_for_user(bot_id, user_id)
    if not row:
        raise HTTPException(404)
    await db.update_welcome(bot_id, welcome_message)
    return RedirectResponse(f"/bots/{bot_id}", status_code=303)


@app.get("/billing", response_class=HTMLResponse)
async def billing(request: Request):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    user = await db.get_user(user_id)
    plans = await db.list_plans()
    return templates.TemplateResponse(
        "billing.html", {"request": request, "user": user, "plans": plans}
    )


@app.post("/billing/request")
async def billing_request(request: Request, plan: str = Form(...), interval: str = Form(...)):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    p = await db.get_plan(plan)
    if not p or interval not in {"monthly", "yearly"}:
        raise HTTPException(400, "Invalid plan")
    amount = p.monthly_price if interval == "monthly" else p.yearly_price
    await db.create_payment(user_id, plan, interval, amount, "USD", "manual")
    return RedirectResponse("/billing?requested=1", status_code=303)



@app.post(WEBHOOK_PATH_PREFIX + "/{bot_id}")
async def telegram_webhook(bot_id: int, request: Request):
    """
    Telegram sends updates here after the worker sets the webhook.
    Routing is delegated to the owning worker through Redis in production.
    This API returns 202 if the bot is owned by another worker; the worker
    deployment should expose the same route and consume its registry.
    """
    if WEBHOOK_SECRET_TOKEN:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET_TOKEN:
            raise HTTPException(403, "invalid webhook secret")

    # V6 web app records the request as accepted. The worker's webhook gateway
    # can consume the same endpoint when deployed behind the reverse proxy.
    worker = await queue.get_bot_worker(bot_id)
    if not worker:
        raise HTTPException(404, "bot worker not registered")
    # To keep the core package dependency-light, the web process enqueues a
    # lightweight webhook payload for the worker gateway.
    payload = await request.body()
    await queue.redis.rpush(
        f"factory:webhook:{worker}",
        json.dumps({"bot_id": bot_id, "update": json.loads(payload.decode("utf-8"))})
    )
    return {"ok": True}

@app.post("/billing/webhook")
async def billing_webhook(request: Request):
    # Provider-neutral webhook endpoint.
    # Production provider integration must validate its signature before activating plans.
    if not PAYMENT_WEBHOOK_SECRET:
        raise HTTPException(503, "Payment webhook secret not configured")
    # V5 deliberately does not auto-activate arbitrary webhook payloads.
    return {"ok": True, "message": "Webhook endpoint ready; provider adapter required."}


@app.get("/admin/api/overview")
async def admin_overview(request: Request):
    if uid(request) not in ADMIN_IDS: raise HTTPException(403)
    return {"workers": await cluster.workers(), "queue_depth": await queue.depth(), "dead_letter_depth": await queue.dead_depth()}

@app.get("/admin/api/dlq")
async def admin_dlq(request: Request):
    if uid(request) not in ADMIN_IDS: raise HTTPException(403)
    return {"items": await queue.dead_list(200)}

@app.post("/admin/api/dlq/{task_id}/retry")
async def admin_dlq_retry(request: Request, task_id: str):
    if uid(request) not in ADMIN_IDS: raise HTTPException(403)
    return {"ok": await queue.dead_retry(task_id)}

@app.delete("/admin/api/dlq/{task_id}")
async def admin_dlq_delete(request: Request, task_id: str):
    if uid(request) not in ADMIN_IDS: raise HTTPException(403)
    return {"ok": await queue.dead_delete(task_id)}

@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    user_id = uid(request)
    if user_id not in ADMIN_IDS:
        raise HTTPException(403)
    stats = await db.stats()
    users = await db.list_users()
    return templates.TemplateResponse(
        "admin.html", {"request": request, "stats": stats, "users": users}
    )


@app.post("/admin/users/{telegram_id}/plan")
async def admin_plan(request: Request, telegram_id: int, plan: str = Form(...), limit: int = Form(...)):
    user_id = uid(request)
    if user_id not in ADMIN_IDS:
        raise HTTPException(403)
    p = await db.get_plan(plan)
    if not p:
        raise HTTPException(400)
    await db.set_plan(telegram_id, plan, limit)
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/cluster")
async def cluster_status(request: Request):
    user_id = uid(request)
    if user_id not in ADMIN_IDS:
        raise HTTPException(403)
    return {"workers": await cluster.workers()}
