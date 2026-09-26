# V10 integration

V10 adds the complete payment UI and admin review components.

## Telegram
Register `payment_ui.router` in the main Aiogram Dispatcher.
Before using it, attach:
- `bot.payment_service = PaymentService(...)`
- `bot.factory_bot_id = <current child bot id>`

## Admin web
Mount:
`build_payment_admin_router(session_factory, payment_service, ADMIN_IDS)`
on the FastAPI app.

Serve `web/static/payment_admin.html` behind the existing authenticated admin area.

## Database
Apply `migrations/0002_payments.sql` after backing up the database.

## Subscription expiry
Run `subscription_worker.loop(session_factory, queue)` as a background task in the main service or a dedicated scheduler.

## Free plan
Call `activate_free(...)` when a user is granted the free 90-day plan.

The V10 modules are intentionally isolated because the V1-V9 project files can differ in their exact initialization wiring.
